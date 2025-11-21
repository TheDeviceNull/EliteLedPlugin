import tinytuya
import time
import logging
import socket
from lib.Logger import log


# Disable noisy tinytuya logging and make sure tinytuya debug off
logging.getLogger("tinytuya").setLevel(logging.CRITICAL)
tinytuya.set_debug(False)

# === Socket / timeouts ===
# Global default socket timeout (sensible default)
socket.setdefaulttimeout(2)

# === Tuya defaults / globals ===
DEVICE_ID: str | None = None
DEVICE_IP: str | None = None
LOCAL_KEY: str | None = None
DEVICE_VER: float = 3.3

# --- Reachability / backoff globals ---
DEFAULT_TUYA_PORT = 6668
# timestamp (epoch) of last failure to reach device
_last_failure_time: float = 0.0
# when a failure occurs, skip further attempts for this many seconds (backoff)
_failure_cooldown: float = 30.0
# cache last reachability check result and time (avoid too-frequent checks)
_reachability_cache_ttl: float = 5.0
_reachability_cache_time: float = 0.0
_reachability_cache_result: bool = False

# === Colors mapping ===
COLORS = {
    'red': (255, 0, 0),
    'orange': (255, 50, 0),
    'yellow': (255, 255, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'white': (255, 255, 255),
    'purple': (128, 0, 128),
    'cyan': (0, 255, 255),
    'red_alert': 'red_alert',
    'orange_alert': 'orange_alert',
    'fsd_jump': 'fsd_jump',
    'breathing_yellow': 'breathing_yellow',
    'breathing_bluegreen': 'breathing_bluegreen',
    'under attack': 'red_alert',
    'pink': (255, 192, 203),
    'magenta': (255, 0, 255),
    'lime': (0, 255, 0),
    'olive': (128, 128, 0),
    'teal': (0, 128, 128),
    'navy': (0, 0, 128),
    'maroon': (128, 0, 0),
    'silver': (192, 192, 192),
    'gray': (128, 128, 128),
    'brown': (165, 42, 42),
    'gold': (255, 215, 0),
    'light_blue': (173, 216, 230),
    'dark_green': (0, 100, 0),
    'dark_red': (139, 0, 0),
    'orchid': (218, 112, 214)
}

# === Speed values for dynamic scenes ===
SPEEDS = {
    'fast': '0f0f',
    'normal': '1212',
    'slow': '3c3c'
}

# === Configuration setter ===
def configure(device_id: str, device_ip: str, local_key: str, device_ver: float = 3.3):
    """Set Tuya device parameters from plugin settings"""
    global DEVICE_ID, DEVICE_IP, LOCAL_KEY, DEVICE_VER
    DEVICE_ID = device_id or None
    DEVICE_IP = device_ip or None
    LOCAL_KEY = local_key or None
    try:
        DEVICE_VER = float(device_ver)
    except Exception:
        DEVICE_VER = 3.3

def _check_tcp_connectivity(ip: str, port: int = DEFAULT_TUYA_PORT, timeout: float = 1.5) -> bool:
    """Fast TCP connect test to detect unreachable IP/port (fails fast)."""
    try:
        if not ip:
            return False
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def is_reachable() -> bool:
    """Public helper to quickly determine if the configured device is reachable.
    Uses a small cache and a failure cooldown to avoid repeated slow attempts."""
    global _last_failure_time, _reachability_cache_time, _reachability_cache_result

    if not DEVICE_IP:
        return False

    now = time.time()
    # If we had a recent failure within cooldown, don't try again yet
    if _last_failure_time and (now - _last_failure_time) < _failure_cooldown:
        return False

    # Use cached reachable result if fresh
    if (_reachability_cache_time and (now - _reachability_cache_time) < _reachability_cache_ttl):
        return _reachability_cache_result

    result = _check_tcp_connectivity(DEVICE_IP, DEFAULT_TUYA_PORT, timeout=1.5)
    _reachability_cache_time = now
    _reachability_cache_result = result
    if not result:
        _last_failure_time = now
    return result

# === Initialize the Tuya Bulb device ===
def init_device():
    """Initialize the LED strip connection using configured values"""
    try:
        # Quick pre-check: avoid instantiating tinytuya when device unreachable (tinytuya may block)
        if not is_reachable():
            log("warn", "[EliteLEDPlugin] LED device not reachable (fast-check). Skipping init.")
            return None

        if not DEVICE_ID or not DEVICE_IP or not LOCAL_KEY:
            log("warn", "[EliteLEDPlugin] LED device configuration incomplete, skipping init.")
            return None

        d = tinytuya.BulbDevice(DEVICE_ID, DEVICE_IP, LOCAL_KEY)
        d.set_version(DEVICE_VER)
        # prefer persistent socket to avoid reconnect overhead when possible
        d.set_socketPersistent(True)
        return d
    except Exception as e:
        # record failure time to apply cooldown/backoff
        global _last_failure_time
        _last_failure_time = time.time()
        log("error", f"[EliteLEDPlugin] Error connecting to LED device: {e}")
        return None

# === Set LED color or scene ===
def set_led(color: str, speed: str = "normal") -> bool:
    """Set the LED strip to a color or scene. Returns boolean success."""
    # Quick reachable check before doing tinytuya calls
    if not is_reachable():
        log("warn", "[EliteLEDPlugin] LED device unreachable, skipping set_led.")
        return False

    d = init_device()
    if not d:
        log("error", "[EliteLEDPlugin] LED device not initialized, skipping LED setting.")
        return False

    try:
        if color == 'off':
            d.turn_off()
            return True
        elif color == 'on':
            d.set_mode('colour')
            time.sleep(0.2)
            d.set_colour(255, 255, 255)
            d.turn_on()
            return True
        elif color in ['red_alert', 'orange_alert', 'fsd_jump', 'breathing_yellow', 'breathing_bluegreen']:
            d.set_mode('scene')
            time.sleep(0.2)
            spd = SPEEDS.get(speed, SPEEDS['normal'])

            if color == 'red_alert':
                dps_value = f"c9{spd}01000003e803e800000000{spd}0100ec00000000000000"
                d.set_value(25, dps_value)
            elif color == 'orange_alert':
                dps_value = f"c9{spd}01000b03e803e800000000{spd}01000b00000000000000"
                d.set_value(25, dps_value)
            elif color == 'fsd_jump':
                spd = SPEEDS.get(speed, SPEEDS['slow'])
#                dps_value = f"c9{spd}0100d703e803e800000000{spd}01006600000000000000"
                dps_value = f"0447470200f803e803e80000000047470200b703e803e800000000474702008b03e803e80000000047470200b903e803e800000000"
                d.set_value(25, dps_value)
            elif color == 'breathing_yellow':
                spd = SPEEDS.get(speed, SPEEDS['slow'])
#                dps_value = f"c9{spd}0100d703e803e800000000{spd}01ffff66000000000000"
                dps_value = f"07464602000003e803e800000000464602003703e803e800000000"
                d.set_value(25, dps_value)
            elif color == 'breathing_bluegreen':
                spd = SPEEDS.get(speed, SPEEDS['slow'])
                dps_value = f"065f5f0200bc03e803e8000000005f5f02007803e803e800000000"
                d.set_value(25, dps_value)

            d.turn_on()
            return True
        else:
            rgb = COLORS.get(color)
            if isinstance(rgb, tuple):
                d.set_mode('colour')
                time.sleep(0.2)
                d.set_colour(*rgb)
                d.turn_on()
                return True
            # unknown color/scene
            log("warn", f"[EliteLEDPlugin] Unknown color/scene requested: {color}")
            return False
    except Exception as e:
        # record failure time to apply cooldown/backoff
        global _last_failure_time
        _last_failure_time = time.time()
        log("error", f"[EliteLEDPlugin] Error setting {color}: {e}")
        return False

