# Design decisions

Short records of *why*, so each choice can be defended or changed deliberately.

### D1. Deterministic core, LLM for judgment
Maths (projection, safety stock, requirement, cost) and rule checks are code; the LLM investigates, interprets, chooses and explains. LLMs make arithmetic slips, and rules must be applied identically every time. The engine is pure (no I/O) and fully unit-tested; the tests assert it reproduces every fixture's hand-computed answer.

### D2. Read/write split (CQRS) as the safety model
`read_api` opens SQLite with `mode=ro`, so investigation physically cannot change data (tested). `write_api` is the only service that writes, and every write goes through validation → approval → idempotent execution → verification. The agent investigates through the Read API over HTTP and acts only by submitting a decision.

### D3. The planning snapshot lives in `shared/db/snapshot.py`
Both sides need the identical "DB rows → engine input" view. The write side must re-validate a plan **inside its own transaction** right before writing; asking the Read API over HTTP would open a check-then-write race. The snapshot only SELECTs and accepts either session type. Everything else read-related stays in `read_api`.

### D4. Protection interval = arrival offset + review period; open POs counted on their real date
The order placed now must last until the *next* order arrives. "Arrival offset" includes the order cut-off hour and the supplier's delivery weekdays, not just the nominal lead time. Open POs arriving after the horizon don't protect this cycle and are reported separately.

### D5. Safety stock on the *need* side
`need = demand over horizon + SS − (on hand + open POs in time)`. Counting SS as supply would double-count the buffer. SS = z·√(Σσ_d² + d̄²σ_L²) (periodic review; Silver, Pyke & Thomas).

### D6. Day-by-day projection with FEFO lots, lost sales (no backorders)
Storage overflows on a specific day, and food expires lot by lot, so a single formula isn't enough. Quick-commerce customers don't wait, so unmet demand is lost, not backordered.
Shelf-life convention: a lot arriving on day *a* with *r* days left is written off at the start of day *a + r − buffer* (buffer = 1 day).

### D7. Decision cost compares only costs that differ
Purchase cost isn't a cost here because the goods get sold. Options are compared on price premium vs the cheapest supplier, express premium, holding, avoidable lost sales × margin × churn multiplier, and expired units. Purchase value is still reported for the budget rule.

### D8. Express is a bridge, not a default
Express is only proposed when standard delivery arrives after stock falls below safety stock. The bridge keeps stock **≥ safety stock** (not just ≥ 0) until the standard delivery; the rest goes standard. All-express is still listed but needs approval over the premium threshold.

### D9. Hard vs soft rules
**Hard** (never overridden): storage capacity, shelf-life waste, MOQ/case pack, supplier active / max qty, delivery calendar, duplicates. **Soft** (need a human): budget, avoidable stockout, below safety stock, PO value, *increasing* spend > 30% over the recommendation, express premium, low supplier reliability.
Buying *less* than recommended doesn't need approval when the projection proves coverage, so automation still has value.

### D10. Stockouts the plan can't fix aren't blamed on the plan
Lost sales before any supplier could possibly deliver are "unavoidable" and don't trigger the stockout rule. Otherwise every option would need approval.

### D11. Generic LLM endpoint
Only `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` (OpenAI-compatible). No provider names in code. Tool arguments and the decision form are validated in our code, because provider-side strict schemas differ (Claude's compatibility layer ignores `strict`).
