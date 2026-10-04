"""MQTT → InfluxDB collector.

    python -m collector      (configured with environment variables, see ``Settings``)

Subscribes to ``chiller/+/telemetry`` and writes one point per message, converted by
``collector.schema.to_point``. Malformed messages are logged and skipped, never fatal.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from collector.schema import to_point

log = logging.getLogger("collector")

TOPIC_FILTER = "chiller/+/telemetry"
# The delivered QoS is the minimum between the publisher's and the subscriber's.
SUBSCRIBE_QOS = 1


@dataclass(frozen=True)
class Settings:
    mqtt_host: str
    mqtt_port: int
    influx_url: str
    influx_token: str
    influx_org: str
    influx_bucket: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            mqtt_host=os.getenv("MQTT_HOST", "localhost"),
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            influx_url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
            influx_token=os.environ["INFLUXDB_TOKEN"],
            influx_org=os.environ["INFLUXDB_ORG"],
            influx_bucket=os.environ["INFLUXDB_BUCKET"],
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = Settings.from_env()
    influx = InfluxDBClient(
        url=settings.influx_url, token=settings.influx_token, org=settings.influx_org
    )
    write_api = influx.write_api(write_options=SYNCHRONOUS)

    def on_connect(client, userdata, flags, reason_code, properties):
        log.info("MQTT connected (%s), subscribing to %s", reason_code, TOPIC_FILTER)
        client.subscribe(TOPIC_FILTER, qos=SUBSCRIBE_QOS)  # again after every reconnect

    def on_message(client, userdata, message):
        try:
            point = to_point(message.topic, message.payload)
        except ValueError as exc:
            log.warning("Skipped message on %s: %s", message.topic, exc)
            return
        try:
            write_api.write(bucket=settings.influx_bucket, record=point)
        except Exception as exc:  # InfluxDB down or rejecting: keep consuming
            log.warning("InfluxDB write failed: %s", exc)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="collector")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(settings.mqtt_host, settings.mqtt_port)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
