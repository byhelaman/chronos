"""
Chronos - Config Manager
Gestiona configuración cifrada almacenada en Supabase
"""

from cryptography.fernet import Fernet
from supabase import Client
from typing import Dict, Optional
import base64
import hashlib

# Clave maestra para cifrado (derivada de un secreto)
# NOTA: En producción, esta clave debería ser más compleja y estar ofuscada
# Para máxima seguridad, considera usar un KDF (Key Derivation Function)
MASTER_SECRET = "chronos_secure_key_2024_v1"  # Cambiar en producción


class ConfigManager:
    """Gestor de configuración cifrada"""
    
    def __init__(self):
        self._fernet = self._create_cipher()
        self._config_cache: Dict[str, str] = {}
    
    def _create_cipher(self) -> Fernet:
        """Crea instancia de Fernet con clave derivada del secreto maestro"""
        # Derivar clave de 32 bytes desde el secreto maestro
        key_bytes = hashlib.sha256(MASTER_SECRET.encode()).digest()
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        return Fernet(key_b64)
    
    def encrypt_value(self, value: str) -> str:
        """Cifra un valor usando Fernet (AES-256)"""
        if not value:
            return ""
        encrypted_bytes = self._fernet.encrypt(value.encode())
        return encrypted_bytes.decode()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """Descifra un valor previamente cifrado"""
        if not encrypted_value:
            return ""
        try:
            decrypted_bytes = self._fernet.decrypt(encrypted_value.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            raise ValueError(f"Error decrypting value: {str(e)}")
    
    def fetch_config_from_db(self, supabase: Client) -> Dict[str, str]:
        """
        Descarga y descifra toda la configuración desde Supabase
        
        Returns:
            Dict con pares key-value descifrados
        """
        try:
            # Obtener todos los registros de configuración
            response = supabase.table("app_config").select("key, value_encrypted").execute()
            
            if not response.data:
                raise Exception("No configuration found in database")
            
            # Descifrar y cachear
            config = {}
            for item in response.data:
                key = item["key"]
                encrypted_value = item["value_encrypted"]
                decrypted_value = self.decrypt_value(encrypted_value)
                config[key] = decrypted_value
                self._config_cache[key] = decrypted_value
            
            return config
        
        except Exception as e:
            raise Exception(f"Error fetching config from database: {str(e)}")
    
    def save_config_to_db(self, supabase: Client, config: Dict[str, str]) -> None:
        """
        Cifra y guarda configuración en Supabase
        
        Args:
            supabase: Cliente autenticado de Supabase
            config: Dict con pares key-value a guardar (en texto plano)
        """
        try:
            for key, value in config.items():
                encrypted_value = self.encrypt_value(value)
                
                # Upsert (insert o update si ya existe)
                supabase.table("app_config").upsert({
                    "key": key,
                    "value_encrypted": encrypted_value
                }).execute()
            
            print(f"✓ Saved {len(config)} configuration items to database")
        
        except Exception as e:
            raise Exception(f"Error saving config to database: {str(e)}")
    
    def get_config_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Obtiene un valor de configuración del cache"""
        return self._config_cache.get(key, default)
    
    def clear_cache(self) -> None:
        """Limpia el cache de configuración (seguridad al cerrar app)"""
        self._config_cache.clear()
    
    def validate_config(self, config: Dict[str, str]) -> bool:
        """
        Valida que la configuración tenga todas las claves necesarias
        
        Returns:
            True si la configuración es válida
        """
        required_keys = ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"]
        
        for key in required_keys:
            if key not in config or not config[key]:
                return False
        
        return True


# Instancia global del gestor
config_manager = ConfigManager()
