# Supported hardware and schematics

Hardware must be configured in `settings.json` and `connectors.json` files.

## RFID/NFC readers

### Supported or tested readers

| Reader |  Is supported    | 
| :---:	| :---:	|
|  PN532    |  ✔  |

#### PN532

PN532 reader shares the I2C bus 1 with the LCD.

| RPI PIN |   PN532 PIN    | 
| :---:	| :---:	|
|   2 or any 5V pin    |  VCC  |
|   14 or any ground pin    |  GND    | 
|   3 (GPIO 2)    |  SDA    |
|   5 (GPIO 3)    |  SCL    | 

## Displays

### Supported displays

| Display |  Is supported    | 
| :---:	| :---:	|
|  HD44780    |  ✔ |

#### HD44780

The HD44780 LCD should be on I2C bus 1 with an address equal to 0x27. To find the I2C address, follow these steps:

1. Download i2c tools:

   ```bash
   sudo apt-get install -y i2c-tools
   ```

2. Enable I2C interface and if needed, reboot.

3. Run the following command to get the I2C address:

   ```bash
   sudo i2cdetect -y 1 
   ```

| RPI PIN |   PCF8574 PIN    | 
| :---:	| :---:	|
|   2 or any 5V pin    |  VCC  |
|   14 or any ground pin    |  GND    | 
|   3 (GPIO 2)    |  SDA    |
|   5 (GPIO 3)    |  SCL    | 

## Relay (or relay module)

It is highly recommended splitting both GND and VCC between relays or using a relay module.

| RPI PIN |  RELAY PIN    | 
| ---	| :---:	|
|   4 or any 5V pin    |   VCC    | 
|   20 or any ground pin    |   GND    |  
|  37 (GPIO 26) or any free GPIO pin    |   S/Enable    |  

## Power meter

### Supported power meters

| Power meter |  Is supported | 
| :---:	| :---:	|
|  CS5460A    |  ✔ |

#### CS5460A

| RPI PIN|  CS5460A PIN    |  RPI PIN |   CS5460A PIN    |
| :---:	| :---:	| :---:	| :---:	|
|   4 or 2    |   VCC    |  38 (GPIO 20)    |   MOSI    |
|   25 or any ground pin    |   GND    |   35 (GPIO 19)    |   MISO    |
|   Any free pin    |   CE/CS    |   /    |   /    |
|   40 (GPIO 21)    |   SCK    |   /    |  /    |

## Indicators

### Supported LED indicators

| Indicator |  Is supported | 
| :---:	| :---:	|
|  WS2812b    |  ✔ |
|  WS2811    |  ✔ |

#### WS2811 and WS2812b

The WS281x LED strip comes in multiple voltage variants. It is recommended to use the 5V variant, because there is no
need to add an external power supply that will supply 12V or more.

| RPI PIN|  WS281x PIN    |  RPI PIN |   WS281x PIN    |
| :---:	| :---:	| :---:	| :---:	|
|    Any 5V pin   |   VCC    |  32 (GPIO 12)    |   Data |
|    Any GND pin   |   GND    |   /    |  / |

## Wiring diagram

![](WiringSketch_eng.png)