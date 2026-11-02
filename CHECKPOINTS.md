# Checkpoints

Every push is tagged `checkpoint-NN-<name>`. Check one out with `git checkout checkpoint-NN-<name>`.

| Tag | What works at this point |
|---|---|
| `checkpoint-00-scaffold` | Repo layout (backend read/write split + frontend), env examples, Makefile, import-boundary tests |
| `checkpoint-01-data-model` | DB schema, read-only vs read-write sessions (writes rejected on the read side), policy.yaml, fixture format + loader, 11 S1/S4 fixtures with hand-computed expected outcomes |
