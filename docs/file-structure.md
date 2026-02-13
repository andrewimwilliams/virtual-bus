# Repository Layout

```
virtual-bus/

    artifacts/
        clean/
            single/{date_time}/
            multi/{date_time}/
                events.jsonl            # Events flagged by analyzer (rules-based)
                feed.jsonl              # Entire feed of processed signals
                frames.jsonl            # Raw CAN data
                model_events.jsonl      # Events flagged by ML model (inference-based)
                model_report.json       # ML training metadata and report
                run_meta.json           # Simulation metadata
                signals.jsonl           # Normalized frames prepared for analyzer/ML model
        models/
            model_v1.json               # ML artifacts
        noisy/
            single/{date_time}/
            multi/{date_time}/
                events.jsonl
                feed.jsonl
                frames.jsonl
                model_events.jsonl
                model_report.json       # ML report
                run_meta.json
                signals.jsonl

    docs/
        architecture.md
        file-structure.md
        motivation.md
        scope.md

    scripts/
        __init__.py
        model_offline.py                # Train ML on clean signals, analyze noisy signals
        replay_demo.py                  # Execute past simulation by replaying frames
        run_demo.py                     # Execute new simulation by generating frames

    src/
        virtual_bus/
            __init__.py
            bus/
                __init__.py
                analyzer.py             # Rules-based analysis layer (signals -> events)
                bus.py                  # System-wide pub-sub communication method
                generator.py            # CAN traffic generator (frames)
                jsonl.py                # JSONL parser
                model_v1.py             # ML model V1
                normalizer.py           # Normalizer layer (frames -> signals)
                observer.py             # Frame ingestor component
                replayer.py             # Replay frames (deterministic generator)
                types.py                # Data type definitions (frames, signals, events)

    tests/
        fixtures/
            clean_run_meta.json
            noisy_run_meta.json
            single_clean_events.jsonl
            single_clean_frames.jsonl
            single_clean_signals.jsonl
            single_noisy_events.jsonl
            single_noisy_frames.jsonl
            single_noisy_signals.jsonl
        test_analyzer.py
        test_demo_modes.py
        test_e2e_pipeline.py
        test_normalizer.py
        test_replayer.py
    
    .gitignore
    pyproject.toml
    README.md
```
