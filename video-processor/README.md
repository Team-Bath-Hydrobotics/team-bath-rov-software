# Overview
This project aims to provide a basic cli for decoding video data, providing basic pre-processing on it, such as meta-data extraction and filtering and then re-encoding it for other streams.

This project also aims to provide back-pressure resilience, through the use of queueing and dropping of frames.

## Running 
### Download system level dependencies
brew install ffmpeg or your OS equivalent process

## Running
Ensure you are in the src of the project
`cd video-processor`
Run
`poetry install` to install all dependencies
`poetry run python src/video_processor.py` to run the video processor

This will try to connect to an MPGETS encoded stream sent over TCP.
It will then apply back pressure resilience as configured eg downsampling to maximum 30fps.
Then it will re-encode these frames using MPGETS and send them over UDP

(We probably don't need to decode and re-encode?)

You can also run in a seperate terminal a packet simulating script from the same location
`poetry run python src/simulate_packets.py`
This will generate random image and telemetry data encoded via MPGETS and send the video data over a TCP which should connect to the other script, as long as the configured ports match.

To visualise the results you can then also run the pilot UI following the steps in the readme.