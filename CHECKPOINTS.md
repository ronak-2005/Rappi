# Checkpoints

Every push is tagged `checkpoint-NN-<name>`. Check one out with `git checkout checkpoint-NN-<name>`.

| Tag | What works at this point |
|---|---|
| `checkpoint-00-scaffold` | Repo layout (backend read/write split + frontend), env examples, Makefile, import-boundary tests |
| `checkpoint-01-data-model` | DB schema, read-only vs read-write sessions (writes rejected on the read side), policy.yaml, fixture format + loader, 11 S1/S4 fixtures with hand-computed expected outcomes |
| `checkpoint-02-engine` | Pure planning engine: calendar, safety stock, day-by-day FEFO projection (expiry + storage), net requirement, option generator (standard / express / bridge / two drops / within budget / waste-free) with decision cost and per-rule checks, data-quality flags. Engine reproduces every fixture's hand-computed answer |
| `checkpoint-02.1-engine-fix` | ⚠️ `checkpoint-02-engine` was pushed with 1 failing test (phantom-stock rule flagged stores that genuinely sold out days ago). Fixed here: the rule only fires when the product sold *yesterday* while the system shows 0. From now on every checkpoint goes through `scripts/checkpoint.sh`, which refuses to commit unless all tests pass |
