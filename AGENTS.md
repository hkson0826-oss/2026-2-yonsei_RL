# Agent instructions — Role 5: model implementation, training, and evaluation

## Current assignment and scope precedence

The next owner of this repository handles **role 5: build the model, connect the
role-4 data, run learning, and evaluate results**. Model implementation, environment
changes, training, and algorithm comparisons are authorized responsibilities of
this role when the user asks to proceed with role-5 work.

The old ban on model/training work applied to the previous role-4 data/map team.
It does **not** restrict the new role-5 owner. `ORCHESTRATION.md` is the historical
role-4 workflow: reuse its evidence-first, independent-review, free-only, and
research-only logging principles, but do not inherit its role-4-only scope or its
training prohibition. Current explicit user instructions always take precedence.

This handoff authorizes a role; it does not assert that training has already run,
that all model inputs are complete, or that the existing model implements the new
specification. Do not claim completed results without actually producing them.

Repository: `hkson0826-oss/2026-2-yonsei_RL`. Upstream model source:
`Gyuhongcho/26-2-RL`, initially inspected at `aca14c9`. Preserve attribution and
reproducible legacy behavior under a named legacy configuration or branch rather
than silently replacing its semantics.

## Read first

1. `README.md` — current artifacts and role-5 entry point.
2. `docs/ROLE4_HANDOFF.md` and `docs/ROLE4_FINAL_REPORT.md` — data contract and gaps.
3. `data/reward_contract_v2.json`, `docs/research/REWARD_EVIDENCE_REVIEW.md`,
   `docs/research/REWARD_CRITIQUE.md`, and `docs/research/CRITICAL_REVIEW_V2.md`.
4. `docs/research/DATA_REWARD_SPEC.md`, `data/role4_config.json`, and the actual
   `data/processed/role4_bundle.json` schema. The v1 scalar is a baseline only.
5. `docs/research/SELECTED_ROUTES_METHOD.md`, `data/routes/v1/manifest.json`.
6. `train.py`, `prepare.py`, `requirements.txt`, `PARALLEL_EXPERIMENTS.txt`, existing
   tests, and `docs/research/RESEARCH_LOG.md`.

## Work autonomously, with no new expenditure

- Resolve ordinary design choices from source evidence, data, and explicit model
  contracts. Record reasons and limitations instead of repeatedly asking the user.
- Reject paid APIs, new subscriptions, purchased datasets, cloud/GPU charges, and
  chargeable trials. Do not ask the user to fund them. Use an existing local CPU or
  available local GPU; inspect resources before choosing a training budget.
- Do not bypass access controls. No live public routing API calls inside training.
- Divide independent work if useful, within the actual concurrency limit: model
  coordinator, paper/method reviewer, data/environment implementer, learning-agent
  implementer, and independent experiment/reproducibility reviewer. Assign distinct
  files; a result's author must not impersonate its independent reviewer.
- Inspect Git remotes and remote updates. Preserve unrelated work; never force-push.
  Publish to the destination authorized by the user, keeping large checkpoints out
  of ordinary commits unless storage and publication are explicitly arranged.

## What exists and what remains to implement

Existing `train.py` supports Q-learning, SARSA, DQN, Random, Greedy, and small DP.
DQN needs PyTorch. MC Control is **not implemented**. Epsilon-greedy is currently an
exploration policy for learning agents, not an independent epsilon-greedy heuristic
baseline. Do not claim the requested four-way comparison exists merely because
these names appear in the project documents.

Role 5 must explicitly define the intended comparison. A defensible interpretation
is Greedy, epsilon-greedy heuristic, DQN with exploration, and MC Control with
exploration; retain existing Q-learning/SARSA/Random/DP as clearly named optional
controls when useful. Do not confuse MC Control, random Monte Carlo route sampling,
and MCTS. Consult the supplied course notes/source documentation where available.

The existing model is a starting point, not a finished implementation of role 4's
new input contract:

- `train.py` defaults to the old 282-stop `network.json` and hub bonus **2**.
- It recomputes an equal mean of monthly daily demand, rather than pooled totals
  divided by 123 days, and does not consume `demand_score_train` automatically.
- Its stop fields (`id`, `hub`) differ from the new fields (`station_id`, `hub_id`).
- It assumes numeric distances; do not feed a null-containing matrix straight in.
- It has no STOP action and extends a route until no valid next move remains.
- Its training winner includes exploratory discoveries. It is not an independent
  evaluation of a frozen learned policy.

## Data facts and experiment readiness gates

- Reference universe: **464 unique official ARS district-code-13 stops**, inventory
  dated 2026-09-02. Code membership is not polygon or current-operation certification.
- Six months have records for 454 stops; the same 10 have no source record. Preserve
  `null` versus observed zero. Do not invent zero demand, zero distance, or straight-
  line replacement costs to make a model run.
- Training data: May–August 2026, 123 calendar days. Use the supplied pooled daily
  demand and the fixed max-only scale from all complete training records, including
  central-lane references. Do not refit on validation months or candidate filters.
- Validation: September–October. If used to tune settings, do not call it a final
  independent test. The inventory and monthly sources are a retrospective snapshot.
- Historical alighting activity is not new ridership, unique passengers, OD, or
  demonstrated transfer benefit. Hub 300m screening is not verified walking access.
- Source road data covers 292 stops: 84,972 observed directed off-diagonal pairs;
  129,860 pairs in the 464-index matrix remain unknown. Direction matters. The
  source's flagged non-diagonal 0m must be handled explicitly, not silently edited.
- The 259-stop noncentral/observed/road-covered subset is diagnostic. It may support
  a declared partial-data experiment, but it is not the complete district or a
  substitute silently satisfying the user's full-region objective. Do not shrink
  the final question to 20–30 stops to obtain convenient results.
- `data/routes/v1/` has **24 actual directed road geometries**, not a complete road
  graph. They use a separate OSRM car-profile source and `routability` weighting.
  Preserve same-response geometry/distance/duration, cache hashes, quality flags,
  and unknown provider data version. Do not mix them into the old matrix unnoticed.
- Router time is a car-profile estimate, not 07–09 bus time or dwell time. Neither
  legal bus drivability nor minimum-distance/minimum-duration paths are certified.

**First gate:** choose and record an experiment scope, versioned stop IDs, demand,
known directed costs, candidate policy, and missing-data treatment. A full-district
run requires the necessary full-domain inputs; acquire consistent free data or
report that gate as not met. A declared partial experiment can proceed separately.
Unknown edges may be outside a declared observed-edge experiment's action set,
but this is a change in the modeled graph, not proof of physical inaccessibility.
Keep `full_district_model_ready=false` until the actual requirements are satisfied.

## Model/environment contract to settle before substantial learning

1. Define state, action, transition, valid-action masks, budget, start set, terminal
   behavior, visited IDs, hub groups, and units. Include any varying task/goal/demand
   context necessary for the state to determine future rewards and feasible moves.
2. Write an explicit input adapter consuming the new IDs, fixed demand scores,
   group mapping, and missing-data flags. Preserve the source bundle; emit a
   versioned experiment input/config with hashes, not an unexplained overwrite.
3. Use raw activity, new hub groups, distance, optional profile time, stop count,
   coverage, and quality as reporting components. The vector is **not automatically
   a scalar DQN reward**. Declare scalarization or constraints and their rationale.
4. The `activity + 0.5*new_groups - 0.2*km` scalar is an **uncalibrated policy
   baseline**. Bonus 0.5 equals roughly 32 median eligible-stop scores or 2.5km.
   Do not call it paper-calibrated, demand-balanced, or optimal. Sensitivity and
   alternative-objective comparisons are now role-5 work; compare raw components
   as well as scores, especially when the score weights themselves differ.
5. Explicitly choose optional STOP, a fixed goal, or forced extension. Optional STOP
   can make an empty route optimal when all continuations are negative. A useful
   nontrivial bus service may require separately justified constraints; do not
   invent a minimum-stop count and present it as an empirical fact.
6. Mask invalid/unknown actions consistently in behavior and bootstrap targets;
   terminal continuation value is zero. Verify all-invalid masks, no repeated stop,
   group-first reward, nulls, source 0m, budget boundaries, and start/goal inclusion.
7. New durations do not automatically justify an extra time penalty. Avoid silently
   double-charging correlated distance/time or pretending absent dwell-time data.

## Implementation and experiment sequence

1. Reproduce data checks and inspect compute/software availability.
2. Build the explicit input/environment adapter and meaningful boundary checks.
3. On a tiny synthetic problem, compare an independent enumeration/DP result with
   the environment's arithmetic. This is a correctness check, not district optimum.
4. Implement missing methods and verify a short learning smoke run. Use separate
   output directories and a bounded initial budget; do not launch a large sweep
   before the environment and learning updates are demonstrably correct.
5. Freeze a comparison protocol: same graph/data/reward/constraints/start evaluation
   set; learning methods get comparable transition budgets and declared seeds.
   Record wall time and memory too; equal steps do not mean equal compute cost.
6. Save checkpoints/configs, then evaluate a **frozen** policy with exploration off
   where appropriate. Keep training return, best discovered route, and evaluation
   performance separate. For stochastic baselines, report repeated-generation
   variation separately from learning-seed variation. Do not infer convergence or
   superiority from a single lucky route or a single seed.
7. Re-score frozen training-selected routes on later months with the training scale
   fixed. Separate tuning, validation, and any genuinely held-out final assessment.
8. Report raw components, reward, route validity, seed variation, learning curves,
   cost/coverage/source limitations, and reproducible commands. Do not claim a
   global optimum unless computed in the exact same finite problem.

Useful existing checks (not training):

```powershell
python -m pip install -r requirements-research.txt
python -m pytest tests -q
python scripts/validate_route_geometry.py
python scripts/audit_reward_tradeoffs.py
```

An optional **legacy-only** smoke example after inspecting the environment is:

```powershell
python train.py --algo q-learning --steps 1000 --bonus 0.5 --no-viewer --out runs/role5/legacy-smoke
```

That command uses old data/semantics; it does **not** validate the new adapter or
full-region experiment. Do not label 1,000 DQN steps as successful learning merely
because the replay warm-up completed. Determine adequate training from actual
updates, evaluation behavior, and available local resources. Install/use PyTorch
only in the selected environment; do not assume CUDA is available.

## Research records and final handoff

Append research content to `docs/research/RESEARCH_LOG.md`. A separate role-5
experiment protocol/report may be created under `docs/research/`. Preserve earlier
observations and supersede them explicitly when new evidence changes a conclusion.
Record hypotheses, source justification, dataset/config/code hashes, seeds, actual
budgets and model settings, results, uncertainty, substantive critiques, failures
that affect inference, and limitations. These are research methods/results.
Do not log agent allocation, waiting, token counts, download operations, or routine
Git/file administration as research.

Store run-specific traces/checkpoints in separate `runs/role5/` directories (ignored
by default). Publish small configs, metrics, commands, and research conclusions
with a clear artifact manifest; arrange any large-model sharing explicitly. Do not
publish secrets, session state, signed URLs, or paper full texts without verified
redistribution rights. Keep source attribution and immutable input snapshots.

Completion means the declared role-5 model and experiments actually run, results
are independently evaluated and reproducible, and data/compute limits are honestly
reported. Updating these instructions alone is not completion of role-5 research.
