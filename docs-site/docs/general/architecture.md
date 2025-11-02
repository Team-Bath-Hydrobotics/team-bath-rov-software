The teams goal for 2026 is to enable this architecture
![Rov architecture diagram](../images/rov-arch.png)


# Responsibilities of services
## Preprocesser
- parse raw sensor data/frames
- validate and annotate with mission_id, device, ingest_timestamp, schema_version, producer_id
- smooth or filter eg low pass
- compute derived metrics (velocity etc)
- publish to mqtt topics
- optionally provide rest endpoint for - 
	- `/health` – system heartbeat
	- `/schema` – current telemetry schema (JSON Schema)
	- `/status` – CPU/GPU/memory metrics

## MQTT Broker
- real time message bus for telemetry and status
- retain latest message for new subscribers (eg after ui disconnect)
- Topics such as rov/{rov_id}/{mission_id}/telemetry/{sensor}
- Allow multiple pub subs
- Bidirectional communication if necessary (might be for float)

## Video ingest service
- capture and encode video stream, stream low latency 
- Avoid routing frames through mqtt, publish metadata to mqtt
- jetson nano, encode/decode and stream video using ffmpeg
- allow concurrent subscribers eg UI, recorder
- optionally provide rest endpoint for - 
	- `/health` – system heartbeat
	- `/schema` – current telemetry schema (JSON Schema)
	- `/status` – CPU/GPU/memory metrics

## Schema registry
- json schema with pydantic models accessed by fast api
- retrieve by version and allow ui to request a schema for decoding rather than hard coupling and redefining in all applications

## UI 
- queries schema registry for data format based on schema present in packets
- subscribe to cleaned topics via async mqtt clients
- decode video on seperate thread
- connect to video ingest service for low latency video
- show mission critical indicators
- display tasks lists, timers, alerts
- potentially allow limited controls input
- be able to render replay streams
- offload analysis to dashboards

## Secondary UI
- queries schema registry for data format based on schema present in packets
- Subscribe to telemetry + ML topics
- Display system diagnostics
- Display graphs
- Show ML inference output, species count, iceberg tracking, edna estimates, could be a web dashboard eg grafana

## DB writer
- queries schema registry for data format based on schema present in packets
- consumes telemetry stream/meta data from mqtt topic
- writes to postgres and influx or similar

## Replay engine
- runs anywhere
- reconstruct past missions from db
- publish to mqtt
- optionally stream timestamped synced video

## ML consumers
- subscribe to video data
- run inference tasks
- publish results back to mqtt
- archived processed annotations/images for training

## Archive
- s3/minio store for processed video
