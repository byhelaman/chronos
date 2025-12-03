"""
Chronos - Auth Manager
Gestiona autenticación de usuarios con Supabase Auth
"""

from supabase import create_client, Client
from typing import Optional, Tuple, Dict, List
import os
import json


class AuthManager:
    """Gestor de autenticación con Supabase"""
    
    # Credenciales públicas de Supabase (seguras para estar en el ejecutable)
    SUPABASE_URL = "https://cckrbcuzhglhnxwrpilt.supabase.co"
    SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNja3JiY3V6aGdsaG54d3JwaWx0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ3Nzc1NDAsImV4cCI6MjA4MDM1MzU0MH0.-bO7CbzAoZu9bOipUwSjC1d6u1dd8867yUV_eSXyyqo"
    
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
        Obtiene información del usuario autorizado incluyendo permisos
        
        Returns:
            Dict con información del usuario (role, email, permissions, etc.)
        """
        try:
            # Obtener info de authorized_users y su rol asociado
            # Nota: Supabase-py no soporta joins anidados complejos fácilmente en una query fluida simple
            # sin configurar foreign keys explícitas en el cliente a veces.
            # Haremos dos queries por simplicidad y robustez inicial.
            
            # 1. Obtener usuario y rol
            auth_resp = supabase.table("authorized_users")\
                .select("role, custom_permissions")\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            
            if not auth_resp.data:
                return {"id": user_id, "role": "user", "permissions": []}
                
            role_name = auth_resp.data.get("role", "user")
            custom_perms = auth_resp.data.get("custom_permissions", []) or []
            
            # 2. Obtener permisos del rol
            role_resp = supabase.table("roles")\
                .select("permissions")\
                .eq("name", role_name)\
                .single()\
                .execute()
                
            role_perms = role_resp.data.get("permissions", []) if role_resp.data else []
            
            # 3. Combinar permisos (set para eliminar duplicados)
            all_permissions = list(set(role_perms + custom_perms))
            
            # Combinar con info de auth.users
            user_data = {
                "id": user_id,
                "email": self._current_user.email if self._current_user else "",
                "role": role_name,
                "permissions": all_permissions
            }
            
            return user_data
        
        except Exception as e:
            print(f"Error getting user info: {e}")
            return {
                "id": user_id,
                "email": self._current_user.email if self._current_user else "",
                "role": "user",
                "permissions": []
            }

    def has_permission(self, permission: str) -> bool:
        """
        Verifica si el usuario actual tiene un permiso específico
        """
        if not self._current_user:
            return False
            
        # Si ya tenemos la info del usuario cargada en memoria (podríamos optimizar esto)
        # Por ahora, asumimos que get_user_info se llama al login y podríamos guardar el resultado.
        # Pero auth_manager no guarda el user_info completo en self, solo _current_user (auth).
        # Para evitar llamadas a DB en cada check, deberíamos cachear los permisos.
        # Por simplicidad en esta iteración, consultamos get_user_info si tenemos el cliente.
        
        if not self._supabase:
            return False
            
        try:
            user_info = self.get_user_info(self._supabase, self._current_user.id)
            return permission in user_info.get("permissions", [])
        except:
            return False

    def get_permissions(self) -> List[str]:
        """Retorna la lista de permisos del usuario actual"""
        if not self._supabase or not self._current_user:
            return []
            
        try:
            user_info = self.get_user_info(self._supabase, self._current_user.id)
            return user_info.get("permissions", [])
        except:
            return []
    
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

    def get_all_users(self) -> List[Dict]:
        """
        Obtiene todos los usuarios autorizados.
        Requiere permisos de administrador (gestionado por RLS).
        """
        if not self._supabase:
            return []
            
        try:
            # Obtener usuarios de authorized_users
            response = self._supabase.table("authorized_users")\
                .select("user_id, role, custom_permissions")\
                .execute()
            
            users = response.data
            
            # Intentar enriquecer con emails si es posible (ej. desde zoom_users si hay sync)
            # O si tuviéramos acceso a una vista segura de auth.users
            # Por ahora, devolvemos lo que tenemos
            return users
            
        except Exception as e:
            print(f"Error fetching users: {e}")
            return []

    def update_user_role(self, user_id: str, new_role: str) -> bool:
        """
        Actualiza el rol de un usuario.
        """
        if not self._supabase:
            return False
            
        try:
            self._supabase.table("authorized_users")\
                .update({"role": new_role})\
                .eq("user_id", user_id)\
                .execute()
            return True
        except Exception as e:
            print(f"Error updating user role: {e}")
            return False


# Instancia global del gestor
auth_manager = AuthManager()
