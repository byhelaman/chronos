"""
Chronos - Auth Manager
Gestiona autenticación de usuarios con Supabase Auth
"""

from supabase import create_client, Client
from typing import Optional, Tuple, Dict
import os


class AuthManager:
    """Gestor de autenticación con Supabase"""
    
    # Credenciales públicas de Supabase (seguras para estar en el ejecutable)
    SUPABASE_URL = "https://glsefcxnncgzujvfkete.supabase.co"
    SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdsc2VmY3hubmNnenVqdmZrZXRlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQxOTU0MzgsImV4cCI6MjA3OTc3MTQzOH0.QFBHQIK-E1dyHveWcq_vn4zgvsgcsRmE4E5i4NFCM1k"
    
    def __init__(self):
        self._supabase: Optional[Client] = None
        self._current_user: Optional[Dict] = None
    
    def login(self, email: str, password: str) -> Tuple[Client, Dict]:
        """
        Autentica usuario con email y password
        
        Args:
            email: Email del usuario
            password: Contraseña del usuario
        
        Returns:
            Tuple (supabase_client, user_data)
        
        Raises:
            Exception: Si las credenciales son inválidas o el usuario no está autorizado
        """
        try:
            # Crear cliente de Supabase
            supabase = create_client(self.SUPABASE_URL, self.SUPABASE_ANON_KEY)
            
            # Intentar autenticación
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not auth_response.user:
                raise Exception("Invalid credentials")
            
            user = auth_response.user
            self._supabase = supabase
            self._current_user = user
            
            # Verificar si el usuario está autorizado
            if not self.is_user_authorized(supabase, user.id):
                raise Exception("User not authorized to access this application")
            
            # Obtener información adicional del usuario
            user_info = self.get_user_info(supabase, user.id)
            
            return supabase, user_info
        
        except Exception as e:
            error_msg = str(e)
            # Mensajes de error más amigables
            if "Invalid login credentials" in error_msg or "Invalid credentials" in error_msg:
                raise Exception("Incorrect email or password")
            elif "not authorized" in error_msg:
                raise Exception("You are not authorized to access this application")
            else:
                raise Exception(f"Login error: {error_msg}")
    
    def is_user_authorized(self, supabase: Client, user_id: str) -> bool:
        """
        Verifica si un usuario está en la lista de usuarios autorizados
        
        Args:
            supabase: Cliente autenticado de Supabase
            user_id: ID del usuario a verificar
        
        Returns:
            True si el usuario está autorizado
        """
        try:
            response = supabase.table("authorized_users")\
                .select("user_id")\
                .eq("user_id", user_id)\
                .execute()
            
            return len(response.data) > 0
        
        except Exception as e:
            print(f"Error checking user authorization: {e}")
            return False
    
    def get_user_info(self, supabase: Client, user_id: str) -> Dict:
        """
        Obtiene información del usuario autorizado
        
        Returns:
            Dict con información del usuario (role, email, etc.)
        """
        try:
            # Obtener info de authorized_users
            auth_resp = supabase.table("authorized_users")\
                .select("role")\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            
            # Combinar con info de auth.users
            user_data = {
                "id": user_id,
                "email": self._current_user.email if self._current_user else "",
                "role": auth_resp.data.get("role", "user") if auth_resp.data else "user"
            }
            
            return user_data
        
        except Exception as e:
            print(f"Error getting user info: {e}")
            return {
                "id": user_id,
                "email": self._current_user.email if self._current_user else "",
                "role": "user"
            }
    
    def logout(self, supabase: Client) -> None:
        """Cierra sesión del usuario actual"""
        try:
            supabase.auth.sign_out()
            self._supabase = None
            self._current_user = None
        except Exception as e:
            print(f"Error during logout: {e}")
    
    def get_current_user(self) -> Optional[Dict]:
        """Retorna información del usuario actual"""
        return self._current_user
    
    def set_client(self, client: Client) -> None:
        """Establece el cliente de Supabase autenticado"""
        self._supabase = client
        # Intentar obtener el usuario si no está seteado
        if not self._current_user:
            try:
                self._current_user = client.auth.get_user().user
            except:
                pass

    def get_client(self) -> Client:
        """Obtiene el cliente de Supabase actual"""
        if not self._supabase:
            # Si no hay cliente autenticado, lanzar error claro
            raise Exception(
                "No authenticated Supabase client available. "
                "This usually means the user session has not been initialized. "
                "Please ensure auth_manager.set_client() is called after login."
            )
        return self._supabase

    @classmethod
    def create_supabase_client(cls) -> Client:
        """Crea un cliente de Supabase sin autenticación (para uso público)"""
        return create_client(cls.SUPABASE_URL, cls.SUPABASE_ANON_KEY)


# Instancia global del gestor
auth_manager = AuthManager()
