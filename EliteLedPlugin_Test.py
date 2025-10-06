import json
import os
from lib.Logger import log
from lib.Plugin import Plugin
from lib.Settings import Settings
from .elite_led_controller import configure, set_led

class EliteLEDPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.settings = Settings(self.plugin_path, "settings.json", {
            "device_id": "",
            "device_ip": "",
            "local_key": "",
            "device_ver": 3.3
        })

    def on_load(self):
        log("info", "EliteLEDPlugin loaded")
        self.settings.load()
        configure(
            self.settings.get("device_id"),
            self.settings.get("device_ip"),
            self.settings.get("local_key"),
            self.settings.get("device_ver")
        )

    def on_unload(self):
        log("info", "EliteLEDPlugin unloaded")

    def on_settings_changed(self):
        log("info", "EliteLEDPlugin settings changed")
        self.settings.load()
        configure(
            self.settings.get("device_id"),
            self.settings.get("device_ip"),
            self.settings.get("local_key"),
            self.settings.get("device_ver")
        )

# === Event handlers ===
def on_idle(context):
    set_led("blue")

def on_docked(context):
    set_led("green")

def on_undocked(context):
    set_led("orange")

def on_under_attack(context):
    set_led("red_alert")

# === Plugin registration ===
def register(plugin):
    plugin.register_plugin(EliteLEDPlugin())
    plugin.on_event("idle", on_idle)
    plugin.on_event("docked", on_docked)
    plugin.on_event("undocked", on_undocked)
    plugin.on_event("under_attack", on_under_attack)
