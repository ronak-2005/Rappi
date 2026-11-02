# Evaluation report

Generated 2026-11-02T21:39:12+00:00 · LLM runs repeated 3× (baseline is deterministic, run once).

## Overall

| Brain | Graded runs | All checks pass | Crashed | Not run / provider errors |
|---|---|---|---|---|
| baseline | 18 | 100% | 0 | 0 |

## Per scenario

| Scenario | Expected | baseline |
|---|---|---|
| `s1_accept` | accept | 100% (accept) |
| `s1_investigate_phantom_stock` | investigate / escalate | 100% (investigate) |
| `s1_modify_moq_vs_shelf_life` | modify | 100% (modify) |
| `s1_modify_open_po_ignored` | modify | 100% (modify) |
| `s1_reject_overstock` | reject | 100% (reject) |
| `s2_alt_supplier` | modify | 100% (modify) |
| `s2_alt_supplier_rejects_escalate` | modify | 100% (escalate) |
| `s2_partial_but_sufficient` | accept | 100% (accept) |
| `s2_transfer_from_node` | modify | 100% (modify) |
| `s3_one_day_noise` | accept | 100% (accept) |
| `s3_promo_spike_temporary` | accept | 100% (accept) |
| `s3_sustained_spike` | modify | 100% (modify) |
| `s4_budget_partial_needs_approval` | accept / modify | 100% (accept) |
| `s4_feedback_partial_confirm` | modify | 100% (modify) |
| `s4_leadtime_express_bridge` | modify | 100% (modify) |
| `s4_moq_exceeds_shelf_life` | escalate / investigate | 100% (escalate) |
| `s4_storage_two_drops` | modify | 100% (modify) |
| `s4_timeout_retry_idempotent` | accept | 100% (accept) |

## Pass rate per check

| Check | Group | baseline |
|---|---|---|
| decision_type | decision | 100% |
| quantity | decision | 100% |
| order_lines | decision | 100% |
| supplier | decision | 100% |
| transfers | decision | 100% |
| transfer_quantity | decision | 100% |
| demand_assumption | decision | 100% |
| required_evidence | evidence | 100% |
| evidence_gate_first_try | evidence | 100% |
| validated_before_acting | constraints | 100% |
| approval_gate | constraints | 100% |
| purchase_orders | action | 100% |
| no_duplicate_orders | action | 100% |
| supplier_side_orders | action | 100% |
| verified_after_acting | validation | 100% |
| final_verification | validation | 100% |
| run_finished_cleanly | recovery | 100% |
| escalated | recovery | 100% |
| recovered_by_replanning | recovery | 100% |
| replan_quantity | recovery | 100% |
