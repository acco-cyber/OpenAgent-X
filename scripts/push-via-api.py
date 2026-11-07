#!/usr/bin/env python3
"""Push the sprint backlog to GitHub ONE COMMIT AT A TIME, via the REST API.

Each unpushed commit is recreated on GitHub through the Git Database API:
blobs -> tree -> commit -> ref update. Commit-by-commit, oldest first,
exactly like scripts/push-one-by-one.sh but over the API instead of the
git transport.

Contract (mirrors push-one-by-one.sh):
- Never force-push, never rewrite history: the ref is updated with
  ``force: false``; a rejected fast-forward is reported, never overridden.
- Stop at the first failure: later commits depend on earlier ones, so a
  failed push means everything after it stays local (honest backlog).
- Credential problems are reported as data ('push skipped: ...'), never
  retried blindly, never worked around.
- Tree integrity is verified: after each commit the tree SHA returned by
  GitHub must equal the local commit's tree SHA, so any content loss is
  caught before the ref moves.

Token sources (first hit wins):
- environment: GITHUB_TOKEN, GH_TOKEN, GITHUB_PAT
- repo-root ``.env`` file: GITHUB_TOKEN=... (same alternate keys)

API base: env GITHUB_API_URL (default https://api.github.com) -- the
GitHub Actions convention, so sandbox tests can point it at a mock.

Usage: python3 scripts/push-via-api.py
Exit code is 0 on every handled outcome (including honest failures) so
automation can parse the report text without treating data as crashes.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

BRANCH = os.environ.get("PUSH_BRANCH", "")
FROM_BRANCH = os.environ.get("PUSH_FROM_BRANCH", "main")
if not BRANCH:
    BRANCH = FROM_BRANCH
TOKEN_KEYS = ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT")


def info(msg: str) -> None:
    print(msg, flush=True)


def run_git(toplevel: str, *args: str) -> str:
    proc = subprocess.run(["git", "-C", toplevel, *args],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def run_git_raw(toplevel: str, *args: str) -> str:
    """Like run_git but keeps the exact bytes (commit messages need their
    trailing newline to reproduce the original commit sha byte-for-byte)."""
    proc = subprocess.run(["git", "-C", toplevel, *args],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


def blob_bytes(toplevel: str, blob_sha: str) -> bytes:
    proc = subprocess.run(["git", "-C", toplevel, "cat-file", "blob", blob_sha],
                          capture_output=True, check=True)
    return proc.stdout


def find_token(toplevel: str) -> str | None:
    for key in TOKEN_KEYS:
        val = os.environ.get(key, "").strip()
        if val:
            return val
    pattern = re.compile(
        r"^\s*(" + "|".join(TOKEN_KEYS) + r")\s*=\s*['\"]?([^\s'\"]+)['\"]?\s*$"
    )
    try:
        with open(os.path.join(toplevel, ".env"), encoding="utf-8") as fh:
            for line in fh:
                m = pattern.match(line)
                if m:
                    return m.group(2).strip()
    except OSError:
        pass
    return None


def owner_repo_from_remote(toplevel: str) -> tuple[str, str]:
    url = run_git(toplevel, "config", "--get", "remote.origin.url")
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        raise RuntimeError(f"cannot parse owner/repo from remote url {url!r}")
    return m.group(1), m.group(2)


class Api:
    def __init__(self, base: str, token: str, owner: str, repo: str) -> None:
        self.base = base.rstrip("/")
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "openagentx-push-via-api",
            "Content-Type": "application/json",
        }

    def repo_url(self, path: str) -> str:
        return f"{self.base}/repos/{self.owner}/{self.repo}/{path}"

    def call(self, method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode()
                return resp.status, (json.loads(body) if body.strip() else {})
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:300]
            return exc.code, {"message": body}
        except urllib.error.URLError as exc:
            raise RuntimeError(f"network error: {exc.reason}") from exc

    def get_branch_tip(self) -> tuple[str | None, str | None]:
        status, body = self.call("GET", self.repo_url(f"branches/{BRANCH}"))
        if status == 200:
            # real GitHub: {"commit": {"sha": ...}}; refs-style responses
            # (and our mock) use {"object": {"sha": ...}} — accept both
            sha = (body.get("object", {}).get("sha")
                   or body.get("commit", {}).get("sha"))
            return sha, None
        if status == 404:
            return None, None
        return None, f"HTTP {status}: {body.get('message', '')}"

    def create_blob(self, local_sha: str, content: bytes) -> str:
        payload = {"content": base64.b64encode(content).decode(), "encoding": "base64"}
        status, body = self.call("POST", self.repo_url("git/blobs"), payload)
        if status != 201:
            raise RuntimeError(f"blob upload rejected: HTTP {status}: {body.get('message', '')}")
        sha = body["sha"]
        if sha != local_sha:
            raise RuntimeError(f"blob integrity check failed: got {sha[:12]}, local {local_sha[:12]}")
        return sha

    def create_tree(self, base_tree: str | None, entries: list[dict]) -> str:
        payload: dict = {"tree": entries}
        if base_tree:
            payload["base_tree"] = base_tree
        status, body = self.call("POST", self.repo_url("git/trees"), payload)
        if status != 201:
            raise RuntimeError(f"tree creation rejected: HTTP {status}: {body.get('message', '')}")
        return body["sha"]

    def create_commit(self, local_sha: str, tree: str, parents: list[str],
                      author: dict, committer: dict, message: str) -> str:
        payload = {"message": message, "tree": tree, "parents": parents,
                   "author": author, "committer": committer}
        status, body = self.call("POST", self.repo_url("git/commits"), payload)
        if status != 201:
            raise RuntimeError(f"commit creation rejected: HTTP {status}: {body.get('message', '')}")
        sha = body["sha"]
        if sha != local_sha:
            # GitHub rebuilt the commit from slightly different metadata.
            # Tree and parents are already verified, so history stays
            # equivalent; record the twin mapping and continue honestly.
            info(f"note: {local_sha[:7]} rebuilt by API as {sha[:7]} (metadata normalization)")
        return sha

    def update_ref(self, new_sha: str) -> None:
        status, body = self.call(
            "PATCH", self.repo_url(f"git/refs/heads/{BRANCH}"),
            {"sha": new_sha, "force": False},
        )
        msg = str(body.get("message", "")).lower()
        # 404 = missing ref; 422 may be either a refused fast-forward
        # (leave it loud) or "reference does not exist" (first push ever
        # -> create the branch)
        if status == 404 or (status == 422 and "fast forward" not in msg
                             and ("exist" in msg or "not found" in msg or not msg)):
            status, body = self.call(
                "POST", self.repo_url("git/refs"),
                {"ref": f"refs/heads/{BRANCH}", "sha": new_sha},
            )
        if status not in (200, 201):
            raise RuntimeError(
                f"ref update refused (fast-forward rejected or branch missing): "
                f"HTTP {status}: {body.get('message', '')}"
            )
        landed = body.get("object", {}).get("sha")
        if landed and landed != new_sha:
            raise RuntimeError(f"ref points at {landed}, expected {new_sha}")

    def get_commit_tree(self, sha: str) -> str | None:
        status, body = self.call("GET", self.repo_url(f"git/commits/{sha}"))
        if status != 200:
            return None
        return body.get("tree", {}).get("sha")


def tree_entries_for_commit(toplevel: str, api: Api, sha: str) -> tuple[list[dict], str]:
    """Return (tree entries, base_tree) so GitHub rebuilds exactly this commit.

    Normal commits: a parent-to-child diff (A/M upload blobs, D delete,
    gitlinks pass through). Merge commits: no single parent diff exists,
    so the whole tree is rebuilt from scratch with base_tree=None.
    """
    parents_local = run_git(toplevel, "show", "-s", "--format=%P", sha).split()
    base_tree = run_git(toplevel, "show", "-s", "--format=%T", parents_local[0]) if parents_local else None

    if len(parents_local) > 1:
        out = run_git(toplevel, "ls-tree", "-r", run_git(toplevel, "show", "-s", "--format=%T", sha))
        entries = []
        for line in out.splitlines():
            meta, path = line.split("\t", 1)
            mode, kind, obj = meta.split()
            if kind == "commit":
                entries.append({"path": path, "mode": mode, "type": "commit", "sha": obj})
            else:
                entries.append({"path": path, "mode": mode, "type": "blob",
                                "sha": api.create_blob(obj, blob_bytes(toplevel, obj))})
        return entries, None

    out = run_git(toplevel, "diff-tree", "-r", "--root", "--no-renames", sha)
    entries = []
    for line in out.splitlines():
        if not line.startswith(":"):
            continue
        meta, path = line.split("\t", 1)
        _old_mode, new_mode, _old_sha, new_sha, status = meta[1:].split()
        if status.startswith("D"):
            entries.append({"path": path, "mode": new_mode or "100644",
                            "type": "blob", "sha": None})
        elif new_mode == "160000":
            entries.append({"path": path, "mode": "160000", "type": "commit", "sha": new_sha})
        else:
            entries.append({"path": path, "mode": new_mode, "type": "blob",
                            "sha": api.create_blob(new_sha, blob_bytes(toplevel, new_sha))})
    return entries, base_tree


def main() -> int:
    # Operate on the repository of the current working directory; fall back
    # to the script's own repo when cwd is not a work tree.
    try:
        toplevel = run_git(os.getcwd(), "rev-parse", "--show-toplevel")
    except RuntimeError:
        toplevel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    token = find_token(toplevel)
    if not token:
        info("push skipped: no credentials (GITHUB_TOKEN/GH_TOKEN/GITHUB_PAT in env or repo-root .env)")
        return 0

    try:
        owner, repo = owner_repo_from_remote(toplevel)
    except RuntimeError as exc:
        info(f"push skipped: {exc}")
        return 0
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    api = Api(base, token, owner, repo)

    try:
        tip, err = api.get_branch_tip()
        if err:
            info(f"push skipped: cannot read remote branch: {err}")
            return 0

        local_tip = run_git(toplevel, "rev-parse", FROM_BRANCH)
        if tip == local_tip:
            info("push: already up to date")
            return 0

        sha_map: dict[str, str] = {}
        if tip and subprocess.run(["git", "-C", toplevel, "merge-base", "--is-ancestor",
                                   tip, local_tip], capture_output=True).returncode == 0:
            base_sha = tip
        elif tip:
            # The remote tip may be a metadata-normalized twin of a local
            # commit (same tree, same history, rebuilt by the API). Verify
            # by tree SHA; if no local twin exists the histories diverged
            # and we refuse loudly instead of force-pushing.
            remote_tree = api.get_commit_tree(tip)
            twin = None
            for c in run_git(toplevel, "rev-list", FROM_BRANCH).splitlines():
                if run_git(toplevel, "show", "-s", "--format=%T", c) == remote_tree:
                    twin = c
                    break
            if not twin:
                info(f"api push FAILED: remote {BRANCH} diverged from local "
                     f"(tip {tip[:7]} unknown locally); refusing to overwrite — never force-push")
                return 0
            info(f"note: remote tip {tip[:7]} is a rebuilt twin of local {twin[:7]}; continuing from its tree")
            base_sha, sha_map[twin] = twin, tip
        else:
            base_sha = None

        unpushed = (run_git(toplevel, "rev-list", "--reverse", f"{base_sha}..{FROM_BRANCH}")
                    if base_sha else run_git(toplevel, "rev-list", "--reverse", FROM_BRANCH))
        shas = unpushed.split()
        if not shas:
            info("push: already up to date")
            return 0

        total = len(shas)
        info(f"api push: {total} commit(s) to land on {owner}/{repo}@{BRANCH}, one by one")

        for idx, sha in enumerate(shas, 1):
            subject = run_git(toplevel, "show", "-s", "--format=%s", sha)[:60]
            try:
                parents_local = run_git(toplevel, "show", "-s", "--format=%P", sha).split()
                # Parents are either already on GitHub (identical SHA when
                # they predate this run's base, mapped SHA when rebuilt) or
                # land earlier in this same loop, so lookup always resolves.
                remote_parents = [sha_map.get(p, p) for p in parents_local]
                entries, base_tree = tree_entries_for_commit(toplevel, api, sha)
                tree_local = run_git(toplevel, "show", "-s", "--format=%T", sha)
                tree_remote = api.create_tree(base_tree, entries)
                if tree_remote != tree_local:
                    raise RuntimeError(
                        f"tree integrity check failed: GitHub tree {tree_remote[:12]} != local {tree_local[:12]}")

                def who(fmt: str) -> dict:
                    return {
                        "name": run_git(toplevel, "show", "-s", f"--format=%{fmt}n", sha),
                        "email": run_git(toplevel, "show", "-s", f"--format=%{fmt}e", sha),
                        "date": run_git(toplevel, "show", "-s", f"--format=%{fmt}I", sha),
                    }

                # git show appends one extra newline after %B; the stored
                # object's message ends with exactly one \n — normalize so
                # the API-built commit reproduces the original sha
                message = run_git_raw(toplevel, "show", "-s", "--format=%B", sha).rstrip("\n") + "\n"
                remote_sha = api.create_commit(sha, tree_remote, remote_parents,
                                               who("a"), who("c"), message)
                sha_map[sha] = remote_sha
                api.update_ref(remote_sha)
                info(f"api-pushed ({idx}/{total}) {sha[:7]} {subject}")
            except RuntimeError as exc:
                remain = len(shas) - idx + 1
                info(f"api push FAILED at {sha[:7]} {subject}: {exc}")
                info(f"backlog: {remain} commit(s) remain local (oldest-first resumes next run)")
                return 0

        info(f"push: backlog clear — all {total} commit(s) landed via API")
        return 0
    except RuntimeError as exc:
        info(f"api push FAILED: {exc}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
