"""
Chronos - Setup Admin Script (Simplified)
Migra credenciales de .env a Supabase y crea usuario admin.
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
from config_manager import config_manager
import getpass

def main():
    print("--- CHRONOS SETUP ---")

    # 1. Cargar .env
    if not os.path.exists(".env"):
        print("Error: .env no encontrado.")
        sys.exit(1)
    
    load_dotenv()
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    ZOOM_CLIENT_ID = os.getenv("CLIENT_ID")
    ZOOM_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    
    if not all([SUPABASE_URL, SUPABASE_KEY, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET]):
        print("Error: Faltan variables en .env")
        sys.exit(1)
        
    print("✓ Credenciales cargadas")

    # 2. Conectar Supabase
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✓ Conectado a Supabase")
    except Exception as e:
        print(f"Error conectando a Supabase: {e}")
        sys.exit(1)

    # 3. Subir Configuración
    config = {
        "ZOOM_CLIENT_ID": ZOOM_CLIENT_ID,
        "ZOOM_CLIENT_SECRET": ZOOM_CLIENT_SECRET
    }
    
    try:
        config_manager.save_config_to_db(supabase, config)
        print("✓ Configuración cifrada y guardada")
    except Exception as e:
        print(f"Error guardando configuración: {e}")
        sys.exit(1)

    # 4. Crear Admin
    print("\nCrear Usuario Administrador:")
    email = input("Email: ").strip()
    password = getpass.getpass("Password (min 6 chars): ")
    
    if len(password) < 6:
        print("Error: Password muy corto.")
        sys.exit(1)

    try:
        # Crear en Auth
        auth_resp = supabase.auth.sign_up({"email": email, "password": password})
        
        if auth_resp.user:
            user_id = auth_resp.user.id
            print(f"✓ Usuario Auth creado: {user_id}")
            
            # Autorizar
            supabase.table("authorized_users").upsert({
                "user_id": user_id,
                "role": "admin",
                "created_by": user_id
            }).execute()
            print("✓ Usuario autorizado como Admin")
        else:
            # Si ya existe, intentar solo autorizar (necesitamos el ID)
            # Nota: sign_up suele loguear si ya existe o devolver error, depende config.
            # Asumimos flujo simple.
            print("Nota: El usuario podría ya existir.")
            
    except Exception as e:
        print(f"Error creando/autorizando usuario: {e}")

    print("\n--- SETUP FINALIZADO ---")

if __name__ == "__main__":
    main()
