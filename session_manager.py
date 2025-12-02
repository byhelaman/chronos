"""
Chronos - Session Manager
Gestiona persistencia de sesiones para evitar login repetido
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict
from supabase import Client, create_client
from config_manager import config_manager


class SessionManager:
    """Gestor de persistencia de sesión"""
    
    # Configuración
    SESSION_FILE = ".session"  # Archivo oculto en el directorio de la app
    SESSION_DURATION_DAYS = 7  # Duración de la sesión (7 días por defecto)
    
    def __init__(self):
        self.session_path = self._get_session_path()
    
    def _get_session_path(self) -> Path:
        """Obtiene la ruta del archivo de sesión"""
        # Usar directorio de datos del usuario para persistencia
        # Esto funciona tanto en desarrollo como en .exe
        if os.name == 'nt':  # Windows
            app_data = os.getenv('APPDATA')
            if not app_data:
                app_data = os.path.expanduser('~')
            base_dir = Path(app_data) / 'Chronos'
        else:  # Linux/Mac
            base_dir = Path.home() / '.chronos'
        
        # Crear directorio si no existe
        base_dir.mkdir(parents=True, exist_ok=True)
        
        return base_dir / self.SESSION_FILE
    
    def save_session(self, supabase: Client, user_info: Dict, config: Dict) -> None:
        """
        Guarda la sesión actual para uso futuro
        
        Args:
            supabase: Cliente autenticado de Supabase
            user_info: Información del usuario
            config: Configuración descifrada
        """
        try:
            # Obtener el token de acceso actual
            session = supabase.auth.get_session()
            
            if not session:
                return
            
            # Datos a guardar
            session_data = {
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "expires_at": session.expires_at,
                "user_info": user_info,
                "saved_at": datetime.now().isoformat(),
                "expires_session_at": (datetime.now() + timedelta(days=self.SESSION_DURATION_DAYS)).isoformat()
            }
            
            # Cifrar y guardar
            encrypted_session = config_manager.encrypt_value(json.dumps(session_data))
            
            with open(self.session_path, 'w') as f:
                f.write(encrypted_session)
            
            print(f"✓ Session saved (expires in {self.SESSION_DURATION_DAYS} days)")
        
        except Exception as e:
            print(f"Warning: Could not save session: {e}")
    
    def load_session(self) -> Optional[tuple[Client, Dict, Dict]]:
        """
        Carga y valida una sesión guardada
        
        Returns:
            Tuple (supabase_client, user_info, config) si la sesión es válida
            None si no hay sesión o expiró
        """
        try:
            # Verificar si existe el archivo
            if not self.session_path.exists():
                return None
            
            # Leer y descifrar
            with open(self.session_path, 'r') as f:
                encrypted_session = f.read()
            
            session_json = config_manager.decrypt_value(encrypted_session)
            session_data = json.loads(session_json)
            
            # Verificar expiración de la sesión guardada
            expires_session_at = datetime.fromisoformat(session_data["expires_session_at"])
            if datetime.now() > expires_session_at:
                print("Session expired, please login again")
                self.clear_session()
                return None
            
            # Crear cliente con el token guardado
            from auth_manager import auth_manager
            supabase = create_client(
                auth_manager.SUPABASE_URL,
                auth_manager.SUPABASE_ANON_KEY
            )
            
            # Restaurar sesión en Supabase
            # Primero intentar con el access_token actual
            try:
                # Supabase maneja automáticamente el refresh si es necesario
                supabase.auth.set_session(
                    access_token=session_data["access_token"],
                    refresh_token=session_data["refresh_token"]
                )
                
                # Verificar que la sesión sigue siendo válida
                current_session = supabase.auth.get_session()
                if not current_session:
                    print("Session invalid, please login again")
                    self.clear_session()
                    return None
                
            except Exception as e:
                print(f"Could not restore session: {e}")
                self.clear_session()
                return None
            
            # Cargar configuración desde la base de datos
            config = config_manager.fetch_config_from_db(supabase)
            
            user_info = session_data["user_info"]
            
            print(f"✓ Session restored for {user_info.get('email', 'user')}")
            return supabase, user_info, config
        
        except Exception as e:
            print(f"Error loading session: {e}")
            self.clear_session()
            return None
    
    def clear_session(self) -> None:
        """Elimina la sesión guardada"""
        try:
            if self.session_path.exists():
                self.session_path.unlink()
                print("✓ Session cleared")
        except Exception as e:
            print(f"Error clearing session: {e}")
    
    def has_saved_session(self) -> bool:
        """Verifica si existe una sesión guardada"""
        return self.session_path.exists()


# Instancia global del gestor
session_manager = SessionManager()
