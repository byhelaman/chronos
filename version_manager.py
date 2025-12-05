"""
Chronos - Version Manager
Gestiona la verificación y descarga de actualizaciones automáticas.
"""

import os
import sys
import json
import httpx
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from typing import Optional, Dict

# Versión actual de la aplicación
CURRENT_VERSION = "0.1.4"

def parse_version(v: str) -> tuple:
    """Parsea versión 'X.Y.Z' a tupla de enteros para comparación."""
    try:
        return tuple(map(int, v.split(".")))
    except ValueError:
        return (0, 0, 0)

class VersionManager(QObject):
    """Gestor de versiones y actualizaciones"""
    
    # Señales
    update_available = pyqtSignal(str, str, str) # version, url, notes
    no_update = pyqtSignal()
    error = pyqtSignal(str)
    download_progress = pyqtSignal(int)
    download_complete = pyqtSignal(str) # path to downloaded file
    
    # Configuración de GitHub Releases
    REPO_OWNER = "byhelaman"
    REPO_NAME = "chronos"
    GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    
    def __init__(self):
        super().__init__()
        self._download_thread = None

    def check_for_updates(self):
        """Inicia la verificación de actualizaciones en segundo plano"""
        thread = CheckUpdateThread(self.GITHUB_API_URL, CURRENT_VERSION)
        thread.update_found.connect(self.update_available.emit)
        thread.no_update.connect(self.no_update.emit)
        thread.error.connect(self.error.emit)
        thread.start()
        # Mantener referencia para evitar garbage collection
        self._check_thread = thread

    def check_for_update_sync(self) -> Optional[Dict]:
        """
        Synchronous update check for blocking startup.
        Returns dict with {version, url, notes} if update available, None otherwise.
        """
        try:
            with httpx.Client() as client:
                response = client.get(self.GITHUB_API_URL, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                tag_name = data.get("tag_name", "").lstrip("v")
                body = data.get("body", "")
                assets = data.get("assets", [])
                
                if not tag_name or not assets:
                    return None
                
                # Find .exe asset
                download_url = None
                for asset in assets:
                    if asset["name"].endswith(".exe"):
                        download_url = asset["browser_download_url"]
                        break
                
                if not download_url:
                    return None
                
                # Compare versions
                if parse_version(tag_name) > parse_version(CURRENT_VERSION):
                    return {"version": tag_name, "url": download_url, "notes": body}
                
                return None
                
        except Exception as e:
            print(f"Update check failed: {e}")
            return None  # Allow app to continue if check fails

    def download_update(self, url: str):
        """Descarga la actualización"""
        self._download_thread = DownloadThread(url)
        self._download_thread.progress.connect(self.download_progress.emit)
        self._download_thread.finished.connect(self.download_complete.emit)
        self._download_thread.error.connect(self.error.emit)
        self._download_thread.start()

    def apply_update(self, new_file_path: str):
        """
        Aplica la actualización:
        1. Genera script de reemplazo
        2. Ejecuta script
        3. Cierra la aplicación actual
        """
        try:
            exe_path = sys.executable
            exe_dir = os.path.dirname(exe_path)
            
            # Nombre del script de actualización
            updater_script = os.path.join(exe_dir, "updater.bat")
            
            # Script batch para reemplazar el archivo
            # Espera 2 segundos, intenta borrar el exe actual, renombra el nuevo, y reinicia
            batch_content = f"""
@echo off
timeout /t 2 /nobreak > NUL
:loop
del "{exe_path}"
if exist "{exe_path}" goto loop
move "{new_file_path}" "{exe_path}"
start "" "{exe_path}"
del "%~f0"
            """
            
            with open(updater_script, "w") as f:
                f.write(batch_content)
                
            # Ejecutar script y salir
            subprocess.Popen([updater_script], shell=True)
            sys.exit(0)
            
        except Exception as e:
            self.error.emit(f"Error applying update: {e}")


class CheckUpdateThread(QThread):
    """Hilo para verificar actualizaciones sin bloquear UI"""
    update_found = pyqtSignal(str, str, str)
    no_update = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, url, current_version):
        super().__init__()
        self.url = url
        self.current_version = current_version
        
    def run(self):
        try:
            with httpx.Client() as client:
                response = client.get(self.url, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                # Obtener versión del tag (ej: "v1.0.2" -> "1.0.2")
                tag_name = data.get("tag_name", "").lstrip("v")
                body = data.get("body", "") # Release notes
                assets = data.get("assets", [])
                
                if not tag_name or not assets:
                    raise Exception("Invalid release info from GitHub")
                
                # Buscar el asset del ejecutable (.exe)
                download_url = None
                for asset in assets:
                    if asset["name"].endswith(".exe"):
                        download_url = asset["browser_download_url"]
                        break
                
                if not download_url:
                    raise Exception("No executable found in the latest release")
                
                # Comparar versiones
                if parse_version(tag_name) > parse_version(self.current_version):
                    self.update_found.emit(tag_name, download_url, body)
                else:
                    self.no_update.emit()
                
        except Exception as e:
            self.error.emit(f"Update check failed: {str(e)}")


class DownloadThread(QThread):
    """Hilo para descargar el archivo"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        
    def run(self):
        try:
            # Configurar cliente para seguir redirects (GitHub usa 302 para assets)
            with httpx.Client(follow_redirects=True) as client:
                with client.stream("GET", self.url, timeout=30) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    # Guardar como archivo temporal
                    temp_path = "update_temp.exe"
                    
                    with open(temp_path, 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    percent = int((downloaded / total_size) * 100)
                                    self.progress.emit(percent)
                            
            self.finished.emit(os.path.abspath(temp_path))
            
        except Exception as e:
            self.error.emit(str(e))

# Instancia global
version_manager = VersionManager()
