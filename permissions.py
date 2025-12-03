"""
Chronos - Permissions Definitions
Define los permisos granulares y los roles por defecto.
"""

# --- Permission Constants ---

# Assignment Permissions
ASSIGNMENT_AUTO = "assignment:auto"        # Acceso a asignación automática
ASSIGNMENT_MANUAL = "assignment:manual"    # Acceso a asignación manual
ASSIGNMENT_VIEW = "assignment:view"        # Ver asignaciones

# Meeting Permissions
MEETING_SEARCH = "meeting:search"          # Buscar reuniones
MEETING_CREATE = "meeting:create"          # Crear reuniones
MEETING_UPDATE = "meeting:update"          # Actualizar reuniones
MEETING_DELETE = "meeting:delete"          # Eliminar reuniones

# User Management Permissions
USER_MANAGE = "user:manage"                # Gestionar usuarios (admin)
USER_VIEW = "user:view"                    # Ver usuarios

# System Permissions
SYSTEM_CONFIG = "system:config"            # Configuración del sistema
SYSTEM_LOGS = "system:logs"                # Ver logs

# --- Default Roles Configuration ---

DEFAULT_ROLES = {
    "admin": [
        ASSIGNMENT_AUTO,
        ASSIGNMENT_MANUAL,
        ASSIGNMENT_VIEW,
        MEETING_SEARCH,
        MEETING_CREATE,
        MEETING_UPDATE,
        MEETING_DELETE,
        USER_MANAGE,
        USER_VIEW,
        SYSTEM_CONFIG,
        SYSTEM_LOGS
    ],
    "user": [
        ASSIGNMENT_VIEW,
        MEETING_SEARCH,
        MEETING_CREATE,
        MEETING_UPDATE
    ],
    "viewer": [
        ASSIGNMENT_VIEW,
        MEETING_SEARCH
    ]
}
