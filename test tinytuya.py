
import tinytuya
import time

def main():
    print("TinyTuya BulbDevice Test Script\n")
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
    except Exception as e:
        print("\u274C Connection error:", e)
        return

    # --- Basic ON/OFF test ---
    print("\n\U0001F4A1 ON/OFF Test")
    try:
        d.turn_on()
        print("LED turned ON")
        time.sleep(2)
        d.turn_off()
        print("LED turned OFF")
        time.sleep(2)
    except Exception as e:
        print("\u274C ON/OFF error:", e)

    # --- Red color test (if supported) ---
    print("\n\U0001F3A8 RED Color Test")
    try:
        d.set_mode("colour")
        time.sleep(1)
        d.set_colour(255, 0, 0)  # Pure RGB
        d.turn_on()
        print("LED should be RED")
    except Exception as e:
        print("\u26A0\uFE0F Color set error:", e)

    print("\n\U0001F50E Script completed. Check DPS log above ↑")

if __name__ == "__main__":
    main()
