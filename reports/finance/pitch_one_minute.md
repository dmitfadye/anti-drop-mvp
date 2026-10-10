# One minute, honestly

> MODELLED ESTIMATE, NOT MEASURED ROI. Inputs are assumptions unless marked bank_data.
> Counts only incremental prevention on top of existing bank protection; existing protection is not claimed as a benefit.
> Prevalence (q) and unit loss (L_bank) are assumptions; no bank data was available.
> RevenueUplift = 0, Rewards = 0, Inference = 0 until proven; no cashback is modelled.
> A positive payback in the optimistic scenario is not a promise, only a condition to be tested in a pilot.

Считаем только дополнительный эффект поверх текущей защиты банка: тот же перевод, который
существующий антифрод уже частично перехватывает, мы не считаем своей победой дважды.

Иллюстративная база: годовая маржа -212,500 ₽, net первого года -18,212,500 ₽, простая окупаемость не окупается.
Консервативная база: маржа -5,693,000 ₽, окупаемость не окупается.

Оптимистичная база (множители {"delta_incremental_prevention": 1.5, "false_alerts_per_client_year": 0.7, "k_initial_cost": 0.9, "l_bank_rubles_per_episode": 1.2, "n_clients": 1.2, "opex_annual": 0.9}) даёт 6,193,500 ₽ — это верхняя граница допущений, а не обещание.

Иллюстративная база **убыточна**: годовая маржа отрицательна. Это не повод прятать цифру — это точный список условий, которые пилот должен подтвердить или опровергнуть.

Что именно должен проверить пилот: Delta (дополнительный эффект), OPEX и K, долю ложных
обращений и подтверждённый охват клиентов.

Это не ROI пилота. Это условия, которые пилот должен подтвердить или опровергнуть.
