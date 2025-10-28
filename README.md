# EliteLedPlugin

A Covas:Next plugin to control Tuya-compatible LED strips based on Elite Dangerous game events.

## Installation

1. Copy the entire plugin folder to the `plugins/` directory of Covas:Next.
2. Ensure the `deps/` folder contains `tinytuya` if not installed globally.
3. Restart Covas:Next and enable the plugin via the Plugins UI.


## Usage

Configure your Tuya device in the plugin settings UI:
- Device ID
- Device IP
- Local Key
- Device Version (usually 3.3)

### Standalone Device Test

You can test your Tuya LED device directly using the script `test tinytuya.py`:

```bash
python "test tinytuya.py"
```
The script will prompt for Device ID, IP, Local Key, and Device Version (default 3.3). It will:
- Connect to the device
- Test ON/OFF
- Set the color to RED (if supported)

You can press Enter to use the default values shown in the prompts.

## Development

This plugin follows il [COVAS:Next Plugin Template](https://github.com/MaverickMartyn/COVAS-NEXT-Plugin-Template).

## License
MIT

### How to obtain Device ID, IP, and Local Key

1. **Tuya Device ID & IP**
   - Use a mobile app such as [Tuya Smart](https://www.tuya.com/) or [Smart Life](https://www.smartlife.com/).
   - Your router may also show connected devices; find the IP of the LED strip.
   - Device ID can sometimes be retrieved from the app’s device info or via packet capture (advanced).

2. **Local Key**
   - This is required to control the device locally.
   - **Method 1: Tuya IoT Platform**
     - Register an account at [Tuya IoT Platform](https://iot.tuya.com/).
     - Add your device to a project.
     - Retrieve the `Local Key` from the device details. (check this howto: https://community.home-assistant.io/t/get-local-key-tuya-since-june-2022/436399)
   - **Method 2: Use `tuya-cli` or packet sniffing** (for advanced users)
     - Tools like `tuya-cli` allow you to extract the local key by capturing device setup traffic.
     - See [tinytuya documentation](https://github.com/jasonacox/tinytuya) for details.

3. Once all values are obtained, enter them in the plugin settings UI in Covas:Next.

## Usage

- **Manual LED Control**
  - Use the `Set LED Color` action in Covas:Next to change the LED color or dynamic scene.
- **Automatic Event Mapping**
  - The plugin no longer uses a hard-coded mapping. Colors and dynamic scenes are configurable per-event in the plugin settings UI:
    - Open the plugin settings (Elite LED Controller) in Covas:Next.
    - Under "Event LED Colors" choose the color or scene for each game event from the dropdowns (e.g. StartJump, DockingGranted, UnderAttack, FuelScoopStart, FuelScoopEnd, Docked, Undocked, etc.).
    - You can also select a speed for dynamic scenes where applicable.
  - Once configured, the plugin will apply the selected color/scene automatically when the corresponding Elite Dangerous event occurs.
  - If you prefer manual control, use the "Set LED Color" action to apply a color/scene immediately.

## Notes

- Ensure your LED strip is on the same local network as your PC running Covas:Next.
- The plugin uses `tinytuya` to communicate directly with the LED device.
- `Device Version` is usually `3.3`; only change if your device requires a different version.

## Troubleshooting

- If the LED does not respond:
  1. Check IP address and Device ID.
  2. Ensure the local key is correct.
  3. Verify that no firewall blocks the connection.
  4. Use the test script provided in the plugin folder (`test tinytuya.py`) to verify connectivity.

## License

MIT License

<!-- Changelog moved to the end -->

## Changelog

### v2.0.1 — Event Reactor
Release name: Event Reactor

Key improvements
- Fast TCP reachability checks for Tuya devices to fail fast when a device is offline.
- Short-term caching of reachability checks and an automatic cooldown/backoff after failures to reduce repeated blocking attempts.
- Safer error handling: manual actions and automated side-effects now verify device reachability and will not report success when the device is unreachable.
- Thread-safe, non-blocking LED operations: LED updates are performed in worker threads and guarded by a lock to avoid race conditions.
- Reduced main-thread blocking caused by tinytuya by skipping attempts when the device is clearly unreachable.
- Improved handling for FuelScoop / ReservoirReplenished events (better start/end LED mapping).
- More informative logging to help diagnose connectivity and configuration issues.

Fixes & notes
- Prevents misleading success responses when the LED device is offline.
- Avoids duplicate/projection loops by emitting LEDChangedEvent only after successful LED sets.
- No breaking changes expected; verify Tuya settings (Device ID, IP, Local Key, Device Version) after upgrading.

### v2.0.0
(See release notes)
- Major refactor and feature release that introduced the event-driven LED mapping and core integration with Covas:Next.
- Added support for scene effects, configurable event→LED mappings, and plugin settings UI.
- Initial handling for many Elite Dangerous events to trigger LED color/scene changes automatically.

Release link for v2.0.0:
https://github.com/TheDeviceNull/EliteLedPlugin/releases/tag/v.2.0.0
