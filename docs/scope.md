# Project Scope

## Purpose of This Document

This document defines the **intended scope and boundaries** of the Virtual Bus project.
Its purpose is to clarify what the project **does**, what it **explicitly does not attempt to do**, and the **tradeoffs** made in service of clarity, reproducibility, and system-level analysis.

Establishing these boundaries early is intentional and serves to prevent scope creep, misinterpretation, and overextension beyond the project's stated goals.

---

## In-Scope Functionality

The project focuses on the following core capabilities:

### 1. Virtual CAN Bus Simulation
- Software-based simulation of CAN traffic
- Support for multiple virtual nodes publishing frames
- Configurable message identifiers, payloads, and timing behavior
- Fault injection capabilities such as:
    - dropped frames
    - timing jitter
    - burst traffic
    - priority contention

### 2. Passive Observation
- Observer components that monitor traffic without modifying it
- No message injection, suppression, or arbitration control
- Observation designed to mirror real-world monitoring constraints

### 3. Frame Normalization
- Transformation of raw CAN frames into normalized, semantic representations
- Explicit separation between:
    - transport-level data (IDs, payloads)
    - signal-level meaning (values, units, context)
- Schema-driven normalization to ensure transparency and consistency

### 4. Timing-Aware Analysis
- Analysis of:
    - message frequency
    - inter-arrival timing
    - deadline adherence
    - jitter and burst behavior
- Detection of system-level conditions such as:
    - missed deadlines
    - bus saturation
    - anomalous message rates
    - priority-related starvation

### 5. Deterministic Recording and Replay
- Capture of CAN traffic with preserved timing characteristics
- Deterministic replay for offline analysis and regression testing
- Separation of capture, replay, and analysis stages

### 6. Local Visualization
- Local-only visualization of:
    - live bus activity
    - normalized signals
    - detected events and anomalies
- Focus on clarity and inspectability over complexity

---
## Out-of-Scope Functionality

The following areas are explicitly **out-of-scope** for this project:

### 1. Physical CAN Hardware
- No interaction with physical CAN tranceivers
- No USB-CAN, PCIe, or embedded hardware interfaces
- All bus activity is simulated or replayed

### 2. Real Vehicle or Safety-Critical Deployment
- The project is not intended for use in production vehicles or certified systems
- No claims are made regarding safety compliance or real-world deployment readiness

### 3. Security and Authentication
- No encryption, authentication, or access control mechanisms
- Security considerations are intentionally deferred to maintain focus on observability

### 4. Vendor-Specific Tool Compatibility
- No direct integration with proprietary CAN tooling
- No requirement to support commercial DBC formats
- Signal definitions may use simplified or custom schemas

### 5. Complete CAN Protocol Coverage
- Not all CAN protocol features are implemented
- Advanced features such as:
    - error frames
    - bus-off recovery
    - bit-level arbitration modeling
are not the primary focus

### 6. Performance Optimization
- The project does not aim to maximize throughput or minimize latency
- Performance is secondary to clarity, determinism, and correctness

---
## Design Constraints and Tradeoffs

Several deliberate tradeoffs guide the project design:
- **Virtualization over physical realism**
Software simulation enables reproducibility, experimentation, and accessibility at the cost of hardware fidelity.
- **Passive analysis over control authority**
The system observes behavior rather than attempting to influence it, aligning with certification and monitoring use cases.
- **Explicit schemas over implicit interpretation**
Normalization rules are defined in code and documentation rather than hidden within tooling.
- **Determinism over real-time execution**
Accurate replay and analysis take precedence over strict real-time scheduling.

---
## Extensibility Considerations

While the initial scope is intentionally constrained, the architecture is designed to allow future extensions such as:
- Additional bus profiles
- Alternative transport backends
- More advanced analysis modules
- Integration with external visualization or metrics systems

These extensions are not required for the project to be considered complete.

---
## Definition of Done

The project will be considered complete when:
- A virtual CAN bus can be simulated and observed
- Traffic can be normalized, recorded, replayed, and analyzed
- System-level timing behaviors and anomalies can be detected
- Results can be inspected locally through logs and visual output
- The system behavior and tradeoffs are clearly documented

---
## Summary

This project intentionally prioritizes **system-level observability, reproducibility, and clarity** over hardware realism, protocol completeness, or production deployment. By explicitly defining its scope, the project aims to provide a focused and defensible exploration of CAN-based system behavior without overextending into unrelated domains.