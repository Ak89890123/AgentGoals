# Goal Artifact Tool Fixtures v1

These are declarative inputs for the repo-local Goal artifact tool. They are
not source Goals and must not be placed under a `goals/` tree, because the
reconciler deliberately scans Goal-shaped files there.

- `small-no-write.json`: a chat-only decision; preview must create nothing.
- `standard-single-file.json`: a valid one-file Goal Contract scaffold.
- `goal-grade-directory.json`: a valid Contract/Plan/Evidence directory scaffold.
- `invalid-small-write.json`: a rejected layout/write mismatch.

The fixtures contain no user content and are safe to use in isolated tests.
