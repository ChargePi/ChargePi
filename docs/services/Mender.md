# Mender setup

For the complete charging station experience with Over-the-air (*OTA*) updates, minimal configuration and minimal
hassle, follow this guide.

We will use [Mender](https://mender.io/) as OTA service for updating Linux, Docker and OCPP Client. If you do not wish
to use Mender, skip the first 3 steps. For the OCPP server/central system, we will
use **[SteVe](https://github.com/RWTH-i5-IDSG/steve)**.

1. Sign up on Mender. If you want, host a Mender server yourself.
2. Follow this guide
   for [installing Mender to the Pi](https://docs.mender.io/get-started/preparation/prepare-a-raspberry-pi-device).
3. Add the Raspberry to the Devices list and test if Mender works.
5. Clone the SteVe repository to ChargePi/. It should automatically create steve folder.
   *Skip this step if you do not want the server to be hosted on the same machine. Mostly used for testing purposes.*
6. If you do not wish to automatically update the OCPP client, change this label to false in docker-compose.yaml:

   ```yaml
     chargepi:
        label:
           - com.centurylinklabs.watchtower.enable="false"
   ```

   **Not recommended when using Mender, since you can update the images with Mender.**

7. Run docker-compose:

    ```bash
    docker-compose up -d 
    ```

## Helpful references

### WS281X LED library & tutorial:

- [LED library](https://github.com/jgarff/rpi_ws281x)
- [tutorial](https://tutorials-raspberrypi.com/connect-control-raspberry-pi-ws2812-rgb-led-strips/)

### Python Unsync library:

- [Unsync](https://asherman.io/projects/unsync.html)

### CS5460A library:

- [library](https://github.com/cbm80amiga/ST7789_power_meter_cs5460a_display/)
- [Datasheet](https://statics.cirrus.com/pubs/proDatasheet/CS5460A_F5.pdf)

### OCPP:

- [Steve](https://github.com/RWTH-i5-IDSG/steve)
- [Python library](https://github.com/mobilityhouse/ocpp)
- [1.6 specification](https://www.oasis-open.org/committees/download.php/58944/ocpp-1.6.pdf)
- [2.0.1 specification](https://github.com/mobilityhouse/ocpp/tree/master/docs/v201)

### Docker:

- [Installing Docker on Pi](https://www.docker.com/blog/happy-pi-day-docker-raspberry-pi/)
- [Watchtower](https://github.com/containrrr/watchtower)
- [Docker](https://docs.docker.com/)

### RPi:

- [Pinout](https://pinout.xyz/)

### Mender:

- [Docs](https://docs.mender.io/get-started/preparation/prepare-a-raspberry-pi-device)