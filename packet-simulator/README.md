# Overview
This project aims to provide a basic cli for simulating rov data and video

Video data is encoded using ffmpeg and mpegts.

### Download system level dependencies
brew install ffmpeg or your OS equivalent process

## Running
Ensure you are in the src of the project
`cd packet-simulator`
run
`poetry install` to install all dependencies
`poetry run python src/packet_simulator.py --config src/video_config.json`
This will generate image and telemetry data encoded via MPEGTS and send the video data over the specified network type.
--config represents the path to the config file in the format 

```
{
  "video_config": {
    "feeds": [
      {"width": 640, "height": 480, "fps": 60, "format": "mono"},
      {"width": 1920, "height": 1080, "fps": 30, "format": "stereo"}

    ],
    "input_file_dir": "../fake_videos"
  },
  "network":{
    "base_video_port": 6000,
    "host_ip":"127.0.0.1",
    "output_network_type": "tcp"
  }
}
```

If you do not pass the config argument default settings will be taken, if you provide a input_file_dir for the video files to stream that does not exist eg "" random patterns will be output instead of mp4 video.

To visualise the results you can then also run the pilot UI, and preferably also the video processor to avoid overwhelming the ui, following the steps in the readme.
