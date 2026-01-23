# Proposed Repository Layout

```
virtual-bus/
    README.md
    LICENSE
    .gitignore
    pyproject.toml
    .env.example                   # local config
    docs/
        motivation.md
        scope.md
        architecture.md
        file-structure.md

    src/
        virtual_bus/
            __init__.py

            config/
                __init__.py
                settings.py              # paths, run IDs, replay speed

            schemas/
                __init__.py
                raw_frame.schema.json
                signal.schema.json
                event.schema.json
                artifacts.schema.json    # metadata about model artifacts

            bus/
                __init__.py
                backend.py               # BusBackend interface
                inproc.py                # in-process implementation
                types.py                 # Frame dataclass, enums, common types

            generate/
                __init__.py
                scenarios.py             # baseline/anomalous scenario definitions
                generator.py             # virtual node scheduling + emission
                faults.py                # jitter, drops, bursts, ID flooding

            observe/
                __init__.py
                observer.py              # passive subscriber + fan-out
                timestamps.py            # timestamp policy (source vs capture)

            storage/
                __init__.py
                raw_store.py             # frames.jsonl writer/reader
                signal_store.py          # signals.jsonl writer/reader
                event_store.py           # events.jsonl writer/reader
                session.py               # run_id, metadata.json, hashing configs

            replay/
                __init__.py
                replayer.py              # reads raw frames → re-emits deterministically
                clock.py                 # real-time vs scaled time vs step mode

            normalize/
                __init__.py
                mapping.py               # ID → signal decode definitions
                normalizer.py            # frame → signals
                decode.py                # byte unpacking helpers

            offline/
                __init__.py
                dataset.py               # build training datasets from signals
                train.py                 # train autoencoder / baseline model
                calibrate.py             # thresholds, scoring params
                evaluate.py              # metrics, comparison baseline vs anomalous
                artifacts.py             # save/load model artifacts + metadata

            analyze/
                __init__.py
                analyzer.py              # orchestrates rules + model scoring
                rules.py                 # timing/rate rules
                model.py                 # model inference wrapper (loads artifacts)
                events.py                # event types, severity, formatting

            dashboard/
                __init__.py
                api.py                   # local API
                ui/                      # static frontend assets
                    index.html
                    app.js
                    styles.css

    scripts/
        run_live.py                  # generator → bus → observer → normalize → analyze
        run_replay.py                # raw_store → replayer → normalize → analyze
        run_offline.py               # normalize → train/calibrate → evaluate
        make_scenario.py             # optional helper to generate configs/runs

    tests/
        test_normalizer.py
        test_replayer.py
        test_rules.py
        test_offline_artifacts.py
        test_schema_validation.py

    artifacts/
```
