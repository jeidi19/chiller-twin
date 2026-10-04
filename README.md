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
| OPC UA server, MQTT gateway, collector | ✅ phase 2 | asyncua, paho-mqtt, Mosquitto, InfluxDB |
| Dashboard as code | ✅ phase 2 | Grafana |
| Anomaly detection | ⏳ phase 3 | scikit-learn |
| Control logic in Structured Text | ⏳ phase 4 | OpenPLC, Modbus TCP |

## Demo
Requires Docker with Compose.
```bash
cp .env.example .env              # development credentials, change them for anything public
docker compose up -d --build
scripts/e2e_check.sh              # optional: waits for data in InfluxDB, checks Grafana
```
Open Grafana on http://localhost:3000 (user `admin`, password `GRAFANA_PASSWORD` from `.env`),
dashboard *Chiller Twin*. The simulator runs `configs/faults_example.yaml` at 60× speed in a loop:
a 6 h batch lasts 6 minutes, and a refrigerant leak starts after about 2 minutes (see the
*Active fault* panel). The OPC UA server is also reachable from any client (e.g. UaExpert) on
`opc.tcp://localhost:4840/chiller-twin/`, where the setpoint can be written.

| Optional variable (`.env`) | Default | Meaning |
|---|---|---|
| `SIM_CONFIG` | `faults_example.yaml` | scenario in `configs/` |
| `SIM_SPEED` | `60` | simulated seconds per real second |
| `MACHINE_ID` | `bc-01` | machine name in MQTT topics and InfluxDB |

## Development
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check . && ruff format --check .
python -m simulator --config configs/faults_example.yaml --out data/run.csv   # batch → CSV
python -m simulator serve --config configs/faults_example.yaml --speed 60     # OPC UA server
```
CI (GitHub Actions) runs lint and tests on Python 3.12 and 3.13, builds the images and runs an
end-to-end job: the whole stack is started with Compose and the job waits until data reaches
InfluxDB and Grafana has loaded its datasource and dashboard.

## Data flow
**OPC UA** (`simulator/opcua_model.py`). Object `Chiller` with folders `Measurements`
(cell and product temperature, compressor power), `Status` (compressor, door, active setpoint)
and `Parameters` (the writable setpoint command), plus `label`, the fault ground truth that
exists only because this is a simulation. A written setpoint is applied only if in range;
`active_setpoint_c` shows the value actually in use.

**MQTT** (`gateway/payload.py`). One JSON message per sample on `chiller/<machine_id>/telemetry`,
QoS 1, not retained, with the source timestamp:
```json
{"ts": "2026-10-04T12:00:05+00:00", "cell_temp_c": -17.8, "product_temp_c": 12.3,
 "active_setpoint_c": -18.0, "compressor_on": true, "compressor_power_w": 2000.0,
 "door_open": false, "label": "normal"}
```
The gateway subscribes with a timestamp trigger and rebuilds each sample from the values that
share the same source timestamp, so every message is a consistent snapshot.

**InfluxDB** (`collector/schema.py`). Measurement `chiller`, tags `machine_id` and `label`, float
fields for temperatures and power, bool fields for compressor and door. Malformed messages are
logged and skipped.

## Faults
| Fault | Effect on the plant | What should be visible in the data |
|---|---|---|
| `refrigerant_leak` | cooling capacity ↓↓, compressor power ↓ | longer compressor cycles, slower cool-down |
| `compressor_wear` | compressor power ↑↑, cooling capacity ↓ | more energy per cycle |
| `door_gasket` | heat leakage from the room ↑ | shorter off-times |
| `sensor_drift` | none — the sensor reads too high | cell held colder than needed, more energy |

## Roadmap
- [x] **Phase 1** — thermal model, controller, fault injection, tests
- [x] **Phase 2** — OPC UA + MQTT + InfluxDB + Grafana, one-command demo with `docker compose up`
- [ ] **Phase 3** — labelled datasets, Isolation Forest, anomaly score and alerts on the dashboard
- [ ] **Phase 4** — control logic in IEC 61131-3 Structured Text on OpenPLC; fault classification

## How AI was used
I designed and wrote the thermal model, the OPC UA information model, the MQTT message format and the InfluxDB schema (the ML feature design in phase 3 will be mine too). Scaffolding, the compressor controller, the server/gateway/collector plumbing, tests, infrastructure configuration and documentation were written with the help of Claude (Anthropic); every design choice was reviewed and discussed.

## License
MIT
