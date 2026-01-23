# Virtual Bus

A modular framework for simulating, observing, analyzing, and replaying CAN (Controller Area Network) traffic with an emphasis on timing, normalization, and system-level behavior.

## Overview

Virtual Bus provides a software-based simulation of CAN traffic that enables:

- **Virtual CAN Bus Simulation** - Multiple nodes publishing frames with configurable timing
- **Passive Observation** - Monitor traffic without modifying it
- **Frame Normalization** - Transform raw frames into semantic, time-stamped signals
- **Timing-Aware Analysis** - Detect missed deadlines, bus saturation, and anomalies
- **Deterministic Recording & Replay** - Capture and replay traffic with preserved timing
- **Local Visualization** - Inspect live bus activity and detected events

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/virtual-bus.git
cd virtual-bus

# Install in development mode
pip install -e ".[dev]"

# Or install with visualization support
pip install -e ".[dev,viz]"
```

## Quick Start

### Run the Demo

```bash
virtual-bus demo
```

### Run a Simulation

```bash
# Simulate 3 nodes for 5 seconds
virtual-bus simulate --nodes 3 --duration 5

# With custom message period
virtual-bus simulate --nodes 5 --duration 10 --period 50
```

### Record and Replay

```bash
# Record traffic to a file
virtual-bus record --output traffic.json --duration 10

# Replay at original speed
virtual-bus replay traffic.json

# Replay at 2x speed
virtual-bus replay traffic.json --speed 2.0
```

### Analyze Recorded Traffic

```bash
virtual-bus analyze traffic.json
```

## Python API

### Basic Usage

```python
import asyncio
from virtual_bus import (
    VirtualCANBus,
    CANNode,
    CANFrame,
    BusObserver,
    TimingAnalyzer,
)
from virtual_bus.core.node import MessageConfig

async def main():
    # Create a virtual bus
    bus = VirtualCANBus("vcan0")
    
    # Create an observer
    observer = BusObserver()
    observer.attach(bus)
    
    # Create a node with periodic messages
    node = CANNode("ECU1", node_id=1)
    node.add_periodic_message(MessageConfig(
        arbitration_id=0x100,
        period_ms=100,
        data_generator=lambda: bytes([0x01, 0x02, 0x03, 0x04]),
    ))
    bus.attach_node(node)
    
    # Run the simulation
    async with bus:
        await node.start()
        await asyncio.sleep(5)
        await node.stop()
    
    # Print statistics
    print(f"Observed {observer.frame_count} frames")
    print(f"Unique IDs: {observer.unique_ids}")

asyncio.run(main())
```

### Frame Normalization

```python
from virtual_bus import FrameNormalizer, CANFrame
from virtual_bus.normalizer.schema import MessageSchema, SignalSchema

# Define a message schema
schema = MessageSchema(
    arbitration_id=0x100,
    name="EngineStatus",
    signals=[
        SignalSchema(
            name="RPM",
            start_bit=0,
            bit_length=16,
            scale=0.25,
            unit="rpm",
        ),
        SignalSchema(
            name="Temperature",
            start_bit=16,
            bit_length=8,
            scale=1.0,
            offset=-40,
            unit="°C",
        ),
    ],
)

# Create normalizer and register schema
normalizer = FrameNormalizer()
normalizer.register_schema(schema)

# Normalize a frame
frame = CANFrame(arbitration_id=0x100, data=bytes([0xE8, 0x03, 0x5A, 0, 0, 0, 0, 0]))
message = normalizer.normalize(frame)

if message:
    print(f"Message: {message.name}")
    for signal in message.signals.values():
        print(f"  {signal.name}: {signal.physical_value} {signal.unit}")
```

### Timing Analysis

```python
from virtual_bus import TimingAnalyzer, BusObserver
from virtual_bus.analyzer.analyzer import MessageExpectation, AnalyzerConfig

# Configure analyzer
config = AnalyzerConfig(
    bus_saturation_threshold=5000,
    enable_deadline_detection=True,
    enable_jitter_detection=True,
)

analyzer = TimingAnalyzer(config=config)

# Set timing expectations
analyzer.set_expectation(MessageExpectation(
    arbitration_id=0x100,
    period_ms=100,
    tolerance_percent=20,
    jitter_threshold_ms=10,
))

# Attach to observer
observer = BusObserver()
analyzer.attach(observer)

# After running...
for event in analyzer.events:
    print(f"{event.severity.value}: {event.message}")
```

### Fault Injection

```python
from virtual_bus.faults import FaultInjector, FaultType
from virtual_bus.faults.injector import FaultRule

injector = FaultInjector(bus)

# Add a rule to drop 10% of frames for ID 0x100
injector.add_rule(FaultRule(
    fault_type=FaultType.DROP,
    probability=0.1,
    target_ids={0x100},
))

# Add delay to all frames
injector.add_rule(FaultRule(
    fault_type=FaultType.DELAY,
    probability=0.05,
    delay_ms=50,
    delay_jitter_ms=10,
))
```

## Project Structure

```
virtual-bus/
├── src/
│   └── virtual_bus/
│       ├── core/           # Bus, node, and frame implementations
│       ├── observer/       # Passive observation
│       ├── normalizer/     # Frame normalization with schemas
│       ├── analyzer/       # Timing-aware analysis
│       ├── recorder/       # Recording and replay
│       ├── visualization/  # Console visualization
│       ├── faults/         # Fault injection
│       └── cli.py          # Command-line interface
├── tests/                  # Test suite
├── docs/                   # Documentation
├── pyproject.toml          # Project configuration
└── README.md
```

## Design Philosophy

- **Clarity over completeness** - Focus on understandable, inspectable code
- **Reproducibility over performance** - Deterministic behavior for testing
- **Transparency over vendor abstraction** - No hidden assumptions
- **System behavior over protocol trivia** - Emphasis on timing and interactions

## Limitations

This project is intentionally scoped and does **not** include:

- Physical CAN hardware interfaces
- Real vehicle or safety-critical deployment
- Security/authentication mechanisms
- Vendor-specific tool compatibility
- Complete CAN protocol coverage (error frames, bit-level arbitration)
- Performance optimization

See [docs/scope.md](docs/scope.md) for full details.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src tests

# Lint
ruff check src tests

# Type check
mypy src
```

## License

MIT License - See LICENSE file for details.
