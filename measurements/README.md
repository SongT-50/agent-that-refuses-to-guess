# measurements/ — every number in the main README, and how to reproduce it

These are not part of the shipped agent. They are the scripts that produced the claims, kept in the
repo so the claims can be checked rather than believed.

Run from this folder: `../.venv/bin/python <script>.py` (they add the parent directory to
`sys.path` themselves).

## What proves what

| Script | Question it answers | Result |
|---|---|---|
| `_check_truncation.py` | How much of a day does one page of the API give us? | `totalCount` **129,536** vs **1,000** fetched = **0.77%** |
| `_check_page1_bias.py` | Is that 0.77% a fair sample? | **No.** 6 markets of 33, one market is 64.3%, **Seoul Garak absent** |
| `measure_unit_effect.py` | Does ignoring package size change who ranks first? | Fetches full days (~4 min/day, caches), then compares |
| `measure_decompose.py` | Which fix does the work — unit normalization or outlier handling? | Unit **9/16** · outlier **6/16** · together **10/16** |
| `measure_spread.py` | How far apart are markets on the same day? | n=16 · min **45%** · median **207%** · max **5500%** |
| `_check_variety_mix.py` | Does a product keyword pull in other crops? | It did — `배추` was catching cabbage, broccoli, cauliflower |
| `_check_cabbage.py` | Why was one spread 5500%? | Retail 1 kg bags vs 12 kg bulk boxes. Both real, not comparable |
| `_check_match.py` | Is the product filter matching what we think? | Confirms exact-match behaviour and shows outliers |

## Model-behaviour probes

| Script | Question | Result |
|---|---|---|
| `_diag_toolcall.py` | Why did the tool call leak as text? | First answer (prompt language) was **wrong** — see next row |
| `_diag_repeat.py` | Same conditions, 6 runs each | Korean **5/6** · English **6/6** — language is not the switch |
| `_diag_callback.py` | Then what is? | Default streaming handler **2/6** vs `callback_handler=None` **5/6** |
| `_diag_korean_quality.py` | Does the model mangle Korean **when it writes freely**? | **Yes — ~2 of 6.** This measures the model's raw text, which `agent.py` does not print |
| `_diag_hallucination.py` | Does it invent markets and prices when refusing? | Before/after the fixes: price citations **4/6 → 1/6** |
| `_diag_scene3.py` | Does it invent numbers from the refusal headline? | After removing digits from the copied line: **0/6** |
| `_diag_demo_reliability.py` | The **shipped interface**, three scenes × 4 runs | **12 of 12** expected verdicts, no foreign script |
| `_diag_retry_budget.py` · `_diag_retry_5.py` | How often does the retry budget run out? | retries=2 → **2 of 15** gave up · retries=5 → **0 of 15**, median attempts still 1 |
| `_diag_demo_walltime.py` | How long does the 3-scene demo actually take? | **92 s to 209 s** (n=2). Attempt count is usually 1; wall-clock is not |
| `_diag_walltime_cause.py` | Was the slow run caused by the bigger retry budget? | **No.** Same scene, budgets 2 vs 5 interleaved: mean **34 s vs 26 s**, failures **1/3 vs 0/3** |
| `_try_tools.py` | Raw tool output for both paths, no model involved | — |

### ⚠️ Attempt count and wall-clock are different axes

We raised the retry budget and reported *"median attempts is still 1, so it does not get slower."*
That is true of **attempts**. Wall-clock told another story: the same three scenes ran in **92 s**
once and **209 s** the next time, with per-scene times from **23 s to 102 s**.

Nothing was wrong with the retry change. What was wrong was answering a wall-clock question with an
attempt-count measurement — and it mattered, because someone was about to plan a five-minute video
around the faster figure.

We then said we could not tell whether the slow run came from the retry budget or from load on the
machine, and left it open. Leaving it open would have been easy; instead we interleaved the two
budgets on the same scene. The bigger budget was **not** slower — mean 26 s against 34 s — and it
failed 0 of 3 where the smaller one failed 1 of 3. The variance is the model's, not the budget's.
That is worth knowing, because the obvious next move would have been to undo a change that was
helping.

### 🔴 Two of these measure different paths — do not merge them

`_diag_korean_quality` (**~2 of 6 garbled**) reads the **model's own text**.
`_diag_demo_reliability` (**0 of 12**) reads the **shipped interface**, where the answer line is
written by code.

Both numbers are real. The garbling was not solved — it is **not displayed**. `agent.py` prints the
model's text only behind `SHOW_MODEL_TEXT=1`, and `test_tools.py` holds that default in place. If
someone re-enables it, the broken Korean comes back to the screen.

We keep both figures because quoting only the 0/12 would claim a fix we did not make.

## ⚠️ Read these with the limits attached

- Sample sizes are small (**n = 16** date × product pairs, **n = 6** model runs). We say *"often"*
  and *"most runs"*, not percentages presented as rates.
- Full-day caches cover **2 days** (2026-08-27, 08-28). Products were chosen by us.
- The market-bias result is **one day**. We did not test whether the ordering is stable.
- Model probes are `llama3.2:3b` on one machine. Other models were not measured.

Several of these scripts exist because an earlier measurement of ours was wrong — a truncated
sample, a checker that counted errors as successes, a single run reported as a characteristic. The
corrections are in the git history rather than hidden.
