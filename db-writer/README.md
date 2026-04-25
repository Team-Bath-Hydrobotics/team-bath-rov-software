# Overview
This project aims to write data to our database (supabase)
This data is both meta data and telemetry data

## Running
Ensure you are in the src of the project
`cd db-writer`
run
`poetry install` to install all dependencies
`poetry run db-writer`

You will need a .env file with the following fields at the project root

```
MQTT_HOST
MQTT_PORT
SUPABASE_URL
SUPABASE_KEY
```

When running the writer will listen for updates from MQTT parse them and upload them to the db