# Financial model — assumptions, not achieved savings

Bank-sponsored integration hypothesis. No paid contract, approved budget or consumer revenue. RUB/year unless one-time. All inputs below are illustrative, not bank data or vendor quotes. Fixture accuracy and clicks are not monetized.

This is an independent annual operating sensitivity grid, not the same rollout scenarios as PRODUCT_DISCOVERY. Here N requires at least 10000/25000/50000 actual annual exposures (and more if not everyone is warned). Discovery's illustrative rollout reaches only 500/6000/31500: those populations cannot support this N. Applying those smaller reach caps would reduce benefits further. Validate attainable reach before using any economic scenario as a forecast; no bridge from current MVP adoption to these volumes has been demonstrated.

| Variable | Conservative | Base | Optimistic |
|---|---:|---:|---:|
| N warned unique users/year | 10000 | 25000 | 50000 |
| q eligible avoidable episodes/user/year | .003 | .006 | .01 |
| d incremental avoided bank-loss fraction | .02 | .05 | .10 |
| L avoidable bank-attributable loss/episode | 5000 | 10000 | 20000 |
| Avoided loss N*q*d*L | 3000 | 75000 | 1000000 |
| Support savings | 20000 | 100000 | 250000 |
| False-positive exposure share | .03 | .02 | .01 |
| Cost/FP support event | 200 | 200 | 200 |
| FP cost N*share*cost | 60000 | 100000 | 100000 |
| One-time integration+pilot | 600000 | 900000 | 1200000 |
| Annual infrastructure | 60000 | 90000 | 120000 |
| Annual maintenance/security staff | 240000 | 360000 | 480000 |
| Annual routine support | 100000 | 150000 | 200000 |
| Annual operations total | 400000 | 600000 | 800000 |
| Annual net before upfront | -437000 | -525000 | 350000 |
| Year-one net | -1037000 | -1425000 | -850000 |
| Year-one ROI | -97.83% | -89.06% | -40.48% |
| Steady-state simple payback | none | none | 3.43 years |

One-time assumed split:70% integration development,30% pilot/security/usability. Infrastructure includes PG/storage/backup; labor is in maintenance, not counted twice. Routine support excludes extra FP handling; support savings must be net of overlap. L excludes customer losses not attributable to bank and losses already prevented by current controls.

Gross benefit=N*q*d*L+support_savings. Annual net=gross-operations-FP_cost. Year-one net=annual net-upfront. ROI=year-one net/(upfront+operations+FP_cost). Payback=upfront/positive annual net, excluding discounting/ramp-up. Optimistic:1200000/350000=3.43 years,41.14 months.

Base steady-state break-even d=(600000+100000-100000)/(25000*.006*10000)=40%, against assumed5%. One extra percentage point adds15000 RUB/year. One-year recovery requires100% under these assumptions. Base does not justify rollout on losses alone; obtain evidence-backed reach/value or reduce cost. Do not manufacture ROI with optimistic inputs.

Needed: observed N/q/L, current prevention coverage, support time/cost, staff integration estimate and FP harm. Usability safe-action lift is not d. Genuine incremental monetary effect requires later bank-approved outcomes and adequate sample/duration. This is scenario arithmetic, not a forecast.
