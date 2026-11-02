## Situation
Demand monitoring raised an alert for **{sku}** at store **{node}**: "{message}"
Today is {today}.

Determine whether the purchasing plan needs to change. Look at the evidence first: daily sales, stockout
days, promotions, and `analyze_demand`. Decide which demand to plan on (the forecast, or a different level
for some or all of the horizon) and why. Then check coverage with the calculator tools on that demand and
call `submit_decision`: `accept` = the current plan (stock + open orders) is enough; `modify` = additional
order lines/transfers, with your `demand_assumption`.
