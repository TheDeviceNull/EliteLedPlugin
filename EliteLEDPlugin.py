# EliteLEDPlugin.py - 4.0.0-production
# Pydantic Ocelot — Production
# Production-grade EliteLEDPlugin adapted to PluginHelper API with Pydantic models
# - Uses Pydantic BaseModel for action parameters
# - Commented out assistant replies to user events to avoid redundancy
# -----------------------------------------------------------------------------------------------
# EliteLEDPlugin.py -  3.3.0-production
# Production-grade EliteLEDPlugin adapted to PluginHelper API
# - Reads settings from self.settings.get(...)
# - Dispatches PluginEvent with dict content
# - Game events only apply LED side-effect (source: "game") and do NOT cause assistant replies

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, Tuple, Literal
from pathlib import Path
import sys
from pydantic.main import BaseModel

sys.path.append(str(Path(__file__).parent / "deps"))

from . import elite_led_controller as led

from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper, PluginEvent
from lib.PluginSettingDefinitions import (
    PluginSettings, SettingsGrid, TextSetting, ParagraphSetting, SelectSetting
)
from lib.Event import Event, ProjectedEvent, GameEvent, StatusEvent
from lib.EventManager import Projection
from lib.Logger import log
from pydantic import BaseModel


__version__ = "4.0.0-production"
RELEASE_TITLE = "Pydantic Ocelot — Production"

PLUGIN_LOG_LEVEL = "WARN"  # Options: DEBUG, INFO, WARN, ERROR
_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}

color_options = list(led.COLORS.keys())
speed_options = list(led.SPEEDS.keys())

def p_log(level: str, *args):
    try:
        lvl = _LEVELS.get(level.upper(), 999)
        threshold = _LEVELS.get(PLUGIN_LOG_LEVEL.upper(), 999)
        if lvl >= threshold:
            log(level, "[EliteLEDPlugin]", *args)
    except Exception:
        try:
            log("ERROR", "[EliteLEDPlugin] logging failure")
        except Exception:
            pass

# --- Classes for BaseModel definitions ---
class SetLedColorParameters(BaseModel):
    color: str
    speed: str = "normal"


# --- Projection for current LED state ---
class CurrentLEDState(Projection[Dict[str, Any]]):
    def get_default_state(self) -> Dict[str, Any]:
        return {
            "event": "LEDState",
            "color": "off",
            "speed": "normal",
            "last_update": None
        }

    def process(self, event: Event) -> list[ProjectedEvent]:
        if isinstance(event, PluginEvent) and getattr(event, "plugin_event_name", "") == "LEDChanged":
            data = event.plugin_event_content or {}
            new_color = data.get("new_color", "off")
            speed = data.get("speed", "normal")
            ts = data.get("timestamp", datetime.now(timezone.utc).isoformat())
            self.state.update({"color": new_color, "speed": speed, "last_update": ts})
        return []  # No need to create additional projected events

# --- Main Plugin ---
class EliteLEDPlugin(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        self._led_lock = threading.Lock()
        self._worker_threads: list[threading.Thread] = []
        self._stop_workers = False

        try:
            color_keys = list(led.COLORS.keys())
        except Exception:
            color_keys = ["off", "white"]
        self.color_options = [{"key": c, "label": c.capitalize(), "value": c, "disabled": False} for c in color_keys]

        self.settings_config = PluginSettings(
            key="EliteLEDController",
            label="Elite LED Controller",
            icon="lightbulb",
            grids=[
                SettingsGrid(
                    key="tuya_device",
                    label="Tuya Device Configuration",
                    fields=[
                        ParagraphSetting(key="tuya_desc", label="Description", readonly=True, type="paragraph",
                                         content="Enter Device ID, IP, Local Key and Version to enable the Tuya LED strip."),
                        TextSetting(key="device_id", label="Device ID", type="text"),
                        TextSetting(key="device_ip", label="Device IP", type="text"),
                        TextSetting(key="local_key", label="Local Key", type="text"),
                        TextSetting(key="device_ver", label="Device Version", type="text", default_value="3.3"),
                    ]
                ),
                SettingsGrid(
                    key="event_colors",
                    label="Event LED Colors",
                    fields=[
                        ParagraphSetting(key="event_colors_desc", label="Description", readonly=True, type="paragraph",
                                         content="Assign a color or scene to each Elite Dangerous event."),
                        SelectSetting(key="StartJump", label="FSDJump Color", type="select", default_value="fsd_jump", select_options=self.color_options),
                        SelectSetting(key="DockingGranted", label="DockingGranted Color", type="select", default_value="white", select_options=self.color_options),
                        SelectSetting(key="Undocked", label="Undocked Color", type="select", default_value="yellow", select_options=self.color_options),
                        SelectSetting(key="UnderAttack", label="UnderAttack Color", type="select", default_value="red_alert", select_options=self.color_options),
                        SelectSetting(key="Docked", label="Docked Color", type="select", default_value="white", select_options=self.color_options),
                        SelectSetting(key="FuelScoopStart", label="FuelScoopStart Color", type="select", default_value="breathing_yellow", select_options=self.color_options),
                        SelectSetting(key="FuelScoopEnd", label="FuelScoopEnd Color", type="select", default_value="white", select_options=self.color_options),
                        SelectSetting(key="SupercruiseExit", label="Supercruise Exit Color", type="select", default_value="white", select_options=self.color_options),
                        SelectSetting(key="PreferredColor", label="Preferred Color", type="select", default_value="white", select_options=self.color_options),
                    ]
                )
            ]
        )

        self._event_led_map: Dict[str, Tuple[str, str]] = {}

    # --- Utility to read settings ---
    def _get_setting(self, key: str, default: Any = None) -> Any:
        try:
            if hasattr(self, "settings") and self.settings is not None:
                val = self.settings.get(key, None)
                if val not in (None, ""):
                    return val
                if "." not in key:
                    for prefix in ("tuya_device", "event_colors", ""):
                        composed = f"{prefix}.{key}" if prefix else key
                        val = self.settings.get(composed, None)
                        if val not in (None, ""):
                            return val
        except Exception:
            pass
        return default

    # --- Configure Tuya & event mapping ---
    def on_plugin_helper_ready(self, helper: PluginHelper):
        device_id = self._get_setting("device_id", "")
        device_ip = self._get_setting("device_ip", "")
        local_key = self._get_setting("local_key", "")
        try:
            device_ver = float(self._get_setting("device_ver", "3.3"))
        except Exception:
            device_ver = 3.3
        try:
            led.configure(device_id=device_id, device_ip=device_ip, local_key=local_key, device_ver=device_ver)
            p_log("INFO", f"Configured LED controller (ver={device_ver}) id={device_id} ip={device_ip}")
        except Exception as e:
            p_log("ERROR", f"Failed to configure led controller: {e}")

        # Build event->LED mapping
        self._event_led_map = {
            "LoadGame": (self._get_setting("PreferredColor", "white"), "normal"),
            "Shutdown": (self._get_setting("Shutdown", "white"), "normal"),
            "StartJump": (self._get_setting("StartJump", "fsd_jump"), "normal"),
            "DockingGranted": (self._get_setting("DockingGranted", "white"), "normal"),
            "Undocked": (self._get_setting("Undocked", "yellow"), "normal"),
            "UnderAttack": (self._get_setting("UnderAttack", "red_alert"), "fast"),
            "Docked": (self._get_setting("Docked", "white"), "normal"),
            "FuelScoopStart": (self._get_setting("FuelScoopStart", "breathing_yellow"), "normal"),
            "FuelScoopEnd": (self._get_setting("FuelScoopEnd", "white"), "normal"),
            "SupercruiseExit": (self._get_setting("SupercruiseExit", "white"), "normal"),
        }

    # --- On chat start ---
    def on_chat_start(self, helper: PluginHelper):
        self._last_helper = helper
        self.on_plugin_helper_ready(helper)
        self.register_actions(helper)
        helper.register_projection(CurrentLEDState())
        helper.register_status_generator(lambda states: [("Current LED state", states.get("CurrentLEDState", {}))])

        # Sideeffect: handle game/status events
 
        def sideeffect(event, states):
            try:
                self.handle_game_event(helper, event, states)
            except Exception as e:
                log("error", f"[EliteLEDPlugin] Sideeffect error: {e}")

        helper.register_sideeffect(sideeffect)
# --- No need to register event that triggers assistant replies --- It already replies to direct command, set_led_color
#        helper.register_event(
#            name="LEDChanged",
#            should_reply_check=lambda event: self._should_reply_to_led_event(event),
#            prompt_generator=lambda event: self._generate_led_prompt(event)
#        )
        p_log("INFO", "EliteLEDPlugin ready")
    def on_chat_stop(self, helper: PluginHelper):
        self._stop_workers = True
        for t in list(self._worker_threads):
            try:
                if t.is_alive():
                    t.join(timeout=0.5)
            except Exception:
                pass
        p_log("INFO", "EliteLEDPlugin stopped")

    # --- Actions ---
    def register_actions(self, helper: PluginHelper):
        helper.register_action(
            name="set_led_color",
            description=f"Set the LED strip to a color or scene, Available colors: {', '.join(color_options)}",
            parameters=SetLedColorParameters,  # Passa la classe del modello, non un'istanza
            method=self.set_led_method,  # Nuovo metodo che accetta un modello Pydantic
            action_type="global"  # Mantieni lo stesso action_type
        )
    
    def set_led_method(self, model: SetLedColorParameters, context: dict) -> str:
        # Estrai i parametri dal modello
        color = model.color
        speed = model.speed
    
        # Usa la logica esistente di set_led
        if not color:
            return "Missing color."
        try:
            if not led.is_reachable():
                p_log("WARN", "Device unreachable (action).")
                return "LED device unreachable; check IP/configuration."
        except Exception:
            return "LED device unreachable; check IP/configuration."
    
        # Ottieni helper dal contesto o usa quello passato
        helper = context.get("helper", None)
        if helper is None:
            helper = self._last_helper  # Potresti voler memorizzare l'helper in una variabile di classe
    
        self._apply_led(color, speed, helper, context, source="manual")
        return f"LED update queued: color={color}, speed={speed}"

    # --- Handle game/status events ---
    def handle_game_event(self, helper, event, states):
        if hasattr(event, "content") and isinstance(event.content, dict) and event.content.get("event") == "LEDChanged":
            return
    
        event_name = None
    
        # Check if this is a status event with FuelScoopStarted/FuelScoopEnded
        if hasattr(event, "status") and isinstance(event.status, dict) and "event" in event.status:
            event_name = event.status["event"]
    
        # If not a status event, check if it's a regular game event
        if not event_name and hasattr(event, "content") and isinstance(event.content, dict):
            event_name = event.content.get("event")
    
        if not event_name:
            return
    
        key = event_name
    
        # Handle FuelScoopStarted / FuelScoopEnded
        if event_name in ("FuelScoopStarted", "FuelScoopEnded"):
            p_log("DEBUG", f"Detected {event_name} event")
            key = "FuelScoopStart" if event_name == "FuelScoopStarted" else "FuelScoopEnd"
        elif event_name == "FuelScoop":
            p_log("DEBUG", "Processing FuelScoop event")
            content = getattr(event, "content", {})
            if isinstance(content, dict):
                scooped = content.get("Scooped", 0)
                key = "FuelScoopStart" if scooped > 0 else "FuelScoopEnd"
                p_log("DEBUG", f"FuelScoop event detected, scooped={scooped}, key={key}")
    
        if key in self._event_led_map:
            color, speed = self._event_led_map[key]
            p_log("DEBUG", f"Applying LED for event {event_name}: color={color}, speed={speed}")
            self._apply_led(color, speed, helper, states, source="game")

    # --- Internal LED application ---
    def _apply_led(self, color: str, speed: str, helper: PluginHelper, states: Dict[str, Dict], source: str = "game"):
        try:
            current_state = states.get("CurrentLEDState", {})
            if current_state.get("color") == color and current_state.get("speed") == speed:
                return
        except Exception:
            pass

        def worker():
            threading.current_thread().name = f"LEDWorker-{color}-{int(time.time())}"
            try:
                with self._led_lock:
                    success = led.set_led(color, speed)
            except Exception as e:
                p_log("ERROR", f"Exception while setting LED: {e}")
                success = False
            if success:
                evt = PluginEvent(
                    plugin_event_name="LEDChanged",
                    plugin_event_content={
                        "new_color": color,
                        "speed": speed,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source": source
                    },
                    processed_at=time.time()
                )
                helper.dispatch_event(evt)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self._worker_threads.append(t)

    # --- Assistant reply policy ---
#    def _should_reply_to_led_event(self, event: PluginEvent) -> bool:
#        try:
#            content = event.plugin_event_content or {}
#            return content.get("source", "game") == "manual"
#        except Exception:
#            return False
#
#    def _generate_led_prompt(self, event: PluginEvent) -> str:
#        try:
#            content = event.plugin_event_content or {}
#            color = content.get("new_color", "unknown")
#            speed = content.get("speed", "normal")
#            ts = content.get("timestamp", "")
#            return f"NOTICE: LED updated to '{color}' (speed={speed}) at {ts}. Reply with a short acknowledgment."
#        except Exception:
#            return "NOTICE: LED updated. Reply with a short acknowledgment."
