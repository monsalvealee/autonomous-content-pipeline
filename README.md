# Autonomous Content Generation Pipeline

**An eight-agent system that researches, scripts, narrates, assembles and publishes video content end to end — with an automated quality gate that blocks non-compliant output before it ships.**

No manual editing step. No human in the loop after configuration.

---

## The problem this solves

Producing video content at any volume means a chain of manual handoffs: finding a topic, writing a script, recording narration, sourcing footage, editing, designing a thumbnail, uploading, then checking whether the result actually complies with platform policy.

Each handoff is a place where the process stalls. This system removes all of them, and adds the step that manual workflows usually skip: an explicit compliance check before anything goes live.

---

## Architecture

Eight specialized agents, coordinated by a scheduler. Each writes its output to disk independently, so the pipeline is resumable — a failure at assembly does not cost you the research and scripting that came before it.

| Agent | Responsibility |
|---|---|
| `TrendAgent` | Detects current topics from live sources |
| `ScriptAgent` | Generates the script from the selected topic |
| `VoiceAgent` | Synthesizes narration using a locally hosted TTS model |
| `VisualAgent` | Sources and assembles footage to match the script |
| `ThumbAgent` | Generates thumbnails programmatically |
| `QualityGateAgent` | Scores the finished artifact PASS / REVIEW / BLOCK against policy rules |
| `PublishAgent` | Uploads and schedules approved output |
| `FeedbackAgent` | Collects post-publication performance data back into the loop |

### The quality gate

`QualityGateAgent` is the design decision worth pointing at. Every finished artifact is evaluated against policy rules before publication and assigned one of three outcomes:

- **PASS** — published automatically
- **REVIEW** — held for inspection
- **BLOCK** — rejected, with the failing rule recorded

Nothing reaches publication without passing this stage. It is a pre-release check, not a post-hoc audit — the difference between preventing a compliance problem and discovering one.

---

## Design decisions

**Locally hosted TTS instead of a paid API.** Narration is the highest-volume API call in the pipeline. Running the model locally keeps marginal cost per asset near zero, which is what makes continuous operation viable rather than an expense that scales with output.

**Disk-backed state at every stage.** Each agent's output is persisted before the next one starts. Runs are resumable, and any stage can be inspected or replayed in isolation during debugging.

**Scheduler-driven, not event-driven.** The pipeline runs on a fixed cadence. Simpler to reason about, simpler to recover, and appropriate for a workload with no real-time requirement.

**Mobile-first web control panel over a native app.** Configuration and monitoring happen through a responsive web panel reachable over a private network, rather than a native mobile client. One codebase, no app distribution, same result.

---

## Stack

Python · LLM APIs · locally hosted TTS · FFmpeg / MoviePy · YouTube Data API v3 · cron scheduling
