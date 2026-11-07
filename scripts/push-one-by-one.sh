#!/bin/sh
# Push the sprint backlog ONE COMMIT AT A TIME, oldest first.
#
# Contract:
# - Never force-push, never rewrite history: plain fast-forward pushes of
#   each commit SHA to refs/heads/main, strictly in chronological order.
# - Stop at the first failure: later commits depend on earlier ones, so a
#   failed push means everything after it stays local (honest backlog).
# - Credential failures are reported as data ('push skipped: no
#   credentials'), never retried blindly, never worked around.
#
# Usage: sh scripts/push-one-by-one.sh [remote]
set -eu

REMOTE=${1:-origin}
BRANCH=main

cd "$(git rev-parse --show-toplevel)"

if ! timeout 30 git fetch "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
    echo "push skipped: no credentials (fetch $REMOTE failed)"
    exit 0
fi

# remote-tracking ref when configured (origin/main); FETCH_HEAD fallback
# for URL remotes (no tracking refs are written there)
BASE=$(git rev-parse --verify --quiet "$REMOTE/$BRANCH" 2>/dev/null \
    || git rev-parse -q --verify FETCH_HEAD 2>/dev/null || true)
if [ -z "$BASE" ]; then
    echo "push skipped: $REMOTE/$BRANCH unknown after fetch"
    exit 0
fi

UNPUSHED=$(git rev-list --reverse "$BASE..$BRANCH")
if [ -z "$UNPUSHED" ]; then
    echo "push: already up to date"
    exit 0
fi

for sha in $UNPUSHED; do
    subject=$(git log -1 --format='%s' "$sha" | cut -c1-60)
    if timeout 60 git push "$REMOTE" "$sha:refs/heads/$BRANCH" >/dev/null 2>&1; then
        echo "pushed $(git log -1 --format='%h' "$sha") $subject"
    else
        echo "push FAILED at $(git log -1 --format='%h' "$sha") $subject"
        echo "backlog: $(git rev-list --count "$sha..$BRANCH") commits remain local"
        exit 0
    fi
done
echo "push: backlog clear"
