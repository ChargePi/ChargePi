from rpi_ws281x import PixelStrip
import sys

_LED_PIN: int = 12
_LED_FREQ_HZ: int = 800000
_LED_DMA: int = 10
_LED_BRIGHTNESS: int = 255
_LED_INVERT: bool = False
_LED_CHANNEL: int = 0

if __name__ == "__main__":
    # json_arg = json.loads(sys.argv[1])
    strip: PixelStrip = PixelStrip(len(sys.argv[1:]), _LED_PIN,
                                   _LED_FREQ_HZ, _LED_DMA,
                                   _LED_INVERT, _LED_BRIGHTNESS,
                                   _LED_CHANNEL)
    strip.begin()
    for index, color in enumerate(sys.argv[1:]):
        strip.setPixelColor(index, int(color))
    strip.show()
