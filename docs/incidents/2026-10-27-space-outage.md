# 2026-10-27: the live Space is not scheduled on ZeroGPU

Analysis of the outage tracked on [#252](https://github.com/miravena/foreveryours/issues/252); the hosting decision it feeds is
[#253](https://github.com/miravena/foreveryours/issues/253). This file is the analysis only. The live state (up, down,
restarted, decided) stays on those Issues.

Evidence levels used below:

- **Proven**: read directly from an API response, a workflow log or a Hugging Face page, cited.
- **Likely**: the best reading of the evidence, with a named gap.
- **Unknown**: not settled by anything we can read; says what would settle it.

All Hugging Face pages were read on 2026-10-27. The doc pages are cited by their published URL;
their source and edit history are in
[huggingface/hub-docs](https://github.com/huggingface/hub-docs/tree/main/docs/hub).

## What happened

The judge demo runs as the Gradio Space `elevenbaselab/foreveryours`. The account is a free
personal account (`isPro: false`, `canPay: false` from the Hub's `whoami-v2` endpoint, created
2026-05-23, email verified). Hugging Face requires a paid plan for a Gradio Space on `cpu-basic`,
so the CPU-only app runs on ZeroGPU (`zero-a10g`) with one never-called `@spaces.GPU` function
([ADR-003](../decisions/ADR-003-hosting.md), `scripts/deploy_hf_space.py`).

Every push to `main` runs `.github/workflows/deploy-space.yml`: tests, upload, then
`scripts/verify_space_sha.py --wait 900`, which fails if the new build is not `RUNNING` within
15 minutes, then the live judge check suite.

From the deploy at 00:15 UTC on 2026-10-27 onward the Space never got a machine. The runtime API
reports `stage: APP_STARTING` (at times `RUNTIME_ERROR`), `hardware.current: null`,
`hardware.requested: zero-a10g`; the container log shows `===== Application Startup =====` and
nothing after it, so no app code ran.

## Timeline (UTC, 2026-10-26 to 2026-10-27)

| Time | Event | Source |
|---|---|---|
| 10-26 21:43 | Deploy of `5600d83` does not reach `RUNNING` in 900 s. Stage stays `RUNNING_APP_STARTING`, so the previous build kept serving. | run 40406172300 |
| 10-26 22:11 | Next deploy (`ed85efc`) reaches `RUNNING`, 18 endpoints reachable. | run 40407255344 |
| 10-26 23:20 | Last good deploy: `f768c65`, `RUNNING`, judge check passed. | run 40417425502 |
| 10-27 00:15 | Deploy of `c6ec874` (no app code changed) uploads the same 33 staged files as `f768c65`. | run 40425050109 |
| 10-27 00:30 | Fails "not RUNNING after 900s", last stage `RUNNING_APP_STARTING`: the `f768c65` container is still serving at this point. | run 40425050109 |
| 10-27 00:00 to 03:05 | Across Hugging Face, dozens of other ZeroGPU Spaces fail with `Scheduling failure: unable to schedule` (see Root cause). | runtime API sample |
| 10-27 00:40 | Another user reports the same symptom on the Hugging Face forum (ZeroGPU Space, `zero-a10g`, stuck in `APP_STARTING` after a push, factory reboot does not help). | [forum 191049](https://discuss.huggingface.co/t/191049) |
| 10-27 02:16 | Next deploy starts; the Space is already `RUNTIME_ERROR` with no hardware, so the old container is gone by now. The judge-visible outage began between 00:30 and 02:16; the exact minute is not recorded. | run 40437312002 |
| 10-27 02:31 | `3bae0bc` deploy fails the same way (last stage `APP_STARTING`). | run 40437312002 |
| 10-27 02:48 | `4d7920d` deploy fails the same way; a factory restart follows and does not help. | run 40438609712, #252 |
| 10-27 03:04 | The public URL times out (no HTTP response in 30 s); runtime `APP_STARTING`, `hardware.current: null`. | probe, runtime API |

## Is this the first outage?

**Yes, for judge-visible downtime** (proven for the checks we have). The Space was created on
2026-10-21 at 17:29 UTC and had no recorded downtime until 2026-10-27:

- A keep-awake request from an always-on machine (ADR-003, twice a day at 03:23 and 15:23 UTC)
  got HTTP 200 on all 11 checks from 2026-10-21 17:31 to 2026-10-26 15:23 (0.27 to 0.41 s).
- All 22 runs of `deploy-space.yml` (2026-10-22 to 2026-10-27), by the step that failed:

| Outcome | Runs | What it means |
|---|---|---|
| Success | 4 | Space up, judge check passed |
| Failed at "Live judge check suite" | 13 | Space up and serving; a judge turn's reply missed an assertion (app behaviour, for example a memo recall), not availability |
| Failed at "Wait for the new build" (not `RUNNING` after 900 s) | 4 | Space did not come up: 1 on 2026-10-26 21:43, 3 since 2026-10-27 00:15 |
| Cancelled | 1 | Superseded by a newer push in the same concurrency group |

So 17 of the first 18 deploys reached `RUNNING`; the 4 that did not are all within the last 30
hours.

| # | Start (UTC) | End (UTC) | Duration | Judge-visible? | Cause |
|---|---|---|---|---|---|
| 0 | 2026-10-20 | 2026-10-21 17:29 | about 1 day | No (the Space did not exist yet) | Creating the Space on `cpu-basic` from a free account returned 403 "cpu-basic quota limit"; fixed by deploying to ZeroGPU (PR #172, ADR-003). A launch blocker, not an outage. |
| 1 | 2026-10-26 21:43 | 2026-10-26 22:11 | about 28 min | No evidence of it: the previous build kept serving (`RUNNING_APP_STARTING`) | New build not scheduled within 15 min; the next deploy came up. First sign of slow ZeroGPU scheduling. |
| 2 | 2026-10-27, between 00:30 and 02:16 (deploy started 00:15) | ongoing at the time of writing | ongoing | Yes | ZeroGPU does not schedule the Space (root cause below). |

## Root cause

**Proven: the Space never gets a machine.** `hardware.current` stays `null` while
`hardware.requested` is `zero-a10g`, and the log stops at the startup banner. That is a
scheduling failure, not an app crash: an app fault would show our Python startup output or a
traceback, and the staged files of the first failing deploy equal those of the last good one.

**Proven: it is not specific to this Space or this account.** A sample taken at about 03:05 UTC
of the 400 most recently modified public Spaces found 66 on ZeroGPU modified since 00:00 UTC
(owner tier from each user's public overview endpoint):

| Owner | Got hardware (`RUNNING*`) | No hardware (`APP_STARTING` with none, or "unable to schedule") | Other errors (config, build, code) |
|---|---|---|---|
| Free personal (53) | 11 | 37 (30 of them `Scheduling failure: unable to schedule`) | 5 |
| PRO personal (12) | 5 | 6 (2 "unable to schedule") | 1 |
| Organisation (1) | 1 | 0 | 0 |

This is a point-in-time snapshot of a small sample, not a measured failure rate. The forum
report at 00:40 UTC ([191049](https://discuss.huggingface.co/t/191049)) is a free-account
`zero-a10g` Space whose runtime shows the same `RUNTIME_ERROR` / `Scheduling failure: unable to
schedule`. The [status page](https://status.huggingface.co) said "All services are online" at
03:02 UTC; it listed "Some GPU Jobs and Spaces failing to start" on 2026-09-24 and 09-25.

**Likely: a ZeroGPU capacity or scheduler problem on Hugging Face's side, starting around 00:00
UTC on 2026-10-27, that hits free accounts hardest but not only them.** Gap: Hugging Face has
not acknowledged it, and we cannot see the scheduler.

**Hypothesis checked: "free accounts can no longer host or re-schedule ZeroGPU Spaces, so any
redeploy loses hardware". Disproven as a policy, as far as published evidence goes.**

- The docs still say free personal accounts in good standing (verified email, older than 30
  days) can host up to 2 ZeroGPU Spaces
  ([ZeroGPU, "Hosting Limitations"](https://huggingface.co/docs/hub/spaces-zerogpu);
  [Spaces overview](https://huggingface.co/docs/hub/spaces-overview): "Free personal accounts in
  good standing can still host up to 2 Gradio Spaces running on ZeroGPU"). That wording came in
  with the paid-plan change of 2026-07-21 (hub-docs #2624) and is unchanged in the latest edits
  of these pages (2026-09-07 and 2026-10-22). This account qualifies (created 2026-05-23,
  verified, 1 Space).
- The line "creating a new Space that runs on compute (Gradio or Docker) requires a paid plan"
  ([GPU Spaces](https://huggingface.co/docs/hub/spaces-gpus)) is about `cpu-basic` and paid
  hardware, with the ZeroGPU exception stated on the overview page.
- 11 free-account ZeroGPU Spaces in the sample were scheduled during the outage window, so free
  accounts can still get ZeroGPU hardware.
- Counter-signal, **unknown** weight: a forum thread from 2026-10-23
  ([190930](https://discuss.huggingface.co/t/190930)) reports a 31-day-old verified free account
  that was not offered Gradio or ZeroGPU when creating a Space. That concerns creating a new
  Space; it may mean the free tier is being applied more tightly than documented.

**Contributing factors (proven):**

- **Every push to `main` redeploys.** `deploy-space.yml` has no `paths` filter, so a docs-only or
  video-only merge restarts the Space and sends it back into scheduling. The 00:15 trigger was a
  demo-video merge; the 02:14 and 02:28 deploys were pushed while the Space was already down.
- **A failed deploy is not rolled back.** While the new build waits for hardware the old one
  serves (`RUNNING_APP_STARTING`), but the old container was gone within two hours, and a further
  push or restart replaces the pending build again.
- **The `@spaces.GPU` marker is a workaround.** ZeroGPU is meant for GPU apps; our CPU app sits in
  the GPU queue only to qualify for free hosting (ADR-003 says so). Not a cause here, since other
  GPU apps failed the same way, but it ties the demo to the pool that is failing.
- **Free hardware has no SLA.** Billing is per minute only for upgraded hardware, which "runs
  indefinitely by default"; free hardware is "suspended automatically if not used for an extended
  period" ([GPU Spaces, Billing](https://huggingface.co/docs/hub/spaces-gpus#billing)).
- **No alert.** The keep-awake request logs status codes twice a day but alerts nobody; this
  outage was noticed from the deploy failures.

## The three questions on #253

1. **Can a free account still host a Gradio Space on ZeroGPU?** Yes per the docs (cited above),
   and 11 free-account ZeroGPU Spaces were scheduled during the outage. Proven as documented
   policy; the forum report on new-Space creation keeps "is it being tightened?" unknown. It is
   **not** the root cause of this outage: PRO-owned ZeroGPU Spaces failed to schedule in the same
   window.
2. **Does `cpu-upgrade` need PRO, or only a payment method?**
   - A payment method: **proven** required. "Hugging Face compute services are paid by credit
     card" ([Billing](https://huggingface.co/docs/hub/billing)), and this account has
     `canPay: false` today.
   - PRO: **unknown**. The docs gate *creating* a Gradio Space on compute behind a paid plan; they
     do not say whether an existing Space created under the ZeroGPU exception can be switched to
     paid hardware by a free account with a card. Settled only by trying it in the Space's
     Settings after adding a card. PRO removes the question.
3. **Is `cpu-basic` (2 vCPU) fast enough?** **Unknown.** The ADR-003 timings (1.9 to 6.4 s a
   turn) were taken on ZeroGPU, whose CPU allocation is not documented ("dynamic" on the
   [pricing page](https://huggingface.co/pricing)). The concurrency limit of 4 already assumes
   2 vCPU. Settled by one live judge check run after the switch.

## Options through 2026-12-15

Prices from [huggingface.co/pricing](https://huggingface.co/pricing),
[GPU Spaces](https://huggingface.co/docs/hub/spaces-gpus) and
[nebius.com/prices](https://nebius.com/prices), read 2026-10-27. Hours: 2026-10-27 to 2026-12-15
is 49 days, 1,176 hours. Every paid option needs a credit card on the account first.

| Option | Price | Through 2026-12-15 | Reliability for judges | Effort | Notes |
|---|---|---|---|---|---|
| (a) Wait and retry on free ZeroGPU | $0 | $0 | Lowest: no SLA, outage ongoing, any redeploy re-enters the failing queue | none | What failed. PRO does not fix ZeroGPU scheduling either (PRO Spaces failed in the sample). |
| (b) HF PRO, same Space on `cpu-basic` | $9/month | $18 (2 billing months) | Good: leaves the GPU pool; same URL; sleeps after 48 h idle, which the keep-awake covers | 10 min: subscribe, set hardware, one deploy with `--hardware cpu-basic` | PRO also brings the [documented](https://huggingface.co/docs/hub/billing) monthly compute credits and Dev Mode. |
| (c) `cpu-upgrade` (8 vCPU, 32 GB), always on | $0.03/hour | about $35, plus $18 if PRO is needed (question 2), so $35 to $53 | Best on HF: paid hardware never sleeps by default | same as (b) | 4x the CPU of `cpu-basic`. |
| (c') `cpu-upgrade` with a sleep time | $0.03/hour awake | a few dollars; depends on traffic | Worse than (c): the first judge after a sleep waits on a cold start (model download) | same | The keep-awake would wake it twice a day and cancel most of the saving. |
| (d) Team organisation | $20/user/month | $40 for one user | Same as (b) | Moves the Space to an organisation, which changes the URL already submitted | No advantage over (b) for one Space. |
| (e) Second host outside HF (Nebius AI Cloud CPU VM, or any small VM) | Nebius CPU-only VMs "from $0.06" per hour; a small VM elsewhere is typically $5 to $10 a month | about $70 on Nebius at the lowest listed rate; less elsewhere | Independent of HF; only useful as a backup link | 2 to 4 hours: container, HTTPS, Nebius secret, keep it patched until 12-15 | Nebius AI Cloud is named in the rules, so it fits the "runs on Nebius" story. The submitted link stays the HF one. |
| (f) Process fixes | $0 | $0 | Fewer self-inflicted re-schedules; faster detection | small PRs | See below. |

Process fixes (f):

1. `paths-ignore` on the push trigger of `deploy-space.yml` (`docs/**`, `**/*.md`, `video/**`) so
   a docs or video merge does not restart the Space. Proposed as its own PR.
2. Keep the old Space serving until the new one is up: deploy to a second, staging Space first
   and promote only after its checks pass. On a free account this uses the second ZeroGPU slot
   and inherits the same scheduling risk; worth it only together with paid hardware.
3. An uptime monitor that alerts a person when the public URL fails, instead of only logging
   status codes twice a day. The freeze after 2026-10-30 17:00 UTC (ADR-015) already stops
   automatic redeploys during judging, so after that date the remaining risk is the Space losing
   its machine without a deploy.

## Recommendation

- **Primary: (b) HF PRO on the account and the same Space on `cpu-basic`, about $18.** It takes
  the demo out of the ZeroGPU pool that is failing, keeps the submitted URL, removes the dummy
  GPU marker from the critical path, and is the fallback ADR-003 already named. Confirm question 3
  with one live judge check run after the switch.
- **Fallback: (c) `cpu-upgrade`, about $35 more, if `cpu-basic` is too slow or will not schedule.**
  Same Space, same URL, no sleep. Only after both fail is (e) worth the hours.
- Land the `paths-ignore` change and an alerting uptime check regardless of the choice.

## Follow-ups

- Record the decision in an ADR that supersedes ADR-003's hosting choice (#253).
- Drop `zero-a10g` and the `spaces` requirement from the deploy once the Space is off ZeroGPU.
- Add the alerting uptime check through 2026-12-15.
- Re-check the ZeroGPU and Spaces overview pages before judging starts in case the free tier
  changes.
