<<<<<<< HEAD
# energy_utils.py
from datetime import datetime

FAN_W = 75
LIGHT_W = 40
PROJECTOR_W = 250

def energy_wh(power_w: float, duration_hours: float) -> float:
    return power_w * duration_hours

def estimate_room_energy(on_events) -> float:
    """
    on_events: list of (t_on, t_off) tuples for relay ON periods.
    Returns total Wh.
    """
    total_wh = 0
    power = FAN_W + LIGHT_W  # projector optional add karo
    for t_on, t_off in on_events:
        dt_h = (t_off - t_on).total_seconds() / 3600.0
        total_wh += energy_wh(power, dt_h)
    return total_wh

def savings_if_auto_off(idle_periods):
    """
    idle_periods: list of (t_idle_start, t_idle_end) jab room empty tha
    but traditional system me fan/light ON rehte.
    """
    power = FAN_W + LIGHT_W
    wasted_wh = 0
    for s, e in idle_periods:
        dt_h = (e - s).total_seconds() / 3600.0
        wasted_wh += energy_wh(power, dt_h)
=======
# energy_utils.py
from datetime import datetime

FAN_W = 75
LIGHT_W = 40
PROJECTOR_W = 250

def energy_wh(power_w: float, duration_hours: float) -> float:
    return power_w * duration_hours

def estimate_room_energy(on_events) -> float:
    """
    on_events: list of (t_on, t_off) tuples for relay ON periods.
    Returns total Wh.
    """
    total_wh = 0
    power = FAN_W + LIGHT_W  # projector optional add karo
    for t_on, t_off in on_events:
        dt_h = (t_off - t_on).total_seconds() / 3600.0
        total_wh += energy_wh(power, dt_h)
    return total_wh

def savings_if_auto_off(idle_periods):
    """
    idle_periods: list of (t_idle_start, t_idle_end) jab room empty tha
    but traditional system me fan/light ON rehte.
    """
    power = FAN_W + LIGHT_W
    wasted_wh = 0
    for s, e in idle_periods:
        dt_h = (e - s).total_seconds() / 3600.0
        wasted_wh += energy_wh(power, dt_h)
>>>>>>> 81bf992d76a815cbb279ad7749e4cf614edd9542
    return wasted_wh