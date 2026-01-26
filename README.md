# Virtual Bus
A small, deterministic framework for **simulating, recording, replaying, and analyzing CAN-style bus traffic** without physical CAN hardware.

This project treats CAN traffic as a **time-sensitive distributed system** rather than a collection of individual frames. The focus is on observability, reproducibility, and system-level behavior.

---
## What this project does
- Simulates CAN traffic using virtual nodes
- Passively observes and records raw frames (`frames.jsonl`)
- Normalizes frames into semantic, time-stamped signals (`signals.jsonl`)
- Analyzes signal timing and behavior to emit structured events (`events.jsonl`)
- Replays recorded traffic deterministically with preserved timing
- Supports offline analysis and regression-style testing

All data flows through the same pipeline whether it originates from live simulation or deterministic replay.

---
## What this project is *not*
- No physical CAN hardware
- No real vehicle or production deployment
- No vendor-locked tooling or proprietary formats
- No runtime learning or adaptive models

This is an **exploration and analysis tool**, not a drop-in replacement for commercial CAN stacks.

---
## High-level Data Flow
```
                                 ┌─────────────────────────┐
                                 │    Traffic Generator    │
                                 │   (Virtual CAN Nodes)   │
                                 └───────────┬─────────────┘
                                             │
                                             v
                                 ┌─────────────────────────┐
                                 │     Virtual CAN Bus     │
                                 │   (in-process backend)  │
                                 └───────────┬─────────────┘
                                             │
                                             v
                                 ┌─────────────────────────┐
                                 │        Observer         │
                                 │   (passive capture)     │
                                 └───────────┬─────────────┘
                                             │
              ┌──────────────────────────────┤
              │                              │     
              v                              v      
    ┌─────────────────────┐        ┌─────────────────────┐   
    │   Raw Frame Store   │   ┌───►│      Normalizer     │   
    │   (frames.jsonl)    │   │    │  (frame → signals)  │  
    └─────────┬───────────┘   │    └─────────┬───────────┘  
              │               │              │
              v               │              │    
    ┌─────────────────────┐   │              │ 
    │      Replayer       │   │              │ 
    │   (deterministic)   ├───┘              │
    └─────────────────────┘                  v
                                ┌─────────────────────────┐           
                                │   Normalized Signals    │
                                │    (signals.jsonl)      │
                                └────────────┬────────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────┐
              │                              │                      │
              v                              v                      v
    ┌─────────────────────┐         ┌──────────────────┐    ┌──────────────────┐
    │   Offline Trainer   │   ┌────►│    Analyzer      │    │  Signal Storage  │
    │   (baseline only)   │   │     │   (rules / ML)   │    │ (optional cache) │
    └─────────┬───────────┘   │     └────────┬─────────┘    └──────────────────┘
              │               │              │
              v               │              v
    ┌─────────────────────┐   │   ┌─────────────────────────┐
    │   Model Artifacts   │   │   │      Event Stream       │
    │  (weights, thresh)  ├───┘   │    (events.jsonl)       │
    └─────────────────────┘       └──────────┬──────────────┘
                                             │
                                             v
                                  ┌─────────────────────────┐
                                  │     Local Dashboard     │
                                  │       (API + UI)        │
                                  └─────────────────────────┘
```
Raw frames are treated as ground truth. Everything downstream is deterministic with respect to those frames.

---
## Quick Start

### Requirements
- Python 3.11+

### Run a demo session
```bash
python -m scripts.run_demo
```
This generates:
- `artifacts/frames.jsonl`
- `artifacts/signals.jsonl`
- `artifacts/events.jsonl`

### Replay a recorded session
```bash
python -m scripts.replay_demo
```
Replay preserves frame ordering and inter-frame timing, allowing offline analysis using the same pipeline.

---
## Testing
This project uses **unit tests + golden end-to-end tests** to lock in behavior.
```bash
pytest -q
```
Golden tests assert that a known input recording produces exactly the same signals and events.
Fixtures live in `tests/fixtures`.

---
## Design principles
- Deterministic behavior over realism
- Explicit data contracts over hidden logic
- Passive observation over control
- Reproducibility over performance

---

## Status
Active development. Core pipeline, replay, and testing infrastructure are in place. Analysis rules and visualization will continue to evolve.
See `docs/` for more details.