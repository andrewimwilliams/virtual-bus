# Architecture

## Goal

Provide a clear, modular architecture for **simulating, observing, normalizing, analyzing, replaying, and visualizing** CAN traffic as a time-sensitive distributed system without requiring physical CAN hardware.

This document answers:
- What components exist and why
- How data flows between them
- What interfaces and data contracts keep the system extensible

---
## High-level Data Flow

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

Key Idea:
- Raw frames and normalized signals are treated as distinct, durable artifacts.
- Normalized signals provide a semantic, timing-aware representation suitable for analysis.
- The offline workflow establishes baseline system behavior and produces versioned artifacts that are reused unchanged by the real-time analytic pipeline.

---
## Core Components

### 1) Traffic Generator (Virtual Nodes)
- The Traffic Generator simulates one or more virtual CAN nodes producing raw CAN frames according to a configurable scenario.
- It is responsible for defining message identifiers, payload patterns, transmission rates, and optional fault injection.
- The generator produces frames without interpreting their semantic meaning and does not perform any analysis.

Its sole responsibility is to **emit raw CAN frames into the Virtual CAN Bus**.

---
### 2) Virtual CAN Bus (In-Process Backend)
- The Virtual CAN Bus provides a shared communication substrate for CAN frames within the system.
- It allows multiple publishers and subscribers to interact through a common interface, modeling the broadcast nature of a real CAN bus.
- The initial implementation uses an **in-process backend** to minimize dependencies and simplify testing.
- The bus does not persist data or apply any interpretation to frames.

---
### 3) Observer (Passive Capture)
- The Observer passively subscribes to the Virtual CAN Bus and captures all CAN frames without modifying them.
- It timestamps frames (or preserves source timestamps) and forwards them downstream for storage and normalization.

The Observer does not inject traffic, influence arbitration, or alter message content, enforcing the project's passive-observation constraint.

---
### 4) Raw Frame Store
- The Raw Frame Store is a durable, append-only record of observed CAN frames.
- Frames are stored exactly as captured, along with timing and metadata, forming the system's ground truth.

The Raw Frame Store serves as:
- the input to offline analysis and training
- the source of deterministic replay
- a debugging and audit artifact

It does not perform interpretation or transformation.

---
### 5) Replayer (Deterministic)
- The Replayer consumes recorded raw frames from the Raw Frame Store and deterministically re-emits them into the pipeline.
- It preserves ordering and inter-frame timing so that replayed data is indistinguishable from live traffic to downstream components.

The Replayer functions as a **deterministic frame generator**, enabling offline runs to be processed using the same normalization and analysis logic as live data.

---
### 6) Normalizer (Frame → Signals)
- The Normalizer transforms raw CAN frames into normalized, semantic signal representations using explicit mapping definitions.
- It separates transport-level details (IDs, payload bytes) from signal-level meaning (values, units, context).
- The Normalizer is agnostic to whether frames originate from live generation or replay.
- All downstream analysis operates exclusively on normalized signals.

---
### 7) Normalized Signals
- Normalized Signals are the canonical representation used for analysis, training, and scoring.
- Each signal is time-stamped and carry explicit semantic meaning derived from raw frames.

This artifact serves as the convergence point between offline and online workflows.

---
### 8) Offline Trainer (Baseline Only)
- The Offline Trainer operates exclusively on normalized signals derived from baseline (non-anomalous) data.
- Its purpose is to learn or define what constitutes normal system behavior.
- The trainer produces versioned model artifacts, such as learned weights, thresholds, or configuration parameters.
- It does not run in real time and does not participate in live scoring.

---
### 9) Model Artifacts
- Model Artifacts are versioned outputs produced by the Offline Trainer.
- They represent learned baselines and configuration used during real-time analysis.

Model artifacts are loaded by the Analyzer at startup or configuration time and are not modified during live operation.

---
### 10) Analyzer (Rules / ML)
- The Analyzer consumes normalized signals and evaluates them against offline-derived model artifacts and rule sets.
- It detects timing anomalies, behavioral deviations, and system-level conditions.
- The Analyzer is deterministic with respect to its inputs and loaded artifacts.
- It emits structured events rather than modifying signals or frames.

The Analyzer does not learn or adapt at runtime; all learned behavior is supplied via offline-generated artifacts.

---
### 11) Event Stream
- The Event Stream is an append-only record of detected anomalies, warnings, and analysis results.
- Events are time-stamped, structured, and suitable for both live inspection and offline review.

This stream represents the primary output of the analysis pipeline.

---
### 12) Signal Storage (Optional Cache)
- Signal Storage provides optional persistence or caching of normalized signals for debugging or visualization.
- It is not required for core analysis and does not affect scoring behavior.

Its inclusion is strictly auxiliary.

---
### 13) Local Dashboard (API + UI)
- The Local Dashboard provides a local-only interface for inspecting system behavior.
- It visualizes normalized signals, analysis events, and summary metrics produced by the pipeline.

The dashboard does not perform analysis or load model artifacts directly, but functions solely as a consumer of results.

---
## Execution Modes

### Offline Workflow
The offline workflow operates on recorded raw frames and normalized signals to establish baseline system behavior.
Recorded frames are normalized, and baseline data is used to train or configure models that define normal operating conditions.
The output of this workflow is a set of versioned model artifacts that are reused unchanged during real-time analysis.

### Online (Real-Time) Workflow
The online workflow processes live or replayed frames through the same normalization and analysis components.
The Analyzer loads precomputed model artifacts and evaluates incoming signals in real time, emitting events without modifying system state or learning online.

### Replay Workflow
Replay mode re-emits recorded raw frames through the pipeline using the Replayer, preserving timing semantics.
This enables deterministic reproduction of prior runs and ensures equivalence between offline and online analysis paths.