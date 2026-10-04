# Grafana (phase 2)

Provisioning as code, mounted into the container so everything appears with `docker compose up`:

- `provisioning/datasources/influxdb.yaml`: InfluxDB datasource (Flux). Org, bucket and token
  come from the container environment, i.e. from `.env`.
- `provisioning/dashboards/chiller-twin.json`: the *Chiller Twin* dashboard (temperatures with
  the active setpoint, compressor power, compressor and door state), with a `machine` variable.

Queries select data by field name and `machine_id` tag only, so they do not depend on the
measurement name chosen in `collector/schema.py`. To change the dashboard, edit it in the UI,
then *Export → Save to file* and replace the JSON here.
