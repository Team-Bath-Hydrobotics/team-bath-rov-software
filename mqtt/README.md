We use **MQTT** to publish our processed telemetry data.

This is then read by the UI and displayed.

To set up the MQTT broker, first make sure that you have installed [Docker](https://docs.docker.com/desktop/#:~:text=Next%20steps-,Install%20Docker%20Desktop,-Install%20Docker%20Desktop).

Once, docker is set up.

Create the local password file and set a password:

`cp PASSWORD.example PASSWORD`

Edit `PASSWORD` and set `HIVEMQ_KEYSTORE_PASSWORD`.

If you are on Windows, open Git Bash in this directory.

Then run:

`./create_keystore.sh`

Then:

`docker compose up -d`
