## Situation
The replenishment system recommends buying **{qty} units of {sku}** for store **{node}**{supplier_text}
(recommendation `{recommendation_id}`). Today is {today}.

Decide whether to accept, modify, reject or investigate this recommendation. Investigate first,
use the calculator tools for all numbers, then call `submit_decision` with order lines (if buying),
reasons citing tool_call ids, risks, confidence and a short plain-language summary for the buyer.
