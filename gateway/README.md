# Gateway (phase 2)

Reads the machine variables from the simulator OPC UA server (`asyncua`) and publishes them on MQTT (`paho-mqtt`), topic `chiller/<machine_id>/telemetry`, JSON payload.
