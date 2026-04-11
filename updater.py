import os
import sys
import time
import zipfile
import requests
from pathlib import Path

# --- CONFIG ---
ZIP_URL = "https://github.com/hefe00935/FluxHive-Launcher/releases/download/Release/FluxHive.zip"

# Uses Path.cwd() to target the folder where this script/exe is currently running
INSTALL_DIR = Path.cwd() 
ZIP_TEMP_FILE = INSTALL_DIR / "FluxHive_Launcher.zip"
TARGET_EXE = INSTALL_DIR / "FluxHive.exe"

def install():
    print("--- FluxHive Release Installer ---")
    
    # 1. Ensure directory exists (redundant for cwd, but safe)
    os.makedirs(INSTALL_DIR, exist_ok=True)

    # 2. Download the ZIP
    print(f"[*] Downloading FluxHive from GitHub...")
    try:
        response = requests.get(ZIP_URL, stream=True, timeout=60)
        if response.status_code == 200:
            with open(ZIP_TEMP_FILE, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            print("[+] Download Complete.")
        else:
            print(f"[-] Error: GitHub returned status {response.status_code}")
            return
    except Exception as e:
        print(f"[-] Download failed: {e}")
        return

    # 3. Unzip the contents
    print("[*] Extracting files into current folder...")
    try:
        with zipfile.ZipFile(ZIP_TEMP_FILE, 'r') as zip_ref:
            zip_ref.extractall(INSTALL_DIR)
        print("[+] Extraction successful.")
    except Exception as e:
        print(f"[-] Extraction failed: {e}")
        return
    finally:
        # 4. Clean up
        if ZIP_TEMP_FILE.exists():
            os.remove(ZIP_TEMP_FILE)
            print("[*] Cleaned up temporary files.")

    # 5. Launch
    print(f"\n[SUCCESS] FluxHive is ready.")
    if TARGET_EXE.exists():
        print("[*] Starting Launcher...")
        time.sleep(1)
        os.startfile(TARGET_EXE)
    else:
        print(f"[-] Error: {TARGET_EXE.name} not found. Check ZIP structure.")
        input("Press Enter to close...")
a
if __name__ == "__main__":
    install()
