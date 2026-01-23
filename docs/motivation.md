# Motivation

## Background

Controller Area Network (CAN) is a widely deployed communication bus used in safety-critical and mission-critical systems such as automotive control units, industrial automation, robotics, and medical devices. Its design prioritizes determinism, low latency, and fault tolerance, making it well suited for real-time embedded systems.

Despite its prevalence, CAN traffic is often difficult to reason about at a system level. Raw CAN frames are small, opaque, and highly context-dependent, with meaning derived from message identifiers, timing characteristics, and external signal definitions. As a result, understanding system behavior frequently requires specialized tooling, vendor-specific workflows, or deep domain knowledge that is not easily transferable or reproducible.

---
## The Core Problem

While CAN itself is a mature and well-understood protocol, **system-level observability and analysis of CAN traffic remain fragmented and tool-dependent**.

In practice, engineers often face the following challenges:
- **Limited visibility into timing behavior** 
Many CAN issues are not caused by incorrect data values, but by late, missing, or irregularly timed messages. Existing tools frequently emphasize frame content while treating time as a secondary concern.

- **Opaque or vendor-locked tooling** 
Common CAN analysis tools are often proprietary, GUI-driven, or tightly coupled to specific hardware interfaces. This limits reproducibility, automation, and integration into modern analysis pipelines.

- **Poor separation between transport and meaning** 
CAN frames encode raw bytes, but interpretation is frequently embedded directly into tooling or documentation. This conflation makes it difficult to normalize data, compare behaviors across systems, or perform higher-level analysis.

- **Weak support for deterministic replay** 
Reproducing field issues often requires replaying traffic with accurate timing. Many existing solutions either lack replay entirely or do not preserve timing fidelity in a deterministic way.

- **Limited system-level reasoning** 
Because CAN is a shared bus, failures such as priority starvation or bus saturation often emerge from interactions between multiple nodes. These effects are difficult to detect when analyzing messages in isolation.

---
## Why Existing Solutions are Not Sufficient

It is important to address that **CAN monitoring and analysis tools already exist**, and this project does not attempt to replace or compete with mature, production-grade solutions.

However, existing approaches often fall short in at least one of the following ways:
- They prioritize **interactive debugging** over **structure analysis**
- They are designed for **single-session inspection**, not reproducible workflows
- They tightly couple **data capture, interpretation, and visualization**
- They are not easily extensible or scriptable
- They obscure internal assumptions and tradeoffs

As a result, these tools are often effective for immediate troubleshooting but less suitable for:
- automated analysis
- regression testing
- long-term data study
- experimentation with alternative system models

---
## Project Intent and Value

This project exists to explore a different approach:
> **Treating CAN traffic as a real-time distributed system that can be observed, normalized, analyzed, and replayed using transparent, modular components.**

Rather than focusing on physical hardware or protocol particulars, the project emphasizes:
- **Passive observation**
The system observes CAN traffic without injecting or modifying messages, mirroring real-world monitoring and certification constraints.
- **Explicit normalization**
Raw CAN frames are transformed into semantic, time-stamped signals using clearly defined schemas, separating transport from meaning.
- **Deterministic record and replay**
Traffic can be captured and replayed with preserved timing characteristics, enabling reproducibility and offline investigation.
- **System-level insight**
The analyzer looks for emergent behaviors such as misses deadlines, bus overload, or anomalous message patterns rather than isolated frame errors.

---
## Design Philosophy

This project deliberately favors:
- **Clarity over completeness**
- **Reproducibility over performance**
- **Transparency over vendor abstraction**
- **System behavior over protocol trivia**

The goal is not to implement every feature of CAN, nor to replace existing tooling, but to create a clear, inspectable reference architecture for CAN observability and analysis.

---
## Intended Audience

This project is intended for:
- engineers interested in real-time system and embedded communication
- developers seeking a deeper understanding of CAN beyond frame formats
- educator or students exploring distributed systems concepts
- practicioners who value reproducible analysis and clear absractions

---
## Summary

While CAN itself is a solved problem, **understanding CAN-driven systems as dynamic, time-sensitive, and interacting components remains challenging**. This project addresses that gap by providing a modular, transparent framework for simulating, observing, analyzing, and replaying CAN traffic with an emphasis on timing, normalization, and system-level behavior.