## Situation
Supplier **{supplier}** answered on purchase order `{po_id}` for **{sku}** at store **{node}**:
it can deliver only **{qty_confirmed} of {qty_ordered}** units.
Supplier message: "{message}"
Today is {today}.

Decide what should happen next. First find out whether the shortfall actually matters (does stock plus what
is still coming cover the protection interval?). If it does matter, compare the alternatives: another
supplier, spare stock at another dark store, or a mix. Escalate if nothing works. Use the calculator tools
for every number, then call `submit_decision` (`accept` = no further action needed, `modify` = new order
lines and/or transfers).
