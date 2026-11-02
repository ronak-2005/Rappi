## Situation
Supplier **{supplier}** answered on purchase order `{po_id}` for **{sku}** at store **{node}**:
it can deliver only **{qty_confirmed} of {qty_ordered}** units.
Supplier message: "{message}"
Today is {today}.

Decide what should happen next. First find out whether the shortfall actually matters (does stock plus what
is still coming cover the protection interval?). If it does matter, compare the alternatives: another
supplier, spare stock at another dark store, or a mix. Escalate if nothing works. Use the calculator tools
for every number, then call `submit_decision`.
Decision types here: `accept` = no further action needed · `modify` = new order lines and/or transfers ·
`escalate` = nothing feasible. (`reject` does not apply to a supplier shortfall.)
Required before deciding: `get_inventory`, `get_open_pos`, and either `project_inventory` (to accept) or
`get_supplier_terms`, `get_other_nodes_stock`, `get_budget`, `get_storage_status` (to act).
