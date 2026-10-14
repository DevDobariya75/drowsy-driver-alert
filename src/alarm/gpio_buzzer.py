"""Raspberry Pi alarm: active buzzer module on a GPIO pin (gpiozero, Pi-only)."""
from .base import Alarm


class GpioBuzzerAlarm(Alarm):
    def __init__(self, pin: int = 18, active_high: bool = True):
        from gpiozero import Buzzer  # Pi-only dependency

        # Some modules beep when the pin is LOW: set buzzer_active_high: false.
        self.buzzer = Buzzer(pin, active_high=active_high)
        super().__init__()

    def _sound(self, on, seconds):
        if on:
            self.buzzer.on()
        else:
            self.buzzer.off()
        self._wait(seconds)

    def close(self):
        super().close()
        self.buzzer.close()
