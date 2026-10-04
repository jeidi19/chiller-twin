# Chiller Twin

Digital twin of an industrial **blast chiller** feeding an **IIoT pipeline** (OPC UA → MQTT → InfluxDB → Grafana), with **machine learning** to detect faults before they stop the machine.

> 🚧 Work in progress — see the [roadmap](#roadmap).

## Why
Refrigeration machines rarely break suddenly: a refrigerant leak or a worn compressor shows up first as small changes in temperatures, duty cycle and power. This project simulates such a machine, injects realistic faults, streams the data through the same stack used in Industry 4.0 plants, and learns to spot the faults early.

## Architecture
```
[Simulator] --OPC UA--> [Gateway] --MQTT--> [Collector] --> InfluxDB --> Grafana
 thermal model                                               ^
 controller                                        [ML anomaly scorer]
 fault injection
```

| Component | Status | Tech |
|---|---|---|
| Thermal model, controller, fault injection | ✅ phase 1 | Python, NumPy |
| OPC UA server, MQTT gateway, collector | 🚧 phase 2 | asyncua, paho-mqtt, Mosquitto, InfluxDB |
| Dashboard as code | ⏳ phase 2 | Grafana |
| Anomaly detection | ⏳ phase 3 | scikit-learn |
| Control logic in Structured Text | ⏳ phase 4 | OpenPLC, Modbus TCP |

## Quick start
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m simulator --config configs/faults_example.yaml --out data/run.csv
```
OPC UA server (phase 2, in progress): `python -m simulator serve --config configs/faults_example.yaml --speed 60`.

Full pipeline (phase 2, in progress):
```bash
cp .env.example .env && docker compose up -d --build
scripts/e2e_check.sh          # waits for data in InfluxDB, checks Grafana provisioning
```
Grafana on http://localhost:3000 (user `admin`, password `GRAFANA_PASSWORD` from `.env`), dashboard *Chiller Twin*.

## Faults
| Fault | Effect on the plant | What should be visible in the data |
|---|---|---|
| `refrigerant_leak` | cooling capacity ↓↓, compressor power ↓ | longer compressor cycles, slower cool-down |
| `compressor_wear` | compressor power ↑↑, cooling capacity ↓ | more energy per cycle |
| `door_gasket` | heat leakage from the room ↑ | shorter off-times |
| `sensor_drift` | none — the sensor reads too high | cell held colder than needed, more energy |

## Roadmap
- [x] **Phase 1** — thermal model, controller, fault injection, tests
- [ ] **Phase 2** — OPC UA + MQTT + InfluxDB + Grafana, one-command demo with `docker compose up`
- [ ] **Phase 3** — labelled datasets, Isolation Forest, anomaly score and alerts on the dashboard
- [ ] **Phase 4** — control logic in IEC 61131-3 Structured Text on OpenPLC; fault classification

## How AI was used
The thermal model and the ML feature design were developed and validated by me; scaffolding, the compressor controller, tests, infrastructure configuration and documentation were written with the help of Claude (Anthropic).

## License
MIT
