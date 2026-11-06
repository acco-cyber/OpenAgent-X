# Action protocol

Respond with **exactly one JSON object** and nothing else.

To use a tool:

```json
{"action": {"tool": "<tool name>", "args": {…}}, "thought": "<one line why>"}
```

To finish the task:

```json
{"reply": "<final answer for the human>"}
```

Rules:

- One action per turn; wait for the observation, then decide.
- Before using a non-core tool, discover it first with `find_tools`.
- If a response is rejected as a protocol error, re-emit the JSON object only.
