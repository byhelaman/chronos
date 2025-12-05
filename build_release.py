"""
Chronos - Build & Release Script
Automatiza la compilación y preparación de releases.
"""

import os
import json
import shutil
import subprocess
import re
from datetime import datetime

# Configuración
APP_NAME = "Chronos"
MAIN_SCRIPT = "main.py"
VERSION_FILE = "version_manager.py"
DIST_DIR = "dist"
BUILD_DIR = "build"
ICON_FILE = "favicon.ico"

def get_current_version():
    """Lee la versión actual de version_manager.py"""
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'CURRENT_VERSION\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
    return "0.0.0"

def update_version_file(new_version):
    """Actualiza la versión en version_manager.py"""
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = re.sub(
        r'CURRENT_VERSION\s*=\s*"[^"]+"',
        f'CURRENT_VERSION = "{new_version}"',
        content
    )
    
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)



def main():
    print("--- CHRONOS BUILD & RELEASE ---")
    
    current_ver = get_current_version()
    print(f"Current Version: {current_ver}")
    
    new_ver = input(f"Enter new version (default {current_ver}): ").strip()
    if not new_ver:
        new_ver = current_ver
        
    print(f"Target Version: {new_ver}")
    
    # 1. Update Version File
    update_version_file(new_ver)
    print("✓ Updated version_manager.py")
    
    # 2. Clean previous builds
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
        
    # 3. Run PyInstaller
    print("Building executable... (this may take a while)")
    
    # Argumentos de PyInstaller
    args = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", f"{APP_NAME}",
        "--clean",
        "--noupx",  # No usar UPX - mejora tiempo de inicio
        "--add-data", f"{ICON_FILE};.", # Bundle icon
        # Hidden imports necesarios
        "--hidden-import", "pandas",
        "--hidden-import", "babel.numbers",
        "--hidden-import", "httpx",
        "--hidden-import", "pyqt6",
        # Excluir módulos pesados no utilizados (reduce tamaño y tiempo de carga)
        "--exclude-module", "matplotlib",
        "--exclude-module", "tkinter",
        "--exclude-module", "scipy",
        "--exclude-module", "notebook",
        "--exclude-module", "ipython",
        "--exclude-module", "jedi",
        "--exclude-module", "PIL",
        "--exclude-module", "test",
        "--exclude-module", "unittest",
        MAIN_SCRIPT
    ]
    
    # Usar icono para el ejecutable
    if os.path.exists(ICON_FILE):
        args.extend(["--icon", ICON_FILE])
    
    subprocess.check_call(args)
    print("✓ Build complete")
    
    # 4. Rename and Prepare Release
    original_exe = os.path.join(DIST_DIR, f"{APP_NAME}.exe")
    release_filename = f"{APP_NAME}_v{new_ver}.exe"
    release_exe = os.path.join(DIST_DIR, release_filename)
    
    if os.path.exists(original_exe):
        os.rename(original_exe, release_exe)
        print(f"✓ Renamed to {release_filename}")
        
        print("\n--- BUILD SUCCESSFUL ---")
        print(f"File created: {release_exe}")
        print("\nNEXT STEPS (GitHub Releases):")
        print(f"1. Commit and push your changes (including version_manager.py)")
        print(f"2. Go to: https://github.com/byhelaman/chronos/releases/new")
        print(f"3. Create a new release with tag: v{new_ver}")
        print(f"4. Upload the file: {release_filename}")
        print(f"5. Publish release!")
    else:
        print("Error: Executable not found!")

if __name__ == "__main__":
    main()
