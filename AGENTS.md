# Repository instructions for agents

## Start here

Read `ORCHESTRATION.md` before starting work. It defines the autonomous A–F team,
review gates, scope, and research-only journal. Then read the relevant sections of:

1. `docs/ROLE4_FINAL_REPORT.md`
2. `docs/research/DATA_REWARD_SPEC.md` and `data/role4_config.json`
3. `docs/research/REVIEWS.md`
4. `docs/research/RESEARCH_LOG.md`

Current reward interpretation is refined by `data/reward_contract_v2.json` and
`docs/research/REWARD_EVIDENCE_REVIEW.md`: report raw components first; the old
0.5/0.2 scalar is an uncalibrated policy baseline, not a validated recommendation.
Optional STOP and legacy forced extension are different handoff contracts. The
vector is not automatically a scalar reward usable by an existing learner.

The working repository is `hkson0826-oss/2026-2-yonsei_RL`. The original model was
provided from `Gyuhongcho/26-2-RL`; preserve its attribution and existing model
behavior. Inspect remotes before any publication. Never force-push or overwrite
unrelated remote changes.

## Authorized scope

This team handles role 4: stop inventory, morning alighting activity, directional
road costs, railway/Yonsei hub mapping, reward specifications, maps, preprocessing,
and handoff to the model and presentation owners.

- Do not implement or modify learning agents, run training, optimize routes, or
  compare algorithm performance. Existing model code may be inspected for input
  compatibility; keep it separate from new preprocessing outputs.
- Work autonomously within scope. Resolve technical decisions through evidence
  and the independent C reviewer; do not wait for ordinary user approvals.
- Reject every option requiring new expenditure. Do not ask the user to pay or
  approve costs. Use existing tools, free sources, and local computation.
- Respect unavailable permissions. Use accessible alternatives instead of trying
  to bypass access controls or creating paid/API-key dependencies.
- A assigns non-overlapping output paths. A–F are roles, not a requirement to run
  six agents simultaneously. Respect the actual concurrency limit.

## Scientific invariants

- The reference universe is **464 unique stops with official ARS district code
  13**, from the 2026-09-02 inventory. This is a dated code-based definition, not
  independently certified polygon membership or present operating status.
- The original 282-stop input is a subset, not the complete district. The
  original 808-stop study area overlaps the official reference at 292 stops.
- Six monthly sources have records for 454 stops; the same 10 have no source
  record. Missing values are `null`/blank, never zero. An observed zero is valid.
- Training months are May–August 2026 (123 calendar days). Use pooled alighting
  totals divided by days. Fix max-only scaling from all complete training records,
  including central-lane reference stops. Never refit scaling on validation months
  or on a filtered candidate set. Preserve unclipped validation values.
- Alighting activity is a historical proxy, not predicted new ridership, unique
  passengers, OD demand, or demonstrated transfer benefit.
- Hub anchors are official station reference points and Yonsei-front bus-stop
  points, not surveyed entrances. The default 300m straight-line screening and
  200/500m spatial comparisons are assumptions, not validated walking distances.
- Assign one nearest group deterministically; pay hub bonus once per group.
  Station lines sharing one hub and the two distinct Sinchon stations must not
  be confused. Keep excluded stops on the reference map.
- The 464-index road matrix contains source costs for 292 stops: 84,972 known
  off-diagonal pairs and 129,860 unknown pairs. Preserve direction, unknown `null`,
  and the flagged non-diagonal 0m source value. A diagonal 0 does not prove coverage.
- Do not fill unknown costs with straight-line distance, symmetrize costs, or
  describe source costs as verified bus-feasible roads.
- `data/routes/v1/` separately preserves 24 actual directed road observations.
  Geometry, distance, duration and weight come from the same OSRM response.
  The reported weight is `routability`: do not claim independently verified
  shortest-distance or minimum-duration paths. Time is a car-profile estimate,
  not observed peak-hour bus time. Never mix these costs into the old matrix.
- Whole-district model readiness remains **false** while required demand or road
  inputs are missing. A 259-stop diagnostic subset is not the final full-region
  experiment population. Data readiness and legal/physical drivability are separate.
- New explicit demand fields are not automatically consumed by `train.py`, which
  recomputes a different monthly-average definition. Document this incompatibility.

## Evidence, logs, and checks

Keep source provenance and versions. `docs/notion/` contains preserved source
snapshots. `docs/evidence/` contains machine-readable analysis evidence.
`docs/research/RESEARCH_LOG.md` records **research only**: questions, sources,
methods, results, interpretations, alternatives, substantive criticism, and limits.
Do not put download operations, agent allocation, waiting, tools, tokens, or routine
file edits in that journal. Correct earlier interpretations with linked follow-up
entries rather than erasing research history.

Use the current config and specifications for preprocessing. Existing reproducible
source/audit commands include:

```powershell
python scripts/audit_role4.py
python scripts/compare_role4_demand.py
python scripts/fetch_role4_ridership.py
python scripts/build_role4_roads.py
python scripts/fetch_selected_routes.py --offline
python scripts/validate_route_geometry.py
python scripts/audit_reward_tradeoffs.py
python scripts/build_role4_map.py
python -m pytest tests -q
```

Fetching ridership uses publicly downloadable monthly files; local compressed
copies are reused. Do not run `train.py` as a verification step. Follow handoff
instructions for subsequent bundle/map builds. Verify ID ordering, independent
arithmetic, missing-data behavior, hub assignment, source distances, local links,
and the actual map UI. Do not claim a C gate passed until its verdict is recorded.

## Public-repository hygiene

Publish code, research results, reproducible derived data, and source attribution.
Do not publish secrets, signed expiring URLs, browser/session state, caches, or
temporary test output. Keep third-party paper PDFs and extracted full texts local
unless redistribution permission has been verified; provide original-source links
and bibliographic metadata instead. Do not invent a license for third-party data.
