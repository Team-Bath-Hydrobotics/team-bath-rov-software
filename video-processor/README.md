# Overview
This project aims to provide a basic cli for decoding video data, providing basic pre-processing on it, such as meta-data extraction and filtering and then re-encoding it for other streams.

This project also aims to provide back-pressure resilience, through the use of queueing and dropping of frames. Along with allowing various filters to be applied on the input data.

### Download system level dependencies
brew install ffmpeg or your OS equivalent process

## Running
Ensure you are in the src of the project
`cd video-processor`
Run
`poetry install` to install all dependencies
`poetry run python video_processor.py --config ../processor_config.json` to run the video processor

The config should be in the form:
```
{
  "video_config": {
    "input_feeds": [
      {
        "id": "1",
        "feed_settings": {
          "width": 640,
          "height": 480,
          "fps": 60,
          "format": "mono"
        },
        "backpressure_queue_settings": {
          "max_queue_size": 1000,
          "queue_timeout_ms": 500
        },
        "filter_settings":{
          "filters":[]
        }
      },
      {
        "id": "2",
        "feed_settings": {
          "width": 1920,
          "height": 1080,
          "fps": 30,
          "format": "stereo"
        },
        "backpressure_queue_settings": {
          "max_queue_size": 500,
          "queue_timeout_ms": 500
        },
        "filter_settings":{
          "filters":[]
        }
      }
    ],
    "output_feeds": [
      {
        "id": "1",
        "width": 640,
        "height": 480,
        "fps": 24,
        "format": "mono"
      },
      {
        "id": "2",
        "width": 1280,
        "height": 720,
        "fps": 24,
        "format": "stereo"
      }
    ]
  },
  "network": {
    "input_base_video_port": 6000,
    "host_ip": "127.0.0.1",
    "target_ip": "127.0.0.1",
    "output_base_video_port": 8554,
    "input_network_type": "tcp",
    "output_network_type": "udp"
  }
}
```


This will try to connect to an MPEGTS encoded stream using whatever protocol is specified in the config file, remember this must match the config of the simulator or rov data source.


It will then apply back pressure resilience as configured eg downsampling to maximum 30fps, on a stream by stream basis as outlined in the config file.


Then it will re-encode these frames using MPEGTS and send them over whatever output protocol is specified in the config, this must match all clients of this stream eg the UI.

To visualise the results you can then also run the pilot UI following the steps in the readme.
