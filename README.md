# ⚡ChargePi🔌

⚡ChargePi⚡ is an open-source Raspberry Pi 4 based ⚡Charging Point🔌 project, which supports multiple EVSEs and simple
connectors🔌. A charging connector🔌 consists of a WS281x RGB 🚥 LED strip, a relay and a power meter.

ChargePi client can be deployed/run in multiple ways:

- standalone
- Docker 🐳 by building the image and running the container
- Docker-compose to be deployed with SteVe Central System and Watchtower (**recommended for dev/testing only**)
- Docker-compose by running the client

# :warning: Deprecation notice

This project is no longer maintained, as we've moved to a more optimized and feature-rich version of the project in Go (
[ChargePi-go](https://github.com/ChargePi/ChargePi-go)).

The goal is to create a hardware-agnostic smart charge point platform. The Go version supports more features and
hardware, and is optimized for better performance. Any contributions are welcome.

## Charging station specifications

| Protocol implementation | Core functionalities |  Offline charging   | Local authorization | Charging profiles |
|:-----------------------:|:--------------------:|:-------------------:|:-------------------:|:-----------------:|
|    OCPP 1.6 JSON/WS     |          ✔️          |         ✔️          |         ✔️          |         ❌         |
|   OCPP 2.0.1 JSON/WS    | Will be implemented  | Will be implemented | Will be implemented |         ❌         |

## Graylog logging server

ChargePi uses [Graylog](https://www.graylog.org/) logging server for storing logs, so a logging server should be up and
running if you want the logs to be stored. Logs are sent through GELF UDP protocol to the logging server at port 12201.
The library used for logging is **graypy**.

Configure the `log_server` property in the `settings.json` file with your logging server IP.

## Initial setup

1. If you want to run SteVe on the same host:

   > ChargePi/steve/

   *_When cloning Steve from GitHub, steve directory should be automatically generated._
   Replace SteVe's default Dockerfile with Dockerfile provided in ChargePi/steve/Dockerfile to run on Raspberry Pi.

2. Wire the hardware according to the [schematics](docs/hardware/hardware.md).

3. Configure the client.

## Running standalone

1. Python 3.7+ and pip3 must be installed as they are necessary to support asynchronous operations:

   ```bash
   sudo apt-get install python3 python3-pip
   ```

1. This client uses **[SteVe](https://github.com/RWTH-i5-IDSG/steve)** for the Central System, but can connect to other
   Central Systems as well.
    * Optional: Clone the repository and run SteVe.
    * Be sure the Central system is up when running the client and that the client is added to the Charge Point list.

2. Run the following command to install necessary dependencies:

   ```bash
   sudo pip3 install -r requirements.txt
   ```

3. Run the client as sudo:

   ```bash
   sudo python3 ChargePi_client.py
   ```

## Docker

### Deploying on Docker

1. Configure the configuration file and make sure you have the proper directory structure. Be sure your Central System
   is running and create/add a charge point.

2. Build the client image on Docker:

   ```bash
   cd ChargePi/client
   docker build -t chargepi .
   ```

3. Run the container from built image:

   ```bash
   docker run --device /dev/ttyAMA0:/dev/ttyAMA0 --device /dev/mem:/dev/mem --privileged chargepi
   ```

### Deploying using docker-compose

If you wish, you can run client, SteVe server and Watchtower on the same Pi using **docker-compose**.
The **[Watchtower](https://github.com/containrrr/watchtower)** service will automatically pull the newest image and run
it when it is available.

1. Change the IP address under __server_uri__ in the settings file to **172.0.1.121**.

2. Build services:

   ```bash
   docker-compose build
   ```

3. Run services in daemon mode using the following command:

   ```bash
   docker-compose up -d
   ```




