from typing import Any, Literal, override
from dataclasses import dataclass, field
from datetime import datetime, timezone
from lib.PluginHelper import PluginHelper, PluginManifest
from lib.PluginBase import PluginBase
from lib.PluginSettingDefinitions import PluginSettings, SettingsGrid, TextSetting, ParagraphSetting, SelectSetting, SelectOption
from lib.Event import Event, ProjectedEvent
from lib.EventManager import Projection
from lib.Logger import log
from . import elite_led_controller as led
import sys
import socket
import threading
from pathlib import Path
from lib.Event import GameEvent

# Add deps/ folder to sys.path (in case dependencies are vendored inside the plugin)
sys.path.append(str(Path(__file__).parent / "deps"))

import tinytuya  # ensure tinytuya can be imported when bundled


# Color options for the dropdowns
color_options = [
    {"key": c, "label": c.capitalize(), "value": c, "disabled": False}
    for c in led.COLORS.keys()
]

# === Custom LED Event ===
@dataclass
class LEDChangedEvent(Event):
    new_color: str
    speed: str = "normal"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['tool'] = 'tool'
    processed_at: float = field(default=0.0)
    text: list[str] = field(default_factory=list)
    memorized_at: str = None # to be set when event is memorized by the COVAS:NEXT system
    responded_at: str = None # to be set when event is responded to by the COVAS:NEXT system

    def __post_init__(self):
        self.text = [f"LED changed to {self.new_color} (speed={self.speed})"]

    def __str__(self) -> str:
        return self.text[0]

# === LED State Projection ===
class CurrentLEDState(Projection[dict[str, Any]]):
    def get_default_state(self) -> dict[str, Any]:
        return {"event": "LEDState", "color": "off", "speed": "normal"}

    def process(self, event: Event) -> list[ProjectedEvent]:
        projected: list[ProjectedEvent] = []
        if isinstance(event, LEDChangedEvent):
            self.state["color"] = event.new_color
            self.state["speed"] = event.speed
            projected.append(ProjectedEvent({
                "event": "LEDChanged",
                "new_color": event.new_color,
                "speed": event.speed
            }))
        return projected
# === Game Event to Led Projection ===
class GameEventToLEDProjection(Projection[dict[str, Any]]):
    def get_default_state(self) -> dict[str, Any]:
        return {"last_event": None}

    def process(self, event: Event) -> list[ProjectedEvent]:
        projected: list[ProjectedEvent] = []
        if hasattr(event, "event"):
            evt_name = getattr(event, "event")
            if evt_name in EVENT_LED_MAP:
                color, speed = EVENT_LED_MAP[evt_name]
                projected.append(ProjectedEvent({
                    "event": "LEDChanged",
                    "new_color": color,
                    "speed": speed
                }))
        return projected


# === Main Plugin Class ===
class EliteLEDPlugin(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest, event_classes=[LEDChangedEvent])

        # Initialize thread lock for LED operations
        self._led_lock = threading.Lock()

        # === Plugin Settings ===
        self.settings_config: PluginSettings | None = PluginSettings(
            key="EliteLEDController",
            label="Elite LED Controller",
            icon="lightbulb",
            grids=[
                # LED control info (optional paragraph)
                SettingsGrid(
                    key="info",
                    label="Info",
                    fields=[
                        ParagraphSetting(
                            key="intro",
                            label="Introduction",
                            type="paragraph",
                            readonly=True,
                            content="Configure your Tuya LED device below. These settings allow the plugin to communicate with your LED strip."
                        )
                    ]
                ),
                # Tuya device configuration
                SettingsGrid(
                    key="tuya_device",
                    label="Tuya Device Configuration",
                    fields=[
                        TextSetting(key="device_id", label="Device ID", type="text", placeholder="Enter Tuya Device ID", default_value=""),
                        TextSetting(key="device_ip", label="Device IP", type="text", placeholder="Enter Tuya Device IP", default_value=""),
                        TextSetting(key="local_key", label="Local Key", type="text", placeholder="Enter Tuya Local Key", default_value=""),
                        TextSetting(key="device_ver", label="Device Version", type="text", placeholder="Tuya Device Version", default_value="3.3"),
                    ]
                ),
                # Event to LED color mapping - add "default" color?
                SettingsGrid(
                    key="event_colors",
                    label="Event LED Colors",
                    fields=[
                        SelectSetting(key="StartJump", label="FSDJump Color", type="select", default_value="fsd_jump", select_options=color_options),
                        SelectSetting(key="DockingGranted", label="DockingGranted Color", type="select", default_value="white", select_options=color_options),
                        SelectSetting(key="Undocked", label="Undocked Color", type="select", default_value="yellow", select_options=color_options),
                        SelectSetting(key="UnderAttack", label="UnderAttack Color", type="select", default_value="red_alert", select_options=color_options),
                        SelectSetting(key="Docked", label="Docked Color", type="select", default_value="white", select_options=color_options),
                        SelectSetting(key="FuelScoopStart", label="FuelScoopStart Color", type="select", default_value="breathing_yellow", select_options=color_options),
                        SelectSetting(key="FuelScoopEnd", label="FuelScoopEnd Color", type="select", default_value="white", select_options=color_options),
                    ]
                )   
            ]
        )
    # === Called when plugin helper is ready: configure LED device dynamically ===
    @override
    def on_plugin_helper_ready(self, helper: PluginHelper):
        # Read values from plugin UI
        device_id = helper.get_plugin_setting("EliteLEDController", "tuya_device", "device_id") or ""
        device_ip = helper.get_plugin_setting("EliteLEDController", "tuya_device", "device_ip") or ""
        local_key = helper.get_plugin_setting("EliteLEDController", "tuya_device", "local_key") or ""
        device_ver_str = helper.get_plugin_setting("EliteLEDController", "tuya_device", "device_ver") or "3.3"

        try:
            device_ver = float(device_ver_str)
        except ValueError:
            device_ver = 3.3

        # Configure elite_led_controller with user-provided settings
        led.configure(device_id=device_id, device_ip=device_ip, local_key=local_key, device_ver=device_ver)
        log("debug", f"[EliteLEDPlugin] Tuya device configured: ID={device_id}, IP={device_ip}, Ver={device_ver}")
# Events to be added (modified): StartJump (FSDJump), FuelScoopStart (FuelScoop), FuelScoopEnd (FuelScoop - new color?)
# Add default led color
        event_colors = {
            "StartJump": helper.get_plugin_setting("EliteLEDController", "event_colors", "StartJump") or "fsd_jump",
            "DockingGranted": helper.get_plugin_setting("EliteLEDController", "event_colors", "DockingGranted") or "white",
            "Undocked": helper.get_plugin_setting("EliteLEDController", "event_colors", "Undocked") or "yellow",
            "UnderAttack": helper.get_plugin_setting("EliteLEDController", "event_colors", "UnderAttack") or "red_alert",
            "Docked": helper.get_plugin_setting("EliteLEDController", "event_colors", "Docked") or "white",
            "FuelScoopStart": helper.get_plugin_setting("EliteLEDController", "event_colors", "FuelScoopStart") or "breathing_yellow",
            "FuelScoopEnd": helper.get_plugin_setting("EliteLEDController", "event_colors", "FuelScoopEnd") or "white",
        }

        # === Elite Dangerous Events → LED Mapping ===
        global EVENT_LED_MAP
        # Events to be added (modified): StartJump (FSDJump), FuelScoopStart (FuelScoop), FuelScoopEnd (FuelScoop - new color?)
        # Add "hidden" event to be used as "default led color"
        EVENT_LED_MAP = {
            "LoadGame": ("white", "normal"),  # led reset to white on game load
            "UnderAttack": (event_colors["UnderAttack"], "fast"),
            "StartJump": (event_colors["StartJump"], "normal"),
            "DockingGranted": (event_colors["DockingGranted"], "normal"),
            "Docked": (event_colors["Docked"], "normal"),
            "FuelScoopStart": (event_colors["FuelScoopStart"], "normal"), # Wrong event name. Should be "FuelScoop"
            "Undocked": (event_colors["Undocked"], "normal"),
            "FuelScoopEnd": (event_colors["FuelScoopEnd"], "normal"), # To be removed? Or to be change to "ReservoirReplenished"?
        }

    # === Action to set LED manually ===
    def register_actions(self, helper: PluginHelper):
        helper.register_action(
            "set_led_color",
            "Set the LED strip to a color or scene",
            {
                "type": "object",
                "properties": {
                    "color": {"type": "string", "enum": list(led.COLORS.keys())},
                    "speed": {"type": "string", "enum": list(led.SPEEDS.keys())}
                },
                "required": ["color"]
            },
            lambda args, states: self.set_led(args, states, helper),
            "global"
        )

    def register_projections(self, helper: PluginHelper):
        helper.register_projection(CurrentLEDState())
        helper.register_projection(GameEventToLEDProjection())

    def register_status_generators(self, helper: PluginHelper):
        helper.register_status_generator(
            lambda states: [("Current LED state", states.get("CurrentLEDState", {}))]
        )

    def register_should_reply_handlers(self, helper: PluginHelper):
        helper.register_should_reply_handler(lambda event, states: self.handle_game_event(helper, event, states))

    def register_sideeffects(self, helper: PluginHelper):
        def apply_led_from_projection(event: Event, states: dict[str, dict]):
            if isinstance(event, ProjectedEvent) and event.content.get("event") == "LEDChanged":
                color = event.content.get("new_color")
                speed = event.content.get("speed", "normal")
                self._apply_led(color, speed, helper, states)
        helper.register_sideeffect(apply_led_from_projection)
# Also react to game or conversational events directly
        helper.register_sideeffect(lambda event, states: self.handle_game_event(helper, event, states))

    # === Core LED logic ===
    def set_led(self, args: dict[str, Any], states: dict[str, dict], helper: PluginHelper) -> str:
        color = args["color"]
        speed = args.get("speed", "normal")
        try:
            self._apply_led(color, speed, helper, states)
            return "LED set successfully."
        except Exception as e:
            log("error", f"[EliteLEDPlugin] Error setting LED: {e}")
            return f"Error setting LED: {e}"

    def handle_game_event(self, helper: PluginHelper, event: Event, states: dict[str, dict]) -> bool | None:
        if not isinstance(event, GameEvent):
            return None  # Ignore non-game events   
            # Ignore assistant-completed and non-Elite events
        if getattr(event, "content", None) and isinstance(event.content, dict):
            ev_name = event.content.get("event")
            if ev_name and not ev_name in EVENT_LED_MAP:
                log("debug", f"[EliteLEDPlugin] Ignored non-Elite event: {ev_name}")
                return None   
        # Ignore projected LEDChanged events to avoid loops
        if isinstance(event, ProjectedEvent) and event.content.get("event") == "LEDChanged": 
            return None

        event_name = None
#        log("debug", f"[EliteLEDPlugin] Game event '{event}'")
        # Extract event name from GameEvent content
        if hasattr(event, "content") and isinstance(event.content, dict):
            event_name = event.content.get("event")

        if event_name and event_name in EVENT_LED_MAP:
            color, speed = EVENT_LED_MAP[event_name]
            log("debug", f"[EliteLEDPlugin] Game event '{event_name}' with LED '{color}'")
            try:
                self._apply_led(color, speed, helper, states)
                return None          
            except socket.timeout:
                log("error", "[EliteLEDPlugin] Timeout while communicating with LED device.")
                return False
            except Exception as e:
                log("error", f"[EliteLEDPlugin] Exception setting LED for event '{event_name}': {e}")
                return None
        return None


    def _apply_led(self, color: str, speed: str, helper: PluginHelper, states: dict[str, dict]) -> str:
      # Use the projected state passed to the method
        current_state = states.get("CurrentLEDState", {})

      # Avoid redundant LED updates
        if current_state.get("color") == color and current_state.get("speed") == speed:
            log("debug", f"[EliteLEDPlugin] LED already set to {color} (speed={speed}), skipping.")
            return 
        def worker():
            try:
                with self._led_lock:
                    success = led.set_led(color, speed)
                if success:
                    log("debug", f"[EliteLEDPlugin] LED set to {color}")
                else:
                    log("error", f"[EliteLEDPlugin] Error setting LED to {color}")
            except socket.timeout:
                log("error", "[EliteLEDPlugin] Timeout while communicating with LED device.")
            except Exception as e:
                log("error", f"[EliteLEDPlugin] Exception setting LED: {e}")

        threading.Thread(target=worker, name=f"LEDSet-{color}", daemon=True).start()