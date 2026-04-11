import os
import sys
import time
import zipfile
import requests
from pathlib import Path

# --- CONFIG ---
# Direct link to your newly created release zip
ZIP_URL = "https://github.com/hefe00935/FluxHive-Launcher/releases/download/Release/FluxHive.zip"

# Installation Path
INSTALL_DIR = Path(os.path.expanduser("~")) / "Downloads" / "FluxHive-Launcher"
ZIP_TEMP_FILE = INSTALL_DIR / "FluxHive_Package.zip"
TARGET_EXE = INSTALL_DIR / "FluxHive.exe"

def install():
    print("--- FluxHive Release Installer ---")
    
    # 1. Prepare Directory
    if not INSTALL_DIR.exists():
        os.makedirs(INSTALL_DIR, exist_ok=True)
        print(f"[*] Created directory: {INSTALL_DIR}")

    # 2. Download the ZIP
    print(f"[*] Downloading FluxHive.zip...")
    try:
        response = requests.get(ZIP_URL, stream=True, timeout=60)
        if response.status_code == 200:
            with open(ZIP_TEMP_FILE, "wb") as f:
                # 1MB chunks for faster writing
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
    print("[*] Extracting files...")
    try:
        with zipfile.ZipFile(ZIP_TEMP_FILE, 'r') as zip_ref:
            # This extracts everything into the INSTALL_DIR
            zip_ref.extractall(INSTALL_DIR)
        print("[+] Extraction successful.")
    except Exception as e:
        print(f"[-] Extraction failed: {e}")
        return
    finally:
        # 4. Clean up the zip file
        if ZIP_TEMP_FILE.exists():
            os.remove(ZIP_TEMP_FILE)
            print("[*] Cleaned up temporary files.")

    # 5. Launch
    print(f"\n[SUCCESS] FluxHive is ready at: {INSTALL_DIR}")
    print("[*] Starting Launcher...")
    time.sleep(1)

    if TARGET_EXE.exists():
        os.startfile(TARGET_EXE)
    else:
        print(f"[-] Error: Could not find {TARGET_EXE.name} after extraction.")
        print("Check if the EXE is named correctly inside your ZIP.")

if __name__ == "__main__":
    install()