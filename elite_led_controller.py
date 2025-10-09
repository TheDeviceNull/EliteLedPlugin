import tinytuya
import time
import logging
import socket
from lib.Logger import log


# Disable noisy tinytuya logging
logging.getLogger("tinytuya").setLevel(logging.CRITICAL)
tinytuya.set_debug(False)

# === Set a timeout for socket operations ===
socket.setdefaulttimeout(2)

# === Configure Tuya device settings from plugin ===
def configure(device_id: str, device_ip: str, local_key: str, device_ver: float = 3.3):
    """Set Tuya device parameters from plugin settings"""
    global DEVICE_ID, DEVICE_IP, LOCAL_KEY, DEVICE_VER
    DEVICE_ID = device_id
    DEVICE_IP = device_ip
    LOCAL_KEY = local_key
    DEVICE_VER = device_ver

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
    'under attack': 'red_alert',
    'NavRoute': 'white',
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

# === Initialize the Tuya Bulb device ===
def init_device():
    """Initialize the LED strip connection using configured values"""
    try:
        d = tinytuya.BulbDevice(DEVICE_ID, DEVICE_IP, LOCAL_KEY)
        d.set_version(DEVICE_VER)
        d.set_socketPersistent(True)
        return d
    except Exception as e:
        log("error", f"[EliteLEDPlugin] Error connecting to LED device: {e}")
        return None

# === Set LED color or scene ===
def set_led(color: str, speed: str = "normal") -> bool:
    """Set the LED strip to a color or scene"""
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
        elif color in ['red_alert', 'orange_alert', 'fsd_jump', 'breathing_yellow']:
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

            d.turn_on()
            return True
        else:
            rgb = COLORS.get(color)
            if rgb:
                d.set_mode('colour')
                time.sleep(0.2)
                d.set_colour(*rgb)
                d.turn_on()
                return True
            return False
    except Exception as e:
        log("error", f"[EliteLEDPlugin] Error setting {color}: {e}")
        return False

