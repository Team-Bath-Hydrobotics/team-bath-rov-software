# Local video preset

Use this preset to try the camera dashboard without the ROV or prerecorded video
files. Both feeds use generated patterns at 640×480, 30 fps, in mono format.
The processor uses a three-frame queue per feed and a 100 ms queue read timeout.
When a queue fills, the existing backpressure code discards queued frames to make
room for newer ones. These settings reduce the work and maximum queued frame
count for laptop development; they are not a measured end-to-end latency guarantee.

## Install

Install Python 3.11+, Poetry and FFmpeg, with `ffmpeg` available on your PATH.
From the software repository root:

```sh
cd packet-simulator
poetry install
cd ../video-processor
poetry install
```

Install the secondary UI dependencies using its README as well.

## Run

From the software repository root, start both video services and the secondary UI:

```sh
python scripts/run-all.py --local-video --exclude telemetry-processor
```

Omit `--exclude telemetry-processor` to also start telemetry and its Docker broker.
The UI repository is expected alongside the software repository; use
`--web /path/to/team-bath-rov-secondary-ui` if it is elsewhere.
`--local-video` also works with `--run` to select a single service.
Without `--local-video`, the script uses `video-processor/processor_config.json`
and `packet-simulator/src/video_config.json`.

Alternatively, start the services separately:

Start the simulator first. From the software repository root, in terminal 1:

```sh
cd packet-simulator
poetry run python src/packet_simulator.py --config ../config/local-video/simulator.json
```

From the software repository root, in terminal 2:

```sh
cd video-processor
poetry run python src/video_processor.py --config ../config/local-video/processor.json
```

In terminal 3, from the secondary UI repository root:

```sh
npm run dev
```

Open <http://localhost:5173/copilot> and enable **Front Camera** and **Back Camera**.
The UI's WebSocket base URL should be `ws://localhost:50000` (its default). It can
also be set with `VITE_WS_SERVER_URL=ws://localhost:50000` in the UI's `.env.local`;
restart Vite after changing environment variables. If you previously saved a
different URL in the UI's network settings, update it there as well.

| Connection | Address |
|---|---|
| Simulator → processor, feed 1 | TCP `127.0.0.1:6000` |
| Simulator → processor, feed 2 | TCP `127.0.0.1:6001` |
| Processor → browser, front camera | `ws://localhost:50001` |
| Processor → browser, back camera | `ws://localhost:50002` |

Only these two cameras have simulated streams. Stop each command with Ctrl+C.
Avoid running another simulator or processor on the same ports at the same time.

Video playback does not require MQTT or the telemetry processor. To display
telemetry, follow the existing broker and telemetry setup separately.

## Configuration choices

- `simulator.json` leaves `input_file_dir` empty to select generated patterns.
- `processor.json` matches both input and output feeds to the simulator. Feed IDs
  `1` and `2` map to the UI camera IDs and WebSocket ports above.
- `target_ip` is empty to select WebSocket-only output. The current processor
  omits its optional UDP output when no target is configured.
- This is an optional preset. Select it with `scripts/run-all.py --local-video`
  or the explicit `--config` commands above.

The simulator and WebSocket relay currently bind listeners on all interfaces.
The addresses above describe clients running on the same machine; this preset
does not change the services' bind behavior.
