"""
Chronos - Zoom Service
Servicio para interacción con la API de Zoom.
"""

import base64
import logging
from datetime import datetime
from typing import Optional

import httpx
from supabase import Client

from app.config import config


logger = logging.getLogger(__name__)


class ZoomService:
    """Servicio singleton para manejar operaciones de Zoom."""
    
    _instance: Optional['ZoomService'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._client_id: Optional[str] = None
        self._client_secret: Optional[str] = None
        self._initialized = True
    
    def set_credentials(self, client_id: str, client_secret: str) -> None:
        """Establece las credenciales de Zoom."""
        self._client_id = client_id
        self._client_secret = client_secret
        logger.info("Zoom credentials configured")
    
    @property
    def client_id(self) -> Optional[str]:
        return self._client_id
    
    @property
    def client_secret(self) -> Optional[str]:
        return self._client_secret
    
    @property
    def is_configured(self) -> bool:
        """Verifica si las credenciales están configuradas."""
        return bool(self._client_id and self._client_secret)
    
    def refresh_token(self, supabase: Client) -> str:
        """
        Refresca el token de Zoom usando el refresh_token almacenado.
        
        Args:
            supabase: Cliente de Supabase autenticado
            
        Returns:
            Nuevo access_token
            
        Raises:
            Exception: Si no hay credenciales o falla el refresh
        """
        logger.debug("Refreshing Zoom Token...")
        
        # 1. Obtener refresh_token actual
        resp = supabase.table("zoom_tokens").select("id, refresh_token").limit(1).execute()
        if not resp.data:
            raise Exception("No token record found in DB")
        
        record = resp.data[0]
        refresh_token = record.get("refresh_token")
        
        if not refresh_token:
            raise Exception("No refresh_token found in DB")
            
        if not self._client_id or not self._client_secret:
            raise Exception("Missing Zoom CLIENT_ID or CLIENT_SECRET")
            
        # 2. Llamar a Zoom API
        url = "https://zoom.us/oauth/token"
        
        # Basic Auth Header
        auth_str = f"{self._client_id}:{self._client_secret}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        response = httpx.post(url, headers=headers, data=data, timeout=10.0)
        
        if response.status_code != 200:
            logger.error(f"Failed to refresh token: {response.text}")
            raise Exception(f"Failed to refresh token: {response.text}")
            
        new_tokens = response.json()
        new_access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens.get("refresh_token", refresh_token)
        
        # 3. Actualizar DB
        supabase.table("zoom_tokens").update({
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "updated_at": datetime.now().isoformat()
        }).eq("id", record["id"]).execute()
        
        logger.info("Zoom token refreshed successfully")
        return new_access_token
    
    def update_meeting_host(
        self, 
        access_token: str, 
        meeting_id: str, 
        new_host_email: str
    ) -> dict:
        """
        Actualiza el host de una reunión de Zoom.
        
        Args:
            access_token: Token de acceso de Zoom
            meeting_id: ID de la reunión
            new_host_email: Email del nuevo host
            
        Returns:
            Respuesta de la API
        """
        url = f"https://api.zoom.us/v2/meetings/{meeting_id}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "schedule_for": new_host_email
        }
        
        response = httpx.patch(url, headers=headers, json=data, timeout=10.0)
        
        if response.status_code not in [200, 204]:
            logger.error(f"Failed to update meeting {meeting_id}: {response.text}")
            raise Exception(f"Failed to update meeting: {response.text}")
        
        logger.debug(f"Meeting {meeting_id} host updated to {new_host_email}")
        return {"success": True, "meeting_id": meeting_id}

    def create_meeting(
        self,
        access_token: str,
        user_id: str,
        topic: str,
        start_time: str,
        duration: int = 60,
        recurrence: Optional[dict] = None
    ) -> dict:
        """
        Crea una nueva reunión de Zoom.
        
        Args:
            access_token: Token de acceso
            user_id: ID del usuario (o 'me')
            topic: Tema de la reunión
            start_time: Hora de inicio (ISO 8601)
            duration: Duración en minutos
            recurrence: Configuración de recurrencia (opcional)
            
        Returns:
            Datos de la reunión creada
        """
        url = f"https://api.zoom.us/v2/users/{user_id}/meetings"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "topic": topic,
            "type": 8 if recurrence else 2,  # 8=Recurring with fixed time, 2=Scheduled
            "start_time": start_time,
            "duration": duration,
            "timezone": "America/Lima",  # Default timezone
            "settings": {
                "host_video": False,
                "participant_video": False,
                "join_before_host": True,
                "mute_upon_entry": True,
                "waiting_room": False
            }
        }
        
        if recurrence:
            data["recurrence"] = recurrence
            
        response = httpx.post(url, headers=headers, json=data, timeout=15.0)
        
        if response.status_code != 201:
            logger.error(f"Failed to create meeting: {response.text}")
            raise Exception(f"Failed to create meeting: {response.text}")
            
        return response.json()


# Instancia global del servicio
zoom_service = ZoomService()
