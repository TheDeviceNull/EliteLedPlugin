"""
Tuya Smart Bulb Scene Information Script
=======================================

This script connects to a Tuya-compatible smart bulb using the TinyTuya library
and retrieves information about the current scene/mode settings.

Purpose:
- Connect to a Tuya smart bulb using local network (no cloud required)
- Display the current device status including all Data Points (DPS)
- Identify and show the current scene/mode information
- Display all DPS values to help identify which contain scene data for your specific device

Requirements:
- Python 3.6+
- TinyTuya library (install with: pip install tinytuya)
- Device ID, IP address, and Local Key for your Tuya bulb
  (These can be obtained using the TinyTuya wizard or Tuya IoT Platform)

Usage:
1. Run the script: python tuya_bulb_scene_info.py
2. Enter the requested device information when prompted
3. Review the output to see current scene information and all DPS values

Note: Different Tuya bulb models may store scene information in different DPS keys.
This script checks common locations (DPS 21, 25-29) but your specific device may use
different keys. After running once, note which DPS keys contain scene information
for your particular device.
"""

import tinytuya
import time
import json

def main():
    print("TinyTuya BulbDevice Scene Information Script\n")
    
    # Get parameters from user input
    device_id = input("Enter Device ID: ") 
    device_ip = input("Enter Device IP: ") 
    local_key = input("Enter Local Key: ") 
    device_ver = input("Enter Device Version [default 3.3]: ") or "3.3"
    
    try:
        device_ver = float(device_ver)
    except ValueError:
        print("Invalid version, using default 3.3")
        device_ver = 3.3

    # Initialize device
    d = tinytuya.BulbDevice(device_id, device_ip, local_key)
    d.set_version(device_ver)
    d.set_socketPersistent(True)
    tinytuya.set_debug(True)

    print("\U0001F50C Connecting to device...")
    try:
        status = d.status()
        print("\u2705 Device response:")
        print(status)
        
        # Extract and display scene information
        print("\n\U0001F4A1 Current Scene Information:")
        
        # The DPS structure varies by device, but scenes are typically in specific DPS keys
        # Common DPS keys for scenes might be '21', '25', or others depending on the device
        dps = status.get('dps', {})
        
        # Check for scene mode
        if '21' in dps:  # Scene mode is often in DPS 21
            print(f"Scene Mode (DPS 21): {dps['21']}")
        
        # Check for scene data
        scene_keys = [k for k in dps.keys() if k in ['25', '26', '27', '28', '29']]
        for key in scene_keys:
            print(f"Scene Data (DPS {key}): {dps[key]}")
            
        # Check if the device is in scene mode
        if '2' in dps:  # Mode is often in DPS 2
            mode = dps['2']
            print(f"Current Mode (DPS 2): {mode}")
            if mode == 'scene':
                print("Device is currently in scene mode")
            else:
                print(f"Device is in {mode} mode (not scene mode)")
        
        # Print all DPS values for reference
        print("\n\U0001F50E All DPS Values:")
        for key, value in dps.items():
            print(f"DPS {key}: {value}")
            
    except Exception as e:
        print("\u274C Connection error:", e)
        return

if __name__ == "__main__":
    main()