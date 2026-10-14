"""Alarm factory: the config decides which implementation is used."""
from .base import Alarm


def make_alarm(cfg: dict) -> Alarm:
    kind = cfg.get("alarm", "console")
    if kind == "speaker":
        from .speaker import SpeakerAlarm
        return SpeakerAlarm()
    if kind == "gpio_buzzer":
        from .gpio_buzzer import GpioBuzzerAlarm
        return GpioBuzzerAlarm(cfg.get("buzzer_pin", 18), cfg.get("buzzer_active_high", True))
    if kind == "console":
        from .console import ConsoleAlarm
        return ConsoleAlarm()
    raise ValueError(f"Unknown alarm type: {kind}")
