# AU-S6 — живая проверка оставшихся звуков (2026-10-06)

Сценарий `tools/s09/run-combat-demo.ps1 -JoinerAttack -HostPlanOverride 'attack+defend+feint+slowdefense+ownresult'
-JoinPlanOverride 'attack+abilityboost+scheme+storms+defend+resolve'`, Marmoreal и Sarpedon original, громкость 100,
запись микса. Итог и разбор — [07-production-log.md §10](../../../audio/07-production-log.md).

- `*-host.trace.log`, `*-joiner.trace.log` — трассы клиентов: строки `AUDIO attack`, `AUDIO combat`,
  `CUE sound id=CUE-014 … SW_FX_ARTHUR_BOOST_*`, `SFX bank=BRD-PUSH`, `SFX bank=UI-TIMER-*`.
- `check-trace.txt` — гейт звука: PASS на четырёх трассах.
- `sarpedon-host-no-defense.png` — кадр сценария: реальная карта, фигуры v2.
