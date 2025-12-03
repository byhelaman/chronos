"""
Chronos - Master your Time
Versión optimizada con PyQt6 para máxima performance y seguridad
"""

import sys
import os
from dataclasses import dataclass, asdict
from typing import List, Optional, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QFileDialog,
    QMessageBox, QProgressBar, QHeaderView, QAbstractItemView, QLineEdit, QMenu,
    QCheckBox, QFrame, QStyledItemDelegate, QStyleOptionViewItem, QStyle, QStyleOptionButton,
    QDialog, QComboBox, QProgressDialog
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QDesktopServices, QAction, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QModelIndex, QRect, QItemSelectionModel, QTimer, QUrl

import pandas as pd
from supabase import create_client, Client
import utils  # Importar utils.py para fuzzy matching
import httpx # Para llamadas a API de Zoom

# Imports del sistema de autenticación
from auth_manager import auth_manager
from config_manager import config_manager
from session_manager import session_manager
from ui_login import LoginDialog
from version_manager import version_manager, CURRENT_VERSION as APP_VERSION

# Imports del sistema de temas y componentes
from theme_manager import theme
from ui_components import SearchBar, FilterChip, ToastNotification, CustomButton

APP_NAME = "Chronos"
# APP_VERSION is now imported from version_manager

# Credenciales de Supabase (públicas, seguras para el ejecutable)
SUPABASE_URL = auth_manager.SUPABASE_URL
SUPABASE_KEY = auth_manager.SUPABASE_ANON_KEY

# Credenciales de Zoom (se cargarán desde DB después del login)
ZOOM_CLIENT_ID = None
ZOOM_CLIENT_SECRET = None


# ============================================================================
# MODELOS (sin cambios)
# ============================================================================

@dataclass
class Schedule:
    """Representa una única entrada de horario."""
    date: str
    shift: str
    area: str
    start_time: str
    end_time: str
    code: str
    instructor: str
    program: str
    minutes: str
    units: int

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

    def to_list(self) -> List:
        """Convierte a lista para exportar/copiar (formato interno/snake_case)."""
        return [
            self.date, self.shift, self.area, self.start_time,
            self.end_time, self.code, self.instructor, self.program,
            self.minutes, str(self.units)
        ]
    
    def to_list_display(self) -> List:
        """Convierte a lista para mostrar en tabla (formato 24h)."""
        return [
            self.date, self.shift, self.area, 
            self._convert_to_24h(self.start_time),
            self._convert_to_24h(self.end_time), 
            self.code, self.instructor, self.program,
            self.minutes, str(self.units)
        ]
    
    def _convert_to_24h(self, time_12h: str) -> str:
        """Convierte hora de formato 12h a 24h."""
        try:
            # Manejar múltiples horarios separados por coma
            if ',' in time_12h:
                times = time_12h.split(',')
                converted = [self._convert_single_time_to_24h(t.strip()) for t in times]
                return ', '.join(converted)
            else:
                return self._convert_single_time_to_24h(time_12h)
        except:
            return time_12h  # Retornar original si hay error
    
    def _convert_single_time_to_24h(self, time_str: str) -> str:
        """Convierte un solo horario de 12h a 24h."""
        try:
            # Remover espacios y convertir a mayúsculas
            time_str = time_str.strip().upper()
            
            # Detectar AM/PM
            is_pm = 'PM' in time_str
            is_am = 'AM' in time_str
            
            # Extraer la hora
            time_clean = time_str.replace('AM', '').replace('PM', '').strip()
            
            # Parsear hora:minutos
            if ':' in time_clean:
                hours, minutes = time_clean.split(':')
                hours = int(hours)
                minutes = int(minutes)
            else:
                hours = int(time_clean)
                minutes = 0
            
            # Convertir a 24h
            if is_pm and hours != 12:
                hours += 12
            elif is_am and hours == 12:
                hours = 0
            
            return f"{hours:02d}:{minutes:02d}"
        except:
            return time_str  # Retornar original si hay error
    
    def __hash__(self):
        """Hash para comparaciones eficientes O(1)."""
        return hash((self.date, self.shift, self.area, self.start_time, 
                     self.end_time, self.code, self.instructor, self.program))
    
    def __eq__(self, other):
        """Comparación de igualdad optimizada."""
        if not isinstance(other, Schedule):
            return False
        return (self.date == other.date and 
                self.shift == other.shift and
                self.area == other.area and
                self.start_time == other.start_time and
                self.end_time == other.end_time and
                self.code == other.code and
                self.instructor == other.instructor and
                self.program == other.program)


import base64

def refresh_zoom_token(supabase: Client) -> str:
    """Refresca el token de Zoom usando el refresh_token almacenado."""
    print("DEBUG: Refreshing Zoom Token...")
    
    # 1. Obtener refresh_token actual
    # Optimización: Seleccionar solo campos necesarios en lugar de *
    resp = supabase.table("zoom_tokens").select("id, refresh_token").limit(1).execute()
    if not resp.data:
        raise Exception("No token record found in DB")
    
    record = resp.data[0]
    refresh_token = record.get("refresh_token")
    
    if not refresh_token:
        raise Exception("No refresh_token found in DB")
        
    if not ZOOM_CLIENT_ID or not ZOOM_CLIENT_SECRET:
        raise Exception("Missing CLIENT_ID or CLIENT_SECRET in .env")
        
    # 2. Llamar a Zoom API
    url = "https://zoom.us/oauth/token"
    
    # Basic Auth Header
    auth_str = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
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
        raise Exception(f"Failed to refresh token: {response.text}")
        
    new_tokens = response.json()
    new_access_token = new_tokens["access_token"]
    new_refresh_token = new_tokens.get("refresh_token", refresh_token) # A veces no rota
    
    # 3. Actualizar DB
    supabase.table("zoom_tokens").update({
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "updated_at": datetime.now().isoformat()
    }).eq("id", record["id"]).execute()
    
    print("DEBUG: Token refreshed successfully")
    return new_access_token

# ============================================================================
# UTILIDADES (copiadas del código original)
# ============================================================================

import re

def extract_parenthesized_schedule(text: str) -> str:
    matches = re.findall(r"\((.*?)\)", str(text))
    return ", ".join(matches) if matches else str(text)

def extract_keyword_from_text(text: str) -> Optional[str]:
    predefined_keywords = ["CORPORATE", "HUB", "LA MOLINA", "BAW", "KIDS"]
    for keyword in predefined_keywords:
        if re.search(rf"\b{keyword}\b", str(text), re.IGNORECASE):
            return keyword
    return None

def filter_special_tags(text: str) -> Optional[str]:
    normalized_text = re.sub(r"\s+", "", text.lower())
    special_tags = {
        re.sub(r"\s+", "", variant).lower()
        for group in [
            "@Corp", "@Lima 2 | lima2 | @Lima Corporate",
            "@LC Bulevar Artigas", "@Argentina"
        ]
        for variant in group.split("|")
    }
    if normalized_text in special_tags:
        return None
    return text

def extract_duration_or_keyword(text: str) -> Optional[str]:
    duration_keywords = ["30", "45", "60", "CEIBAL", "KIDS"]
    for keyword in duration_keywords:
        if keyword in ["CEIBAL", "KIDS"]:
            return "45"
        if keyword == "60" and re.search(rf"\b{keyword}\b", str(text), re.IGNORECASE):
            return "30"
        if re.search(rf"\b{keyword}\b", str(text), re.IGNORECASE):
            return keyword
    return None

def format_time_periods(string: str) -> str:
    return string.replace("a.m.", "AM").replace("p.m.", "PM")

def determine_shift_by_time(start_time: str) -> str:
    try:
        start_time_24h = pd.to_datetime(start_time).strftime("%H:%M")
        return "P. ZUÑIGA" if start_time_24h < "14:00" else "H. GARCIA"
    except Exception:
        return "H. GARCIA"


def parse_excel_file(file_path: str) -> List[Schedule]:
    """Parsea un archivo Excel y extrae una lista de horarios."""
    schedules: List[Schedule] = []

    try:
        with pd.ExcelFile(file_path, engine="openpyxl") as xls:
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name)
                if df.empty:
                    continue

                try:
                    schedule_date = df.iat[0, 14]
                    location = df.iat[0, 21]
                    area_name = extract_keyword_from_text(location) or ""
                    instructor_name = df.iat[4, 0]
                    instructor_code = df.iat[3, 0]
                except Exception:
                    continue

                # Pre-calcular conteos de grupos para evitar O(N^2) dentro del bucle
                # Columna 17 es 'group_name' (índice 17 en iloc)
                try:
                    group_counts = df.iloc[6:, 17].value_counts().to_dict()
                except:
                    group_counts = {}

                # Usar itertuples para iteración rápida (index=False devuelve tuplas con valores)
                # df.iloc[6:] selecciona desde la fila 6 en adelante
                for row in df.iloc[6:].itertuples(index=False, name=None):
                    # Mapeo de índices basado en iloc original:
                    # 0 -> row[0] (start_time)
                    # 3 -> row[3] (end_time)
                    # 17 -> row[17] (group_name)
                    # 19 -> row[19] (raw_block)
                    # 25 -> row[25] (program_name)
                    
                    start_time = row[0]
                    end_time = row[3]
                    group_name = row[17] if len(row) > 17 else None
                    raw_block = row[19] if len(row) > 19 else None

                    if pd.notna(raw_block):
                        block_filtered = filter_special_tags(str(raw_block))
                    else:
                        block_filtered = None

                    program_name = row[25] if len(row) > 25 else None

                    if not all(pd.notnull(value) and str(value).strip() != "" for value in (start_time, end_time)):
                        continue

                    if not (pd.notna(group_name) and str(group_name).strip()):
                        if block_filtered and str(block_filtered).strip():
                            group_name = block_filtered
                        else:
                            continue

                    duration = extract_duration_or_keyword(str(program_name)) or ""

                    # Optimización: Usar el conteo pre-calculado
                    unit_count = group_counts.get(group_name, 0)

                    shift = determine_shift_by_time(extract_parenthesized_schedule(str(start_time)))

                    program_keyword = extract_keyword_from_text(str(program_name))
                    area_value = (
                        f"{area_name}/{program_keyword}"
                        if program_keyword == "KIDS" and area_name
                        else area_name
                    )

                    try:
                        date_str = schedule_date.strftime("%d/%m/%Y")
                    except Exception:
                        date_str = str(schedule_date)

                    schedule = Schedule(
                        date=date_str,
                        shift=shift,
                        area=area_value,
                        start_time=format_time_periods(extract_parenthesized_schedule(str(start_time))),
                        end_time=format_time_periods(extract_parenthesized_schedule(str(end_time))),
                        code=str(instructor_code),
                        instructor=str(instructor_name),
                        program=str(group_name),
                        minutes=str(duration),
                        units=unit_count,
                    )
                    schedules.append(schedule)
    except Exception as e:
        raise Exception(f"Error al parsear el archivo: {str(e)}")

    return schedules
def parse_exported_excel_file(file_path: str) -> List[Schedule]:
    """Parsea un archivo Excel exportado (ya procesado) y carga los horarios."""
    schedules: List[Schedule] = []
    
    try:
        # Leer el archivo Excel exportado
        df = pd.read_excel(file_path, engine="openpyxl")
        
        # Verificar columnas esperadas (snake_case)
        expected_columns = ["date", "shift", "area", "start_time", "end_time", 
                          "code", "instructor", "program", "minutes", "units"]
        
        # Verificar si tiene las columnas nuevas (snake_case)
        if not all(col in df.columns for col in expected_columns):
             raise Exception("File format doesn't match exported schedule format")
        
        # Parsear cada fila
        for _, row in df.iterrows():
            # Saltar filas vacías
            if pd.isna(row["date"]) or pd.isna(row["instructor"]):
                continue
            
            try:
                schedule = Schedule(
                    date=str(row["date"]),
                    shift=str(row["shift"]),
                    area=str(row["area"]) if pd.notna(row["area"]) else "",
                    start_time=str(row["start_time"]),
                    end_time=str(row["end_time"]),
                    code=str(row["code"]),
                    instructor=str(row["instructor"]),
                    program=str(row["program"]),
                    minutes=str(row["minutes"]) if pd.notna(row["minutes"]) else "",
                    units=int(row["units"]) if pd.notna(row["units"]) else 0
                )
                schedules.append(schedule)
            except Exception as e:
                # Saltar filas que no se puedan parsear
                continue
    
    except Exception as e:
        raise Exception(f"Error parsing exported file: {str(e)}")
    
    return schedules


def detect_file_type(file_path: str) -> str:
    """Detecta si es un archivo original o exportado."""
    try:
        df = pd.read_excel(file_path, engine="openpyxl", nrows=1)
        
        # Si tiene las columnas de un archivo exportado (snake_case)
        if "start_time" in df.columns and "end_time" in df.columns:
            return "exported"
        else:
            return "original"
    except:
        return "original"  # Por defecto asumir original


def custom_message_box(parent, title, text, icon, buttons):
    """Helper para mostrar alertas con estilos personalizados en botones."""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    
    # Resize Icon (Reducir tamaño a 32x32)
    icon_map = {
        QMessageBox.Icon.Information: QStyle.StandardPixmap.SP_MessageBoxInformation,
        QMessageBox.Icon.Warning: QStyle.StandardPixmap.SP_MessageBoxWarning,
        QMessageBox.Icon.Critical: QStyle.StandardPixmap.SP_MessageBoxCritical,
        QMessageBox.Icon.Question: QStyle.StandardPixmap.SP_MessageBoxQuestion,
    }
    
    standard_pixmap = icon_map.get(icon)
    if standard_pixmap:
        pixmap = msg.style().standardIcon(standard_pixmap).pixmap(32, 32)
        msg.setIconPixmap(pixmap)
    else:
        msg.setIcon(icon)

    msg.setStandardButtons(buttons)
    
    # Estilizar botones secundarios (No, Cancel, Close)
    secondary_buttons = [
        QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Close,
        QMessageBox.StandardButton.Abort,
        QMessageBox.StandardButton.Ignore
    ]
    
    for btn_type in secondary_buttons:
        if buttons & btn_type:
            btn = msg.button(btn_type)
            if btn:
                # Estilo Ghost/Outline
                btn.setStyleSheet("""
                    background-color: #FFFFFF;
                    color: #09090B;
                    border: 1px solid #E4E4E7;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-family: 'IBM Plex Sans', sans-serif;
                    font-weight: 500;
                    font-size: 14px;
                    min-width: 80px;
                """)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                # Hover effect
                # Note: Stylesheets handle hover automatically if defined. 
                # But here we are setting inline style. We need to include hover in the string.
                # However, inline style on widget overrides stylesheet hover if not careful.
                # Better approach: Assign a dynamic property or class and use global stylesheet?
                # Or include :hover in the setStyleSheet string? Yes, setStyleSheet supports pseudo-states.
                
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FFFFFF;
                        color: #09090B;
                        border: 1px solid #E4E4E7;
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-family: 'IBM Plex Sans', sans-serif;
                        font-weight: 500;
                        font-size: 14px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #F4F4F5;
                    }
                    QPushButton:pressed {
                        background-color: #E4E4E7;
                    }
                """)
    
    # Estilizar botones primarios (Yes, Ok, Save, Open)
    primary_buttons = [
        QMessageBox.StandardButton.Yes,
        QMessageBox.StandardButton.Ok,
        QMessageBox.StandardButton.Save,
        QMessageBox.StandardButton.Open,
        QMessageBox.StandardButton.Retry
    ]
    
    for btn_type in primary_buttons:
        if buttons & btn_type:
            btn = msg.button(btn_type)
            if btn:
                # Estilo Primario (Zinc-900)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #18181B;
                        color: #FAFAFA;
                        border: 1px solid #18181B;
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-family: 'IBM Plex Sans', sans-serif;
                        font-weight: 500;
                        font-size: 14px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #27272A;
                    }
                    QPushButton:pressed {
                        background-color: #09090B;
                    }
                """)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)

    return msg.exec()


# ============================================================================
# WORKER THREAD PARA PROCESAMIENTO ASÍNCRONO
# ============================================================================

class ExcelWorker(QThread):
    """Worker thread para procesar archivos Excel sin bloquear la UI."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(list, list)  # schedules, errors

    def __init__(self, file_paths: List[str]):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        all_schedules = []
        errors = []

        for i, file_path in enumerate(self.file_paths):
            self.progress.emit(f"Processing {i+1}/{len(self.file_paths)}: {os.path.basename(file_path)}")
            try:
                # Detectar tipo de archivo
                file_type = detect_file_type(file_path)
                
                if file_type == "exported":
                    # Archivo ya procesado (exportado)
                    schedules = parse_exported_excel_file(file_path)
                else:
                    # Archivo original
                    schedules = parse_excel_file(file_path)
                
                all_schedules.extend(schedules)
            except Exception as e:
                errors.append(f"{os.path.basename(file_path)}: {str(e)}")

        self.finished.emit(all_schedules, errors)


class AssignmentWorker(QThread):
    """Worker thread para procesar la asignación automática de reuniones."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(list, list)  # results, errors

    def __init__(self, schedules: List[Schedule]):
        super().__init__()
        self.schedules = schedules

    def run(self):
        print("DEBUG: AssignmentWorker started")
        results = []
        errors = []
        
        try:
            self.progress.emit("Connecting to Supabase...")
            print(f"DEBUG: Connecting to Supabase... URL={SUPABASE_URL}")
            if not SUPABASE_URL or not SUPABASE_KEY:
                raise Exception("Missing SUPABASE_URL or SUPABASE_KEY in .env")
            
            supabase: Client = auth_manager.get_client()
            
            # 1. Fetch Zoom Users
            self.progress.emit("Fetching Zoom Users...")
            # Ahora traemos display_name directamente de la BD
            users_response = supabase.table("zoom_users").select("id, first_name, last_name, display_name, email").execute()
            
            # Diccionarios para búsqueda rápida de usuarios
            users_by_id = {}
            users_by_name = {} # Clave canónica -> User Data
            
            for u in users_response.data:
                uid = u["id"]
                # Usar display_name si existe, sino construirlo
                dname = u.get("display_name")
                fname = u.get("first_name", "").strip()
                lname = u.get("last_name", "").strip()
                full_name = f"{fname} {lname}".strip()
                
                if not dname:
                    dname = full_name
                
                u["display_name"] = dname
                u["full_name"] = full_name # Guardar nombre completo real
                
                users_by_id[uid] = u
                
                # Indexar por Display Name (Canónico)
                c_dname = utils.canonical(dname)
                if c_dname:
                    users_by_name[c_dname] = u
                    
                # Indexar TAMBIÉN por Full Name (Canónico) si es diferente
                c_fullname = utils.canonical(full_name)
                if c_fullname and c_fullname != c_dname:
                    users_by_name[c_fullname] = u
            
            # 2. Fetch Zoom Meetings
            self.progress.emit("Fetching Zoom Meetings...")
        
            zoom_meetings = []
            page_size = 1000
            offset = 0
            
            # Optimización: Seleccionar solo campos necesarios en lugar de *
            # Esto reduce significativamente la transferencia de datos
            while True:
                response = supabase.table("zoom_meetings")\
                    .select("meeting_id, topic, host_id")\
                    .range(offset, offset + page_size - 1)\
                    .execute()
                if not response.data:
                    break
                zoom_meetings.extend(response.data)
                if len(response.data) < page_size:
                    break
                offset += page_size
                self.progress.emit(f"Fetching Zoom Meetings... ({len(zoom_meetings)} loaded)")
                
            self.progress.emit(f"Processing {len(self.schedules)} schedules against {len(zoom_meetings)} meetings...")
            
            # Diccionarios para búsqueda rápida de reuniones (Global)
            meetings_map = {
                "by_topic": {}, # canonical(topic) -> Meeting
                "list": []      # Lista para fuzzy search
            }
        
            for m in zoom_meetings:
                try:
                    # Agregar info del host para referencia rápida
                    host_data = users_by_id.get(m.get("host_id"))
                    m["host_name"] = host_data.get("display_name", "Unknown") if host_data else "Unknown"
                    
                    topic = m.get("topic", "")
                    c_topic = utils.canonical(topic)
                    
                    meetings_map["list"].append(m)
                    if c_topic:
                        # Nota: Si hay múltiples reuniones con el mismo topic, esto guardará la última procesada.
                        # Sin filtro de fecha, asumimos que el topic es único o que cualquier coincidencia es válida.
                        meetings_map["by_topic"][c_topic] = m
                        
                except Exception as e:
                    continue

            # 3. Procesar Schedules
            
            # --- OPTIMIZATION: Pre-compute choices for fuzzy matching ---
            instructor_choices = {}
            for u in users_by_id.values():
                instructor_choices[utils.normalizar_cadena(u["display_name"])] = u
                if u.get("full_name"):
                    instructor_choices[utils.normalizar_cadena(u["full_name"])] = u
            
            meeting_choices = {utils.normalizar_cadena(m["topic"]): m for m in meetings_map["list"]}
            # ------------------------------------------------------------

            for i, schedule in enumerate(self.schedules):
                if i % 10 == 0:
                    self.progress.emit(f"Analyzing {i+1}/{len(self.schedules)}...")
                
                status = "not_found"
                match_reason = "No match found"
                meeting_id = ""
                
                # Datos del Schedule
                raw_instr = schedule.instructor
                raw_prog = schedule.program
                
                c_instr = utils.canonical(raw_instr)
                c_prog = utils.canonical(raw_prog)
                
                found_meeting = None
                found_instructor = None
                
                # --- BUSCAR INSTRUCTOR ---
                # 1. Exacto
                found_instructor = users_by_name.get(c_instr)
                
                # 2. Difuso (si no exacto)
                if not found_instructor:
                    found_instructor = utils.fuzzy_find(raw_instr, instructor_choices)
                    # found_instructor = utils.fuzzy_find(raw_instr, choices, threshold=80)

                # --- BUSCAR REUNIÓN ---
                # 1. Exacto
                found_meeting = meetings_map["by_topic"].get(c_prog)
                
                # 2. Difuso (si no exacto)
                if not found_meeting:
                    found_meeting = utils.fuzzy_find(raw_prog, meeting_choices, threshold=75)
                
                # --- DETERMINAR ESTADO ---
                if found_meeting and found_instructor:
                    # Ambos encontrados, verificar vínculo
                    if found_meeting.get("host_id") == found_instructor.get("id"):
                        status = "assigned"
                        match_reason = "-"
                        meeting_id = found_meeting.get("meeting_id")
                    else:
                        status = "to_update"
                        match_reason = f"-"
                        meeting_id = found_meeting.get("meeting_id")
                        
                elif found_meeting and not found_instructor:
                    status = "to_update"
                    match_reason = f"Instructor not found"
                    meeting_id = found_meeting.get("meeting_id")
                    
                elif not found_meeting and found_instructor:
                    status = "not_found"
                    meeting_id = "-"
                    match_reason = f"Meeting not found"
                
                else:
                    status = "not_found"
                    match_reason = "Neither Meeting nor Instructor found"

                results.append({
                    "schedule": schedule,
                    "status": status,
                    "meeting_id": meeting_id,
                    "reason": match_reason,
                    "found_instructor": found_instructor
                })
                
        except Exception as e:
            print(f"DEBUG: Error in AssignmentWorker: {e}")
            import traceback
            traceback.print_exc()
            errors.append(str(e))
            
        self.finished.emit(results, errors)


class UpdateWorker(QThread):
    """Worker thread para ejecutar la reasignación en Zoom y BD."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(list, list) # success_list, error_list

    def __init__(self, assignments: List[dict]):
        super().__init__()
        self.assignments = assignments # List of {meeting_id, new_host_email, new_host_id, topic}

    def run(self):
        print("DEBUG: UpdateWorker started")
        successes = []
        errors = []
        
        try:
            self.progress.emit("Connecting to Supabase...")
            if not SUPABASE_URL or not SUPABASE_KEY:
                raise Exception("Missing SUPABASE_URL or SUPABASE_KEY")
            
            supabase: Client = auth_manager.get_client()
            
            # 1. Obtener Token de Zoom
            self.progress.emit("Fetching Zoom Token...")
            token_resp = supabase.table("zoom_tokens").select("access_token").limit(1).execute()
            if not token_resp.data:
                raise Exception("No Zoom token found in database. Please sync first.")
            
            token = token_resp.data[0]["access_token"]
            
            # 2. Procesar Asignaciones en Paralelo
            total = len(self.assignments)
            completed = 0
            
            # Función auxiliar para ejecutar en cada hilo
            def process_assignment(item, current_token):
                meeting_id = item["meeting_id"]
                new_host_email = item["new_host_email"]
                new_host_id = item["new_host_id"]
                topic = item.get("topic", meeting_id)
                
                result = {"success": False, "msg": "", "topic": topic}
                
                try:
                    headers = {
                        "Authorization": f"Bearer {current_token}",
                        "Content-Type": "application/json"
                    }
                    
                    # A. Llamada a Zoom API
                    url = f"https://api.zoom.us/v2/meetings/{meeting_id}"
                    body = {"schedule_for": new_host_email}
                    
                    resp = httpx.patch(url, headers=headers, json=body, timeout=10.0)
                    
                    # Manejo de token expirado (básico, no perfecto en hilos pero funcional)
                    if resp.status_code == 401 or (resp.status_code == 400 and "Access token is expired" in resp.text):
                        return {"success": False, "msg": "TOKEN_EXPIRED", "topic": topic}
                    
                    if resp.status_code == 204:
                        # B. NO Actualizar Supabase aquí, retornar datos para batch update
                        result["success"] = True
                        result["msg"] = f"Updated {topic} -> {new_host_email}"
                        result["db_update"] = {"meeting_id": meeting_id, "host_id": new_host_id}
                    else:
                        result["msg"] = f"Zoom API Error {resp.status_code}: {resp.text}"
                        
                except Exception as e:
                    result["msg"] = str(e)
                    
                return result

            from concurrent.futures import as_completed
            
            updates_to_sync = []
            
            # Usar ThreadPoolExecutor
            max_workers = 10 # Ajustable según necesidad
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Iniciar tareas
                future_to_item = {
                    executor.submit(process_assignment, item, token): item 
                    for item in self.assignments
                }
                
                for future in as_completed(future_to_item):
                    completed += 1
                    res = future.result()
                    
                    # Manejo especial de reintento por token expirado
                    if not res["success"] and res["msg"] == "TOKEN_EXPIRED":
                        self.progress.emit("Token expired. Refreshing (blocking)...")
                        try:
                            # Refrescar token (bloqueante)
                            token = refresh_zoom_token(supabase)
                            # Reintentar SOLO este item
                            item = future_to_item[future]
                            res = process_assignment(item, token)
                        except Exception as e:
                            res["msg"] = f"Token Refresh Failed: {str(e)}"
                    
                    if res["success"]:
                        successes.append(res["msg"])
                        if "db_update" in res:
                            updates_to_sync.append(res["db_update"])
                    else:
                        errors.append(f"{res['topic']}: {res['msg']}")
                        
                    self.progress.emit(f"Processed {completed}/{total}...")

            # C. Actualización Masiva en Supabase
            if updates_to_sync:
                self.progress.emit(f"Syncing {len(updates_to_sync)} records to database...")
                try:
                    # Upsert en lotes de 100 para no saturar
                    batch_size = 100
                    for i in range(0, len(updates_to_sync), batch_size):
                        batch = updates_to_sync[i:i + batch_size]
                        # Usar upsert con on_conflict='meeting_id' para actualizar host_id
                        supabase.table("zoom_meetings").upsert(batch, on_conflict="meeting_id").execute()
                        
                except Exception as e:
                    errors.append(f"Database Sync Error: {str(e)}")
                    # Si falla la BD, marcamos como error global o advertencia?
                    # Los cambios en Zoom YA se hicieron.
        
        except Exception as e:
            errors.append(f"Critical Error: {str(e)}")
            
        self.finished.emit(successes, errors)


class RowHoverDelegate(QStyledItemDelegate):
    """Delegate para resaltar la fila completa al pasar el mouse."""
    def __init__(self, parent=None, hover_color="#F4F4F5"):
        super().__init__(parent)
        self.hover_color = QColor(hover_color)
        self.hover_row = -1

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        if index.row() == self.hover_row:
            painter.save()
            painter.fillRect(option.rect, self.hover_color)
            painter.restore()
        super().paint(painter, option, index)

    def createEditor(self, parent, option, index):
        """Crea un editor de solo lectura para permitir copiar texto."""
        # No permitir edición en columna de checkbox (0)
        if index.column() == 0:
            return None
            
        editor = QLineEdit(parent)
        editor.setReadOnly(True)
        editor.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu) # Deshabilitar menú contextual
        # Fondo opaco para cubrir el texto de abajo y evitar "duplicación"
        editor.setStyleSheet("""
            QLineEdit {
                border: 1px solid #E4E4E7;
                border-radius: 4px;
                background-color: #FFFFFF; 
                color: #09090B;
                selection-background-color: #18181B;
                selection-color: #FAFAFA;
                padding: 0 4px;
            }
        """)
        return editor

    def setEditorData(self, editor, index):
        """Establece los datos en el editor y su alineación."""
        text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        editor.setText(str(text))
        
        # Sincronizar alineación
        alignment = index.model().data(index, Qt.ItemDataRole.TextAlignmentRole)
        if alignment:
            # QLineEdit solo soporta alineación horizontal
            horizontal_align = alignment & Qt.AlignmentFlag.AlignHorizontal_Mask
            editor.setAlignment(Qt.AlignmentFlag(horizontal_align))

    def updateEditorGeometry(self, editor, option, index):
        """Ajusta el tamaño del editor al contenido del texto (fit-content)."""
        # Obtener texto
        text = str(index.model().data(index, Qt.ItemDataRole.DisplayRole))
        
        # Calcular ancho necesario usando fontMetrics
        fm = option.fontMetrics
        text_width = fm.horizontalAdvance(text)
        
        # Padding extra para el borde y margen interno (aprox 10-12px)
        required_width = text_width + 16 
        
        # No exceder el ancho de la celda disponible
        final_width = min(required_width, option.rect.width())
        
        # Crear el rectángulo final
        editor_rect = QRect(option.rect)
        editor_rect.setWidth(final_width)
        
        # Ajustar altura a 24px y centrar verticalmente
        target_height = 24
        vertical_diff = (option.rect.height() - target_height) // 2
        editor_rect.setHeight(target_height)
        editor_rect.moveTop(option.rect.top() + vertical_diff)
        
        # Ajustar alineación horizontal
        alignment = index.model().data(index, Qt.ItemDataRole.TextAlignmentRole)
        
        # Por defecto a la izquierda si no hay alineación
        if alignment is None:
            alignment = Qt.AlignmentFlag.AlignLeft
            
        if alignment & Qt.AlignmentFlag.AlignHCenter:
            # Centrar horizontalmente usando el centro exacto
            editor_rect.moveCenter(option.rect.center())
            # Re-ajustar top porque moveCenter cambia ambos ejes
            editor_rect.moveTop(option.rect.top() + vertical_diff)
        elif alignment & Qt.AlignmentFlag.AlignRight:
            # Alinear a la derecha con un pequeño margen
            editor_rect.moveRight(option.rect.right() - 4)
        else:
            # Izquierda (default) con margen para coincidir con el texto
            editor_rect.moveLeft(option.rect.left() + 8)
            
        editor.setGeometry(editor_rect)

    def setModelData(self, editor, model, index):
        """No hace nada porque es solo lectura."""
        pass


class CheckBoxHeader(QHeaderView):
    """Header personalizado con un checkbox en la primera columna."""
    checkBoxClicked = pyqtSignal(bool)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.isOn = False

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        super().paintSection(painter, rect, logicalIndex)
        painter.restore()

        if logicalIndex == 0:
            # Pintar un rectángulo sobre el área para ocultar el sort indicator
            painter.fillRect(rect, QColor("#F4F4F5"))
            # agregar border bottom

            # Dibujar border bottom
            painter.setPen(QPen(QColor("#E4E4E7"), 1))
            painter.drawLine(rect.x(), rect.bottom(), rect.right(), rect.bottom())
            
            option = QStyleOptionButton()
            option.rect = QRect(rect.x() + 15, rect.y() + 12, 20, 20)  # Ajustar posición con más padding left y superior
            option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            if self.isOn:
                option.state |= QStyle.StateFlag.State_On
            else:
                option.state |= QStyle.StateFlag.State_Off
            
            self.style().drawControl(QStyle.ControlElement.CE_CheckBox, option, painter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Calcular si el click fue en el área del checkbox de la primera columna
            # O si fue en la columna 0 en general (para evitar sort)
            
            # Obtener el índice lógico de la sección bajo el mouse
            logicalIndex = self.logicalIndexAt(event.position().toPoint())
            
            if logicalIndex == 0:
                # Toggle checkbox
                self.isOn = not self.isOn
                self.checkBoxClicked.emit(self.isOn)
                self.viewport().update()
                # NO llamar a super().mousePressEvent(event) para evitar sort
                return

        super().mousePressEvent(event)


# ============================================================================
# DIÁLOGOS
# ============================================================================

class AutoAssignDialog(QDialog):
    """Diálogo para configurar la asignación automática de reuniones."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} | Auto Assign")
        self.setModal(True)
        self.setFixedSize(1200, 600) # Aumentar tamaño para la tabla
        
        # Colores (copiados de SchedulePlanner para consistencia)
        self.COLORS = {
            "BACKGROUND": "#FFFFFF",
            "SURFACE": "#FFFFFF",
            "SURFACE_SECONDARY": "#F4F4F5",
            "BORDER": "#E4E4E7",
            "TEXT_PRIMARY": "#09090B",
            "TEXT_SECONDARY": "#71717A",
            "PRIMARY": "#18181B",
            "PRIMARY_FOREGROUND": "#FAFAFA",
            "DESTRUCTIVE": "#EF4444",
            "ACCENT": "#F4F4F5",
        }

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.COLORS['BACKGROUND']};
            }}
            QLabel {{
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
                color: {self.COLORS['TEXT_PRIMARY']};
            }}
            
            
            /* Estilos generales de botones para el diálogo */
            QPushButton {{
                font-family: 'IBM Plex Sans', sans-serif;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 14px;
            }}
            
            /* Override específico para botones de alerta dentro del diálogo */
            QMessageBox QPushButton {{
                background-color: #18181B;
                color: #FAFAFA;
                border: 1px solid #18181B;
                border-radius: 6px;
                padding: 4px 8px;
                font-weight: 500;
                min-width: 80px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: #27272A;
            }}
        QMessageBox QPushButton:pressed {{
            background-color: #09090B;
        }}
    """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title = QLabel("Automatic Assignment")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel("Review and assign meetings automatically.")
        desc.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']};")
        header_layout.addWidget(title)
        header_layout.addWidget(desc)
        layout.addLayout(header_layout)
        
        # Table Section
        # Filter Layout
        filter_layout = QHBoxLayout()
        
        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by Instructor...")
        self.search_input.setMinimumWidth(200)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                font-family: 'IBM Plex Sans', sans-serif;
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                padding: 8px 12px;
                background-color: {self.COLORS['SURFACE']};
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid #18181B;
            }}
            QLineEdit::placeholder {{
                color: {self.COLORS['TEXT_SECONDARY']};
            }}
        """)
        self.search_input.textChanged.connect(self.filter_table)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Assigned", "To Update", "Not Found"])
        self.filter_combo.setFixedHeight(36)
        self.filter_combo.setFixedWidth(150)
        # Apply combobox style
        self.filter_combo.setStyleSheet(f"""
            QComboBox {{
                font-family: 'IBM Plex Sans', sans-serif;
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                padding: 4px 8px;
                background-color: {self.COLORS['SURFACE']};
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QComboBox:hover {{
                border: 1px solid #18181B;
            }}
            QComboBox:focus {{
                border: 1px solid #18181B;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                font-family: 'IBM Plex Sans', sans-serif;
                background-color: {self.COLORS['SURFACE']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                selection-background-color: {self.COLORS['ACCENT']};
                selection-color: {self.COLORS['TEXT_PRIMARY']};
                padding: 4px;
            }}
        """)
        self.filter_combo.currentTextChanged.connect(self.filter_table)
        
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)

        # Progress bar (Thinner)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                font-family: 'IBM Plex Sans', sans-serif;
                border: none; background-color: {self.COLORS['SURFACE_SECONDARY']};
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {self.COLORS['PRIMARY']}; border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "", "Status", "Meeting ID", "Time", "Instructor", "Program/Group", "Reason"
        ])
        
        # Configuración de Header con Checkbox
        self.header = CheckBoxHeader(Qt.Orientation.Horizontal, self.table)
        self.table.setHorizontalHeader(self.header)
        self.header.setSectionsClickable(True) # Enable sorting clicks
        self.header.checkBoxClicked.connect(self.toggle_all_rows)
        
        # Configuración de tabla
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        
        self.table.horizontalHeader().setStretchLastSection(True) # Reason column stretch
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(45)
        
        # Estilo de Tabla (Mismo que main)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {self.COLORS['SURFACE']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 8px;
                gridline-color: transparent;
                outline: none;
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 12px;
                border-bottom: 1px solid {self.COLORS['BORDER']};
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QTableWidget::item:selected {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
                color: {self.COLORS['TEXT_PRIMARY']};
            }}
            QHeaderView::section {{
                background-color: #F4F4F5;
                color: {self.COLORS['TEXT_SECONDARY']};
                padding: 12px;
                border: none;
                border-bottom: 1px solid {self.COLORS['BORDER']};
                font-weight: 600;
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
            }}
            QTableWidget::corner {{
                background-color: {self.COLORS['SURFACE']};
                border: none;
            }}
            /* Scrollbars */
            QScrollBar:vertical {{
                border: none; background: {self.COLORS['SURFACE']};
                width:8px; margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.COLORS['BORDER']};
                min-height: 40px; border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                border: none; background: {self.COLORS['SURFACE']};
                height: 8px; margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {self.COLORS['BORDER']};
                min-width: 20px; border-radius: 4px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """)
        
        # Anchos de columna
        self.table.setColumnWidth(0, 40)  # Checkbox
        self.table.setColumnWidth(1, 100) # Status
        self.table.setColumnWidth(2, 120) # Meeting ID
        self.table.setColumnWidth(3, 120) # Time
        self.table.setColumnWidth(4, 180) # Instructor
        self.table.setColumnWidth(5, 400) # Program
        # Reason usa el resto del espacio
        
        layout.addWidget(self.table)
        
        # Conectar señales de selección
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemChanged.connect(self.on_item_changed)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        # Status Summary (Left side)
        self.lbl_to_update = QLabel("To Update: 0")
        self.lbl_to_update.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']}; font-weight: 500; font-size: 13px;")
        btn_layout.addWidget(self.lbl_to_update)

        self.lbl_assigned = QLabel("Assigned: 0")
        self.lbl_assigned.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']}; font-weight: 500; font-size: 13px;")
        btn_layout.addWidget(self.lbl_assigned)
        
        self.lbl_not_found = QLabel("Not Found: 0")
        self.lbl_not_found.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']}; font-weight: 500; font-size: 13px;")
        btn_layout.addWidget(self.lbl_not_found)
        
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLORS['BACKGROUND']};
                color: {self.COLORS['TEXT_PRIMARY']};
                border: 1px solid {self.COLORS['BORDER']};
            }}
            QPushButton:hover {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
            }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.start_btn = QPushButton("Execute")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setEnabled(False) # Disabled until processing finishes
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLORS['PRIMARY']};
                color: {self.COLORS['PRIMARY_FOREGROUND']};
                border: 1px solid {self.COLORS['PRIMARY']};
            }}
            QPushButton:hover {{
                background-color: #27272A;
            }}
            QPushButton:disabled {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
                color: {self.COLORS['TEXT_SECONDARY']};
                border: 1px solid {self.COLORS['BORDER']};
            }}
        """)
        self.start_btn.clicked.connect(self.execute_assignment)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.start_btn)
        
        layout.addLayout(btn_layout)
        
        # Referencia a los horarios (se pasará desde el padre)
        self.schedules = []

        # Configurar Hover Delegate
        self.table.setMouseTracking(True)
        self.hover_delegate = RowHoverDelegate(self.table)
        self.table.setItemDelegate(self.hover_delegate)
        self.table.cellEntered.connect(self.on_cell_entered)
        self.table.cellClicked.connect(self.on_cell_clicked)

        # Context Menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_context_menu)

    def on_cell_entered(self, row, column):
        """Maneja el evento de hover en las celdas."""
        self.hover_delegate.hover_row = row
        
        # Cursor Change for Links (Column 2)
        item = self.table.item(row, column)
        if column == 2 and item and item.data(Qt.ItemDataRole.UserRole):
             self.table.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
             self.table.setCursor(Qt.CursorShape.ArrowCursor)
             
        self.table.viewport().update()

    def on_cell_clicked(self, row, column):
        """Maneja el clic en las celdas (para abrir links)."""
        if column == 2: # Meeting ID
            item = self.table.item(row, column)
            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                if url:
                    QDesktopServices.openUrl(QUrl(url))

    def open_context_menu(self, position):
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {self.COLORS['BACKGROUND']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                color: {self.COLORS['TEXT_PRIMARY']};
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 13px;
            }}
            QMenu::item:selected {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
            }}
        """)
        deselect_action = menu.addAction("Deselect All")
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        
        if action == deselect_action:
            self.deselect_all_rows()

    def deselect_all_rows(self):
        self.table.clearSelection()
        # Ensure checkboxes are updated if necessary (toggle_all_rows handles logic but based on state)
        # clearSelection triggers selectionChanged which calls on_selection_changed
        # on_selection_changed updates checkboxes based on selection.
        # So clearSelection should be enough if on_selection_changed is correct.
        # Let's verify on_selection_changed logic.

    def toggle_all_rows(self, state: bool):
        """Marca o desmarca todas las filas."""
        self.table.blockSignals(True)
        try:
            check_state = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
            
            # Actualizar selección visual
            if state:
                self.table.selectAll()
            else:
                self.table.clearSelection()
                
            for i in range(self.table.rowCount()):
                # Solo si la fila es visible
                if self.table.isRowHidden(i):
                    continue
                    
                item = self.table.item(i, 0)
                if item and (item.flags() & Qt.ItemFlag.ItemIsEnabled):
                    item.setCheckState(check_state)
        finally:
            self.table.blockSignals(False)
            self.update_execute_button_text()

    def on_selection_changed(self):
        """Sincroniza la selección de filas con los checkboxes."""
        if self.table.signalsBlocked():
            return

        self.table.blockSignals(True)
        try:
            selected_rows = {index.row() for index in self.table.selectedIndexes()}
            
            for i in range(self.table.rowCount()):
                item = self.table.item(i, 0)
                if not item or not (item.flags() & Qt.ItemFlag.ItemIsEnabled): continue
                
                should_be_checked = i in selected_rows
                current_state = item.checkState() == Qt.CheckState.Checked
                
                if should_be_checked != current_state:
                    item.setCheckState(Qt.CheckState.Checked if should_be_checked else Qt.CheckState.Unchecked)
        finally:
            self.table.blockSignals(False)
            self.update_execute_button_text()

    def on_item_changed(self, item):
        """Sincroniza los checkboxes con la selección de filas."""
        if item.column() == 0:
            if self.table.signalsBlocked():
                return

            self.table.blockSignals(True)
            try:
                row = item.row()
                selection_model = self.table.selectionModel()
                if item.checkState() == Qt.CheckState.Checked:
                    selection_model.select(self.table.model().index(row, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
                else:
                    selection_model.select(self.table.model().index(row, 0), QItemSelectionModel.SelectionFlag.Deselect | QItemSelectionModel.SelectionFlag.Rows)
                
                # Sincronizar header si se desmarca uno
                if item.checkState() == Qt.CheckState.Unchecked and self.header.isOn:
                    self.header.isOn = False
                    self.header.viewport().update()
            finally:
                self.table.blockSignals(False)
                self.update_execute_button_text()

    def process_data(self):
        """Inicia el procesamiento de datos (búsqueda de coincidencias)."""
        print(f"DEBUG: process_data called. Schedules count: {len(self.schedules)}")
        if not self.schedules:
            # Si no hay horarios, tal vez mostrar un mensaje en la tabla vacía
            return
            
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Processing...")
        self.table.setRowCount(0) # Limpiar tabla
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.worker = AssignmentWorker(self.schedules)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.start()
        
    def update_progress(self, msg):
        self.setWindowTitle(f"{APP_NAME} | Auto Assign - {msg}")

    def on_processing_finished(self, results, errors):
        """Maneja los resultados del procesamiento."""
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Execute")
        self.setWindowTitle(f"{APP_NAME} | Auto Assign")
        self.progress_bar.setVisible(False)
        
        if errors:
            custom_message_box(self, "Error", f"Errors occurred: {'; '.join(errors[:3])}", QMessageBox.Icon.Critical, QMessageBox.StandardButton.Ok)
            return
            
        self.table.setRowCount(len(results))
        self.table.setSortingEnabled(False)
        
        to_update_count = 0
        assigned_count = 0
        not_found_count = 0
        
        for i, res in enumerate(results):
            schedule = res["schedule"]
            status = res["status"]
            meeting_id = res["meeting_id"]
            reason = res["reason"]
            
            if status == "assigned":
                assigned_count += 1
            elif status == "to_update":
                to_update_count += 1
            else:
                not_found_count += 1
            
            found_instructor = res.get("found_instructor")
            
            # Checkbox
            chk_item = QTableWidgetItem()
            
            if status == "to_update":
                chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                # Guardar datos del instructor para la ejecución
                if found_instructor:
                    chk_item.setData(Qt.ItemDataRole.UserRole, found_instructor)
            else:
                # Deshabilitar para assigned y not_found
                chk_item.setFlags(Qt.ItemFlag.NoItemFlags)
                # No establecemos estado para que no aparezca el checkbox o aparezca deshabilitado
                # Si queremos que aparezca deshabilitado:
                chk_item.setFlags(Qt.ItemFlag.ItemIsEnabled) # Solo enabled para visualización, pero no checkable
                chk_item.setFlags(chk_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable & ~Qt.ItemFlag.ItemIsSelectable)
                # Mejor: NoItemFlags para que no se pueda seleccionar la fila via checkbox
                # Pero queremos ver el texto? No hay texto en col 0.
                # Para evitar selección de fila, necesitamos manejar flags en TODOS los items de la fila o en selectionChanged.
                
                # Estrategia: Items deshabilitados no son seleccionables por defecto en QTableWidget si se configuran bien.
                chk_item.setFlags(Qt.ItemFlag.NoItemFlags) 

            self.table.setItem(i, 0, chk_item)
            
            # Status
            # Map internal status to display status
            display_status = "Not Found"
            color = QColor("#EF4444") # Red
            
            if status == "assigned":
                display_status = "Assigned"
                color = QColor("#10B981") # Green
            elif status == "to_update":
                display_status = "To Update"
                color = QColor("#F59E0B") # Amber
            
            status_item = QTableWidgetItem(display_status)
            status_item.setForeground(color)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if status != "to_update":
                 status_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.setItem(i, 1, status_item)
            
            # Helper para crear items no editables y deshabilitados si no es to_update
            def create_item(text, align_center=False):
                it = QTableWidgetItem(str(text))
                if align_center:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if status != "to_update":
                    it.setFlags(Qt.ItemFlag.NoItemFlags)
                else:
                    it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                return it

            # Meeting ID
            meeting_id_item = create_item(str(meeting_id), align_center=True)
            if meeting_id and str(meeting_id) != "-" and str(meeting_id) != "":
                 # Configurar como Link
                 meeting_id_item.setForeground(QColor("#2563EB")) # Blue-600
                 font = meeting_id_item.font()
                 font.setUnderline(True)
                 meeting_id_item.setFont(font)
                 meeting_id_item.setData(Qt.ItemDataRole.UserRole, f"https://zoom.us/meeting/{meeting_id}")
                 # Asegurar que sea interactuable para el click
                 # Si es to_update, debe ser seleccionable para que la fila se vea completa
                 if status == "to_update":
                     meeting_id_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                 else:
                     meeting_id_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                 
            self.table.setItem(i, 2, meeting_id_item)
            
            # Time (Local) - Convertir a 24h
            start_24h = schedule._convert_to_24h(schedule.start_time)
            end_24h = schedule._convert_to_24h(schedule.end_time)
            self.table.setItem(i, 3, create_item(f"{start_24h} - {end_24h}", align_center=True))
            
            # Instructor
            self.table.setItem(i, 4, create_item(schedule.instructor))
            
            # Program
            self.table.setItem(i, 5, create_item(schedule.program))
            
            # Reason
            self.table.setItem(i, 6, create_item(reason, align_center=True))
            
        self.lbl_to_update.setText(f"To Update: {to_update_count}")
        self.lbl_assigned.setText(f"Assigned: {assigned_count}")
        self.lbl_not_found.setText(f"Not Found: {not_found_count}")
            
        self.table.setSortingEnabled(True)
        self.table.sortItems(1, Qt.SortOrder.AscendingOrder)
        # Re-apply filters
        self.filter_table()
        
        self.update_execute_button_text()
        # No mostrar popup de completado, solo mostrar la tabla
        
    def filter_table(self, text=None):
        """Filtra la tabla según el estado seleccionado y el texto de búsqueda."""
        status_filter = self.filter_combo.currentText()
        search_text = self.search_input.text().lower().strip()
        
        # Split search text by comma for multiple instructor search
        search_terms = [term.strip() for term in search_text.split(',') if term.strip()]
        
        for row in range(self.table.rowCount()):
            # 1. Check Status
            status_item = self.table.item(row, 1) # Status column
            if not status_item:
                continue
            
            status = status_item.text()
            status_match = (status_filter == "All") or (status_filter == status)
            
            # 2. Check Search Text (Instructor - Column 4)
            instructor_item = self.table.item(row, 4)
            instructor_name = instructor_item.text().lower() if instructor_item else ""
            
            if not search_terms:
                search_match = True
            else:
                # Match if ANY of the terms is found in the instructor name
                search_match = any(term in instructor_name for term in search_terms)
            
            if status_match and search_match:
                self.table.setRowHidden(row, False)
            else:
                self.table.setRowHidden(row, True)

    def update_execute_button_text(self):
        """Actualiza el texto del botón Execute con la cantidad de filas seleccionadas."""
        count = 0
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                count += 1
        
        if count > 0:
            self.start_btn.setText(f"Execute ({count})")
        else:
            self.start_btn.setText("Execute")

    def execute_assignment(self):
        """Ejecuta la asignación para las filas seleccionadas."""
        assignments = []
        
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                found_instructor = item.data(Qt.ItemDataRole.UserRole)
                meeting_id_item = self.table.item(i, 2)
                program_item = self.table.item(i, 5)
                
                if found_instructor and meeting_id_item:
                    assignments.append({
                        "meeting_id": meeting_id_item.text(),
                        "new_host_email": found_instructor.get("email"),
                        "new_host_id": found_instructor.get("id"),
                        "topic": program_item.text() if program_item else "Unknown Meeting"
                    })
        
        if not assignments:
            custom_message_box(self, "Warning", "No meetings selected for assignment.", QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok)
            return
            
        confirm = custom_message_box(
            self, 
            "Confirm Assignment", 
            f"Are you sure you want to assign {len(assignments)} meetings?",
            QMessageBox.Icon.Question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Updating...")
        self.cancel_btn.setEnabled(False)
        self.table.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.update_worker = UpdateWorker(assignments)
        self.update_worker.progress.connect(self.update_progress)
        self.update_worker.finished.connect(self.on_update_finished)
        self.update_worker.start()

    def on_update_finished(self, successes, errors):
        """Maneja el fin de la actualización."""
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Execute")
        self.cancel_btn.setEnabled(True)
        self.table.setEnabled(True)
        self.setWindowTitle(f"{APP_NAME} | Auto Assign")
        self.progress_bar.setVisible(False)
        
        msg = f"Process completed.\n\nSuccess: {len(successes)}\nErrors: {len(errors)}"
        
        if errors:
            msg += "\n\nFirst few errors:\n" + "\n".join(errors[:3])
            custom_message_box(self, "Completed with Errors", msg, QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok)
        else:
            custom_message_box(self, "Success", msg, QMessageBox.Icon.Information, QMessageBox.StandardButton.Ok)
            
        # Recargar datos para reflejar cambios
        self.process_data()



class MeetingSearchWorker(QThread):
    """Worker thread para buscar reuniones en Supabase."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(list, list) # meetings, errors

    def run(self):
        print("DEBUG: MeetingSearchWorker started")
        meetings = []
        errors = []
        
        try:
            self.progress.emit("Connecting to Supabase...")
            if not SUPABASE_URL or not SUPABASE_KEY:
                raise Exception("Missing SUPABASE_URL or SUPABASE_KEY in .env")
            
            supabase: Client = auth_manager.get_client()
            
            # 1. Fetch Zoom Users
            self.progress.emit("Fetching Zoom Users...")
            users_response = supabase.table("zoom_users").select("id, display_name, first_name, last_name, email").execute()
            
            users_map = {} # id -> display_name
            for u in users_response.data:
                uid = u["id"]
                dname = u.get("display_name")
                if not dname:
                    fname = u.get("first_name", "").strip()
                    lname = u.get("last_name", "").strip()
                    dname = f"{fname} {lname}".strip()
                users_map[uid] = dname
            
            # 2. Fetch Zoom Meetings
            self.progress.emit("Fetching Zoom Meetings...")
            # Fetch all meetings (pagination might be needed if huge, but let's start simple or use same pagination logic)
            all_meetings = []
            page_size = 1000
            offset = 0
            
            while True:
                response = supabase.table("zoom_meetings")\
                    .select("meeting_id, topic, host_id, created_at")\
                    .range(offset, offset + page_size - 1)\
                    .execute()
                if not response.data:
                    break
                all_meetings.extend(response.data)
                if len(response.data) < page_size:
                    break
                offset += page_size
                self.progress.emit(f"Fetching Zoom Meetings... ({len(all_meetings)} loaded)")
                
            # 3. Process Meetings
            self.progress.emit("Processing data...")
            for m in all_meetings:
                host_id = m.get("host_id")
                m["host_name"] = users_map.get(host_id, "Unknown")
                meetings.append(m)
                
        except Exception as e:
            errors.append(str(e))
            
        self.finished.emit(meetings, errors)


class MeetingSearchDialog(QDialog):
    """Diálogo para buscar y filtrar reuniones."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} | Search Meetings")
        self.setModal(True)
        self.setFixedSize(1000, 600)
        
        # Colores (Reutilizar del padre si es posible, o definir aquí)
        self.COLORS = {
            "BACKGROUND": "#FFFFFF",
            "SURFACE": "#FFFFFF",
            "SURFACE_SECONDARY": "#F4F4F5",
            "BORDER": "#E4E4E7",
            "TEXT_PRIMARY": "#09090B",
            "TEXT_SECONDARY": "#71717A",
            "PRIMARY": "#18181B",
            "PRIMARY_FOREGROUND": "#FAFAFA",
            "DESTRUCTIVE": "#EF4444",
            "ACCENT": "#F4F4F5",
        }

        self.setStyleSheet(f"""
            QDialog {{ background-color: {self.COLORS['BACKGROUND']}; }}
            QLabel {{ font-family: 'IBM Plex Sans', sans-serif; font-size: 14px; color: {self.COLORS['TEXT_PRIMARY']}; }}
            QPushButton {{
                font-family: 'IBM Plex Sans', sans-serif; border-radius: 6px; padding: 8px 16px; font-weight: 500; font-size: 14px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title = QLabel("Search Meetings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel("Find Zoom meetings by program or instructor.")
        desc.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']};")
        header_layout.addWidget(title)
        header_layout.addWidget(desc)
        layout.addLayout(header_layout)
        
        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Program/Topic...")
        self.search_input.setMinimumWidth(250)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                font-family: 'IBM Plex Sans', sans-serif; border: 1px solid {self.COLORS['BORDER']}; border-radius: 6px; padding: 8px 12px; background-color: {self.COLORS['SURFACE']}; color: {self.COLORS['TEXT_PRIMARY']}; font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid #18181B; }}
        """)
        self.search_input.textChanged.connect(self.filter_table)
        
        self.instructor_input = QLineEdit()
        self.instructor_input.setPlaceholderText("Filter by Instructor...")
        self.instructor_input.setMinimumWidth(200)
        self.instructor_input.setStyleSheet(f"""
            QLineEdit {{
                font-family: 'IBM Plex Sans', sans-serif; border: 1px solid {self.COLORS['BORDER']}; border-radius: 6px; padding: 8px 12px; background-color: {self.COLORS['SURFACE']}; color: {self.COLORS['TEXT_PRIMARY']}; font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid #18181B; }}
        """)
        self.instructor_input.textChanged.connect(self.filter_table)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {self.COLORS['SURFACE']}; color: {self.COLORS['TEXT_PRIMARY']}; border: 1px solid {self.COLORS['BORDER']}; }}
            QPushButton:hover {{ background-color: {self.COLORS['SURFACE_SECONDARY']}; }}
        """)
        self.refresh_btn.clicked.connect(self.load_data)
        
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(self.instructor_input)
        filter_layout.addWidget(self.refresh_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; background-color: {self.COLORS['SURFACE_SECONDARY']}; border-radius: 2px; }}
            QProgressBar::chunk {{ background-color: {self.COLORS['PRIMARY']}; border-radius: 2px; }}
        """)
        layout.addWidget(self.progress_bar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Meeting ID", "Topic", "Host", "Created At"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44) # Better row height
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        # Estilos Tabla
        self.table.setStyleSheet(f"""
            QTableWidget {{ background-color: {self.COLORS['SURFACE']}; border: 1px solid {self.COLORS['BORDER']}; border-radius: 8px; outline: none; }}
            QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {self.COLORS['BORDER']}; color: {self.COLORS['TEXT_PRIMARY']}; }}
            QTableWidget::item:selected {{ background-color: {self.COLORS['SURFACE_SECONDARY']}; color: {self.COLORS['TEXT_PRIMARY']}; }}
            QHeaderView::section {{ background-color: {self.COLORS['SURFACE_SECONDARY']}; color: {self.COLORS['TEXT_SECONDARY']}; padding: 12px; border: none; border-bottom: 1px solid {self.COLORS['BORDER']}; font-weight: 600; }}
            QScrollBar:vertical {{ background-color: {self.COLORS['SURFACE']}; border: none; width: 8px; border-radius: 4px; }}
            QScrollBar::handle:vertical {{ background: {self.COLORS['BORDER']};border-radius: 4px; min-height: 40px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        
        # Column Widths
        self.table.setColumnWidth(0, 150) # ID
        self.table.setColumnWidth(1, 360) # Topic
        self.table.setColumnWidth(2, 200) # Host
        self.table.setColumnWidth(3, 150) # Created At
        
        # Hover Delegate
        self.table.setMouseTracking(True)
        self.hover_delegate = RowHoverDelegate(self.table)
        self.table.setItemDelegate(self.hover_delegate)
        self.table.cellEntered.connect(self.on_cell_entered)
        self.table.cellClicked.connect(self.on_cell_clicked)
        
        layout.addWidget(self.table)
        
        # Close Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {self.COLORS['PRIMARY']}; color: {self.COLORS['PRIMARY_FOREGROUND']}; border: 1px solid {self.COLORS['PRIMARY']}; }}
            QPushButton:hover {{ background-color: #27272A; }}
        """)
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        # Data
        self.all_meetings = []
        
        # Load Data on Open
        QTimer.singleShot(100, self.load_data)

    def on_cell_entered(self, row, column):
        self.hover_delegate.hover_row = row
        # Cursor hand for Meeting ID (0)
        if column == 0:
             self.table.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
             self.table.setCursor(Qt.CursorShape.ArrowCursor)
        self.table.viewport().update()

    def on_cell_clicked(self, row, column):
        if column == 0: # Meeting ID link
            item = self.table.item(row, column)
            if item:
                mid = item.text()
                url = f"https://zoom.us/meeting/{mid}"
                QDesktopServices.openUrl(QUrl(url))

    def load_data(self):
        self.table.setRowCount(0)
        self.refresh_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.worker = MeetingSearchWorker()
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_data_loaded)
        self.worker.start()
        
    def update_progress(self, msg):
        self.setWindowTitle(f"{APP_NAME} | Search Meetings - {msg}")

    def on_data_loaded(self, meetings, errors):
        self.refresh_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.setWindowTitle(f"{APP_NAME} | Search Meetings")
        
        if errors:
            custom_message_box(self, "Error", f"Error loading data: {errors[0]}", QMessageBox.Icon.Critical, QMessageBox.StandardButton.Ok)
            return
            
        self.all_meetings = meetings
        
        # No need to populate combo anymore
        
        self.populate_table(meetings)

    def populate_table(self, meetings):
        self.table.setRowCount(len(meetings))
        self.table.setSortingEnabled(False)
        
        for i, m in enumerate(meetings):
            # ID
            id_item = QTableWidgetItem(str(m.get("meeting_id")))
            id_item.setForeground(QColor("#2563EB"))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = id_item.font()
            font.setUnderline(True)
            id_item.setFont(font)
            self.table.setItem(i, 0, id_item)
            
            # Topic
            self.table.setItem(i, 1, QTableWidgetItem(str(m.get("topic", ""))))
            
            # Host
            host_item = QTableWidgetItem(str(m.get("host_name", "")))
            host_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, host_item)
            
            # Created At
            created_at = m.get("created_at", "")
            # Formatear si es posible (ISO string a algo legible)
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                created_at = dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass
            created_at_item = QTableWidgetItem(created_at)
            created_at_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 3, created_at_item)
            
        self.table.setSortingEnabled(True)

    def filter_table(self):
        search_text = self.search_input.text().lower().strip()
        instructor_filter = self.instructor_input.text().lower().strip()
        
        filtered = []
        for m in self.all_meetings:
            # 1. Instructor
            host_name = str(m.get("host_name", "")).lower()
            if instructor_filter and instructor_filter not in host_name:
                continue
                
            # 2. Search Text (Topic or ID)
            topic = str(m.get("topic", "")).lower()
            mid = str(m.get("meeting_id", ""))
            
            if search_text and (search_text not in topic and search_text not in mid):
                continue
                
            filtered.append(m)
            
        self.populate_table(filtered)


# ============================================================================
# VENTANA PRINCIPAL
# ============================================================================

class SchedulePlanner(QMainWindow):
    # --- SHADCN THEME COLORS (Zinc) ---
    COLORS = {
        "BACKGROUND": "#FFFFFF",
        "SURFACE": "#FFFFFF",
        "SURFACE_SECONDARY": "#F4F4F5",  # Zinc-100
        "BORDER": "#E4E4E7",            # Zinc-200
        "TEXT_PRIMARY": "#09090B",      # Zinc-950
        "TEXT_SECONDARY": "#71717A",    # Zinc-500
        "PRIMARY": "#18181B",           # Zinc-900
        "PRIMARY_FOREGROUND": "#FAFAFA",# Zinc-50
        "DESTRUCTIVE": "#EF4444",       # Red-500
        "ACCENT": "#F4F4F5",            # Zinc-100 (Hover)
        "ACCENT_FOREGROUND": "#18181B", # Zinc-900
        "RING": "#18181B",              # Zinc-900 (Focus)
    }

    def __init__(self):
        super().__init__()
        self.schedules: List[Schedule] = []
        self.selected_rows: Set[int] = set()
        
        # Filtros
        self.filter_instructor = ""
        self.filter_program = ""
        self.filter_time = ""  # Filtro por hora
        
        # Mantener referencia de horarios visibles para eliminación correcta
        self.visible_schedules: List[Schedule] = []
        
        # Simple view flag
        self.simple_view = False
        
        # Timer para debouncing de filtros
        self.filter_timer = QTimer()
        self.filter_timer.setSingleShot(True)
        self.filter_timer.setInterval(100)  # 100ms delay
        self.filter_timer.timeout.connect(self._apply_filters)
        
        self.init_ui()
        
        # Iniciar chequeo de actualizaciones
        QTimer.singleShot(2000, self.check_updates)

    def init_ui(self):
        """Inicializa la interfaz de usuario con estilo Shadcn."""
        self.setWindowTitle(f"{APP_NAME} | Master your Time")
        self.setWindowIcon(QIcon(utils.resource_path("favicon.ico")))
        self.setGeometry(100, 100, 1460, 850)
        
        # Estado persistente
        self.selected_schedule_ids = set() # Set de IDs (tuplas o ids de objeto) seleccionados
        self.schedules = []
        self.visible_schedules = []
        font = QFont("IBM Plex Sans", 14)
        QApplication.instance().setFont(font)
        QApplication.instance().setStyleSheet("""
            QWidget { font-family: 'IBM Plex Sans', sans-serif; font-size: 14px; }
            
            /* QMessageBox Styling */
            QMessageBox {
                background-color: #FFFFFF;
                min-width: 200px;
            }
            QMessageBox QLabel {
                color: #09090B;
                font-size: 14px;
            }
            QMessageBox QPushButton {
                background-color: #18181B;
                color: #FAFAFA;
                border: 1px solid #18181B;
                border-radius: 6px;
                padding: 4px 8px;
                font-weight: 500;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #27272A;
            }
            QMessageBox QPushButton:pressed {
                background-color: #09090B;
            }
        """)

        # Widget central con fondo
        central_widget = QWidget()
        central_widget.setStyleSheet(f"background-color: {self.COLORS['BACKGROUND']};")
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # Header Section
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)
        
        title_label = QLabel(f"{APP_NAME}")
        title_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {self.COLORS['TEXT_PRIMARY']};")
        
        desc_label = QLabel("Master your Time. Precision Scheduling for Zoom.")
        desc_label.setStyleSheet(f"font-size: 14px; color: {self.COLORS['TEXT_SECONDARY']};")
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(desc_label)
        main_layout.addWidget(header_widget)

        # Action Bar (Filters + Actions)
        action_bar = QWidget()
        action_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {self.COLORS['SURFACE']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 8px;
            }}
        """)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(12, 12, 12, 12)
        action_layout.setSpacing(12)

        # Left Side: Load + Filters
        self.load_btn = QPushButton("Load Files")
        self.load_btn.setMinimumHeight(36)
        self.load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_btn.setStyleSheet(self.get_button_style("primary"))
        self.load_btn.clicked.connect(self.load_files)

        self.search_meetings_btn = QPushButton("Search Meetings")
        self.search_meetings_btn.setMinimumHeight(36)
        self.search_meetings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_meetings_btn.setStyleSheet(self.get_button_style("secondary"))
        self.search_meetings_btn.clicked.connect(self.open_meeting_search_dialog)
        
        self.filter_instructor_input = QLineEdit()
        self.filter_instructor_input.setPlaceholderText("Filter by Instructor...")
        self.filter_instructor_input.setMinimumWidth(180)
        self.filter_instructor_input.setStyleSheet(self.get_input_style())
        self.filter_instructor_input.textChanged.connect(self.on_filter_changed)
        
        self.filter_program_input = QLineEdit()
        self.filter_program_input.setPlaceholderText("Filter by Program...")
        self.filter_program_input.setMinimumWidth(180)
        self.filter_program_input.setStyleSheet(self.get_input_style())
        self.filter_program_input.textChanged.connect(self.on_filter_changed)
        
        # Time filter ComboBox
        self.filter_time_combo = QComboBox()
        self.filter_time_combo.setMinimumWidth(120)
        self.filter_time_combo.setMaximumWidth(120)
        self.filter_time_combo.setFixedHeight(36)
        self.filter_time_combo.setMaxVisibleItems(10)  # Limit dropdown height
        self.filter_time_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_time_combo.addItem("All Times")  # Default option
        self.filter_time_combo.setStyleSheet(self.get_combobox_style())
        self.filter_time_combo.currentTextChanged.connect(self.on_time_filter_changed)

        self.show_overlaps_cb = QCheckBox("Overlaps Only")
        self.show_overlaps_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_overlaps_cb.setStyleSheet("""
            QCheckBox {
                border: none;
            }
        """)
        self.show_overlaps_cb.stateChanged.connect(self.update_table)

        action_layout.addWidget(self.load_btn)
        action_layout.addWidget(self.search_meetings_btn)
        action_layout.addWidget(self.filter_instructor_input)
        action_layout.addWidget(self.filter_program_input)
        action_layout.addWidget(self.filter_time_combo)
        action_layout.addWidget(self.show_overlaps_cb)


        self.clear_filters_btn = QPushButton("Clear Filters")
        self.clear_filters_btn.setMinimumHeight(36)
        self.clear_filters_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_filters_btn.setStyleSheet(self.get_button_style("ghost"))
        self.clear_filters_btn.clicked.connect(self.clear_filters)
        action_layout.addWidget(self.clear_filters_btn)
        
        action_layout.addStretch()


        
        main_layout.addWidget(action_bar)

        # Progress bar (Thinner)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                font-family: 'IBM Plex Sans', sans-serif;
                border: none; background-color: {self.COLORS['SURFACE_SECONDARY']};
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {self.COLORS['PRIMARY']}; border-radius: 2px;
            }}
        """)
        main_layout.addWidget(self.progress_bar)

        # Status Bar (Stats | Status/Error | Selection + Delete)
        status_layout = QHBoxLayout()
        
        # Left: Stats
        self.records_label = QLabel("Records: 0")
        self.records_label.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']}; font-size: 14px;")
        
        self.overlaps_label = QLabel("Overlaps: 0")
        self.overlaps_label.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']}; font-size: 14px;")

        # Selection + Delete
        self.selection_label = QLabel("Selected: 0")
        self.selection_label.setStyleSheet(f"color: {self.COLORS['TEXT_SECONDARY']}; font-size: 14px;")
        
        # Middle: Status & Error (Hidden by default or shown when needed)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #10B981; font-weight: 600; font-size: 14px;") # Emerald-500
        
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {self.COLORS['DESTRUCTIVE']}; font-weight: 600;")
        
        self.simple_view_cb = QCheckBox("Simple Columns")
        self.simple_view_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.simple_view_cb.setStyleSheet("""
            QCheckBox {
                border: none;
            }
        """)
        self.simple_view_cb.stateChanged.connect(self.toggle_simple_view)

        status_layout.addWidget(self.records_label)
        status_layout.addWidget(self.overlaps_label)
        status_layout.addWidget(self.selection_label)
        status_layout.addWidget(self.simple_view_cb)

        # status_layout.addSpacing(20)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.error_label)
        status_layout.addStretch()

        # Copy, Export, Clear
        self.copy_menu_btn = QPushButton("Options")
        self.copy_menu_btn.setMinimumHeight(30) # Reduced height for status bar
        self.copy_menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_menu_btn.setStyleSheet(self.get_button_style("secondary"))

        copy_menu = QMenu(self)
        copy_menu.setStyleSheet(self.get_menu_style())
        copy_schedule_action = copy_menu.addAction("Copy Schedule")
        copy_schedule_action.triggered.connect(self.copy_all_schedule)
        copy_instructors_action = copy_menu.addAction("Copy Instructors")
        copy_instructors_action.triggered.connect(self.copy_instructors)
        self.copy_menu_btn.setMenu(copy_menu)

        self.export_btn = QPushButton("Export")
        self.export_btn.setMinimumHeight(30) # Reduced height for status bar
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setStyleSheet(self.get_button_style("outline"))
        self.export_btn.clicked.connect(self.export_to_excel)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setMinimumHeight(30) # Reduced height for status bar
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(self.get_button_style("ghost"))
        self.clear_btn.clicked.connect(self.clear_all)

        # Right Side Buttons Layout (Tighter spacing)
        right_buttons_layout = QHBoxLayout()
        right_buttons_layout.setSpacing(12)
        right_buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        right_buttons_layout.addWidget(self.copy_menu_btn)
        
        # Auto Assign Button (Moved here)
        self.auto_assign_btn = QPushButton("Auto Assign")
        self.auto_assign_btn.setMinimumHeight(30) # Match other buttons height
        self.auto_assign_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_assign_btn.setStyleSheet(self.get_button_style("primary"))
        self.auto_assign_btn.clicked.connect(self.open_auto_assign_modal)
        self.auto_assign_btn.setEnabled(False)
        right_buttons_layout.addWidget(self.auto_assign_btn)
        
        right_buttons_layout.addWidget(self.export_btn)
        right_buttons_layout.addWidget(self.clear_btn)
        
        status_layout.addLayout(right_buttons_layout)

        main_layout.addLayout(status_layout)

        # Table Section
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "", "Date", "Shift", "Area", "Start Time", "End Time",
            "Code", "Instructor", "Program/Group", "Mins", "Units"
        ])
        
        # Configuración de Header con Checkbox
        self.header = CheckBoxHeader(Qt.Orientation.Horizontal, self.table)
        self.table.setHorizontalHeader(self.header)
        self.header.checkBoxClicked.connect(self.toggle_all_rows)
        
        # Configuración de tabla
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Deshabilitar resize en la columna 0 (checkbox) - DESPUÉS de poner todos en Interactive
        self.header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.header.setSectionsClickable(True) # Asegurar que sean clickeables para sort
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(45)  # Ajuste para el padding
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # Configurar Hover Delegate
        self.hover_delegate = RowHoverDelegate(self.table, self.COLORS['ACCENT'])
        self.table.setItemDelegate(self.hover_delegate)
        self.table.setMouseTracking(True)
        self.table.cellEntered.connect(self.on_cell_entered)
        
        # Estilo de Tabla Shadcn + Scrollbars
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {self.COLORS['SURFACE']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 8px;
                gridline-color: transparent;
                outline: none;
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 12px;
                border-bottom: 1px solid {self.COLORS['BORDER']};
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QTableWidget::item:selected {{
                background-color: {self.COLORS['SURFACE_SECONDARY']};
                color: {self.COLORS['TEXT_PRIMARY']};
            }}
            QHeaderView::section {{
                background-color: #F4F4F5;
                color: {self.COLORS['TEXT_SECONDARY']};
                padding: 12px;
                border: none;
                border-bottom: 1px solid {self.COLORS['BORDER']};
                font-weight: 600;
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
            }}
            /* Scrollbars */
            QScrollBar:vertical {{
                border: none; background: {self.COLORS['SURFACE']};
                width:8px; margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.COLORS['BORDER']};
                min-height: 40px; border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                border: none; background: {self.COLORS['SURFACE']};
                height: 8px; margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {self.COLORS['BORDER']};
                min-width: 20px; border-radius: 4px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QTableWidget::corner {{
                background-color: {self.COLORS['SURFACE']};
                border: none;
            }}
        """)
        
        # Anchos de columna
        column_widths = {
            0: 40, 1: 120, 2: 100, 3: 120, 4: 120, 5: 120,
            6: 120, 7: 180, 8: 380, 9: 80, 10: 80
        }
        for col, width in column_widths.items():
            self.table.setColumnWidth(col, width)
        
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemChanged.connect(self.on_item_changed)
        main_layout.addWidget(self.table)

        self.simple_view_cb.setChecked(True)
        self.show()

    def on_cell_entered(self, row, column):
        """Maneja el evento de hover en las celdas."""
        self.hover_delegate.hover_row = row
        self.table.viewport().update()

    def leaveEvent(self, event):
        """Resetea el hover cuando el mouse sale de la ventana (opcional, mejor en la tabla)."""
        super().leaveEvent(event)
        # Idealmente subclassing QTableWidget para leaveEvent, pero esto ayuda


    def get_button_style(self, variant: str = "primary") -> str:
        """Genera estilo Shadcn para botones."""
        base_style = f"""
            QPushButton {{
                font-family: 'IBM Plex Sans', sans-serif;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 500;
                font-size: 14px;
            }}
            QPushButton::menu-indicator {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 8px;
                padding-right: 8px;
                right: 8px;
            }}
        """
        
        if variant == "primary":
            return base_style + f"""
                QPushButton {{
                    background-color: {self.COLORS['PRIMARY']};
                    color: {self.COLORS['PRIMARY_FOREGROUND']};
                    border: 1px solid {self.COLORS['PRIMARY']};
                }}
                QPushButton:hover {{
                    background-color: #27272A; /* Zinc-800 */
                }}
                QPushButton:disabled {{
                    background-color: {self.COLORS['SURFACE_SECONDARY']};
                    color: {self.COLORS['TEXT_SECONDARY']};
                    border: 1px solid {self.COLORS['BORDER']};
                }}
            """
        elif variant == "secondary":
            return base_style + f"""
                QPushButton {{
                    background-color: {self.COLORS['SURFACE_SECONDARY']};
                    color: {self.COLORS['TEXT_PRIMARY']};
                    border: 1px solid {self.COLORS['BORDER']};
                }}
                QPushButton:hover {{
                    background-color: {self.COLORS['BORDER']};
                }}
            """
        elif variant == "outline":
            return base_style + f"""
                QPushButton {{
                    background-color: transparent;
                    color: {self.COLORS['TEXT_PRIMARY']};
                    border: 1px solid {self.COLORS['BORDER']};
                }}
                QPushButton:hover {{
                    background-color: {self.COLORS['ACCENT']};
                }}
            """
        elif variant == "destructive":
            return base_style + f"""
                QPushButton {{
                    background-color: {self.COLORS['DESTRUCTIVE']};
                    color: white;
                    border: 1px solid {self.COLORS['DESTRUCTIVE']};
                }}
                QPushButton:hover {{
                    background-color: #DC2626; /* Red-600 */
                }}
                QPushButton:disabled {{
                    background-color: {self.COLORS['SURFACE_SECONDARY']};
                    color: {self.COLORS['TEXT_SECONDARY']};
                    border: 1px solid {self.COLORS['BORDER']};
                }}
            """
        elif variant == "ghost":
            return base_style + f"""
                QPushButton {{
                    background-color: transparent;
                    color: {self.COLORS['TEXT_PRIMARY']};
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {self.COLORS['ACCENT']};
                }}
            """
        return base_style

    def get_input_style(self) -> str:
        return f"""
            QLineEdit {{
                font-family: 'IBM Plex Sans', sans-serif;
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                padding: 8px 12px;
                background-color: {self.COLORS['SURFACE']};
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.COLORS['RING']};
            }}
            QLineEdit::placeholder {{
                color: {self.COLORS['TEXT_SECONDARY']};
            }}
        """

    def get_menu_style(self) -> str:
        return f"""
            QMenu {{
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 14px;
                background-color: {self.COLORS['SURFACE']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 12px;
                border-radius: 4px;
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QMenu::item:selected {{
                background-color: {self.COLORS['ACCENT']};
                color: {self.COLORS['TEXT_PRIMARY']};
            }}
        """
    
    def get_combobox_style(self) -> str:
        return f"""
            QComboBox {{
                font-family: 'IBM Plex Sans', sans-serif;
                padding: 8px 12px;
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                background-color: {self.COLORS['SURFACE']};
                color: {self.COLORS['TEXT_PRIMARY']};
                font-size: 14px;
            }}
            QComboBox:hover {{
                border: 1px solid {self.COLORS['RING']};
            }}
            QComboBox:focus {{
                border: 1px solid {self.COLORS['RING']};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                font-family: 'IBM Plex Sans', sans-serif;
                background-color: {self.COLORS['SURFACE']};
                border: 1px solid {self.COLORS['BORDER']};
                border-radius: 6px;
                selection-background-color: {self.COLORS['ACCENT']};
                selection-color: {self.COLORS['TEXT_PRIMARY']};
                padding: 4px;
            }}
        """

    def load_files(self):
        """Carga archivos Excel."""
        # Obtener ruta de Descargas
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Excel files",
            downloads_path,  # Directorio inicial: Descargas
            "Excel Files (*.xlsx *.xls)"
        )

        if file_paths:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.status_label.setText("Processing files...")
            self.error_label.setText("")

            # Worker thread para NO bloquear la UI
            self.worker = ExcelWorker(file_paths)
            self.worker.progress.connect(self.on_progress)
            self.worker.finished.connect(self.on_files_loaded)
            self.worker.start()

    def on_progress(self, message: str):
        """Actualiza el progreso."""
        self.status_label.setText(message)

    def on_files_loaded(self, schedules: List[Schedule], errors: List[str]):
        """Callback cuando los archivos terminan de procesarse."""
        self.progress_bar.setVisible(False)

        if schedules:
            # 1. Crear un set de firmas de los horarios existentes para búsqueda rápida
            # Usamos una tupla de los valores del objeto para identificar unicidad
            existing_signatures = {tuple(s.to_dict().values()) for s in self.schedules}
            
            new_unique_schedules = []
            duplicates_count = 0
            
            for schedule in schedules:
                signature = tuple(schedule.to_dict().values())
                if signature not in existing_signatures:
                    new_unique_schedules.append(schedule)
                    existing_signatures.add(signature) # Añadir al set local para evitar duplicados dentro del mismo lote
                else:
                    duplicates_count += 1
            
            if new_unique_schedules:
                self.schedules.extend(new_unique_schedules)
                self.populate_time_filter()  # Update time filter dropdown with available times
                self.update_table()
                
                msg = f"✓ Added {len(new_unique_schedules)} new records"
                if duplicates_count > 0:
                    msg += f" ({duplicates_count} duplicates skipped)"
                self.status_label.setText(msg)
            else:
                if duplicates_count > 0:
                    self.status_label.setText(f"All {duplicates_count} records were duplicates")
                else:
                    self.status_label.setText("No valid data found")
            
            # Limpiar selección al cargar nuevos archivos (opcional, o mantenerla)
            # self.selected_schedule_ids.clear()

        else:
            self.status_label.setText("No valid data found")

        if errors:
            self.error_label.setText("Errors: " + "; ".join(errors[:3]))

    def update_table(self):
        """Actualiza la tabla - ⚡⚡ SUPER OPTIMIZADO para tablas grandes."""
        # NOTA: Ya no leemos la tabla para guardar selección, usamos self.selected_schedule_ids
        
        # Aplicar filtros
        filtered_schedules = self.schedules
        
        if self.filter_instructor:
            # Separar términos por coma y hacer trim
            instructor_terms = [term.strip().lower() for term in self.filter_instructor.split(',') if term.strip()]
            filtered_schedules = [
                s for s in filtered_schedules 
                if any(term in s.instructor.lower() for term in instructor_terms)
            ]
        
        if self.filter_program:
            # Separar términos por coma y hacer trim
            program_terms = [term.strip().lower() for term in self.filter_program.split(',') if term.strip()]
            filtered_schedules = [
                s for s in filtered_schedules 
                if any(term in s.program.lower() for term in program_terms)
            ]
        
        if self.filter_time:
            # Filtrar por hora (intervalo de 1 hora)
            # self.filter_time viene como "HH:00"
            try:
                target_hour = int(self.filter_time.split(':')[0])
                
                new_filtered = []
                for s in filtered_schedules:
                    # Verificar si alguno de los horarios de inicio cae en la hora seleccionada
                    match = False
                    times = [t.strip() for t in s.start_time.split(',')]
                    for t in times:
                        t_24h = s._convert_single_time_to_24h(t)
                        if ':' in t_24h:
                            h = int(t_24h.split(':')[0])
                            if h == target_hour:
                                match = True
                                break
                    if match:
                        new_filtered.append(s)
                filtered_schedules = new_filtered
            except Exception as e:
                print(f"Error filtering time: {e}")
            
        # Filtrar por cruces si está activado
        if self.show_overlaps_cb.isChecked():
            conflicts = self.find_conflicts(filtered_schedules)
            conflict_ids = {id(s) for s in conflicts}
            filtered_schedules = [s for s in filtered_schedules if id(s) in conflict_ids]
        
        # Ordenar por start_time por defecto
        filtered_schedules.sort(key=lambda s: self.get_schedule_minutes(s.start_time.split(',')[0]) if s.start_time else -1)

        
        # Guardar referencia a los horarios visibles
        self.visible_schedules = filtered_schedules
        
        # ⚡ OPTIMIZACIÓN 1: Comparación rápida usando hash
        # Crear un mapa de schedules actuales por posición para comparación O(1)
        current_schedule_map = {}
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                schedule = item.data(Qt.ItemDataRole.UserRole)
                if schedule:
                    current_schedule_map[i] = schedule
        
        # Verificar si hay cambios reales usando hash
        needs_full_update = False
        if len(current_schedule_map) != len(filtered_schedules):
            needs_full_update = True
        else:
            # Comparar hashes para detectar cambios
            for i, schedule in enumerate(filtered_schedules):
                if i not in current_schedule_map or current_schedule_map[i] != schedule:
                    needs_full_update = True
                    break
        
        # ⚡ OPTIMIZACIÓN 2: Si no hay cambios, solo actualizar checkboxes
        if not needs_full_update:
            # Solo actualizar el estado de los checkboxes si cambió
            self.table.blockSignals(True)
            try:
                for i in range(self.table.rowCount()):
                    item = self.table.item(i, 0)
                    if item:
                        schedule = item.data(Qt.ItemDataRole.UserRole)
                        if schedule:
                            should_be_checked = id(schedule) in self.selected_schedule_ids
                            is_checked = item.checkState() == Qt.CheckState.Checked
                            if should_be_checked != is_checked:
                                item.setCheckState(Qt.CheckState.Checked if should_be_checked else Qt.CheckState.Unchecked)
                
                # Actualizar selección visual
                self.table.clearSelection()
                for i in range(self.table.rowCount()):
                    item = self.table.item(i, 0)
                    if item and item.checkState() == Qt.CheckState.Checked:
                        self.table.selectRow(i)
            finally:
                self.table.blockSignals(False)
                self.update_counter()
            return  # ⚡ Salir temprano - no hay cambios en datos
        
        # Solo llegar aquí si realmente hay cambios en los datos
        current_count = self.table.rowCount()
        new_count = len(filtered_schedules)
        
        # Deshabilitar ordenamiento y señales solo durante la actualización
        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        
        try:
            # ⚡ OPTIMIZACIÓN 3: Batch updates
            # Ajustar número de filas una sola vez
            if current_count != new_count:
                self.table.setRowCount(new_count)
            
            # Pre-crear todos los items necesarios (más eficiente)
            for i, schedule in enumerate(filtered_schedules):
                # Verificar si esta fila específica cambió usando hash
                existing_item = self.table.item(i, 0)
                row_changed = (existing_item is None or 
                              existing_item.data(Qt.ItemDataRole.UserRole) != schedule)
                
                if row_changed:
                    # Checkbox Item (Col 0)
                    chk_item = QTableWidgetItem()
                    chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    
                    # RESTAURAR el estado de selección usando el set persistente
                    if id(schedule) in self.selected_schedule_ids:
                        chk_item.setCheckState(Qt.CheckState.Checked)
                    else:
                        chk_item.setCheckState(Qt.CheckState.Unchecked)
                    
                    chk_item.setData(Qt.ItemDataRole.UserRole, schedule)
                    self.table.setItem(i, 0, chk_item)

                    row_data = schedule.to_list_display()
                    
                    if self.simple_view:
                        # Modo simple: combinar Start Time y End Time en una sola columna Time
                        time_combined = f"{row_data[3]} - {row_data[4]}"  # start_time - end_time
                        simple_data = [row_data[0], row_data[2], time_combined, row_data[6], row_data[7], row_data[8], row_data[9]]
                        
                        for j, value in enumerate(simple_data):
                            item = QTableWidgetItem(str(value))
                            # Habilitar edición para permitir seleccionar texto (Delegate lo hace read-only)
                            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                            
                            # Centrar columnas: Date, Area, Time, Mins, Units
                            if j in [0, 1, 2, 5, 6]:
                                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            
                            self.table.setItem(i, j + 1, item)
                    else:
                        # Modo normal: todas las columnas
                        for j, value in enumerate(row_data):
                            item = QTableWidgetItem(str(value))
                            # Habilitar edición para permitir seleccionar texto
                            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                            
                            # Centrar columnas específicas
                            if (j + 1) in [1, 2, 3, 4, 5, 6, 9, 10]:
                                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            
                            self.table.setItem(i, j + 1, item)
                else:
                    # La fila no cambió, solo actualizar checkbox si es necesario
                    if existing_item:
                        if id(schedule) in self.selected_schedule_ids:
                            if existing_item.checkState() != Qt.CheckState.Checked:
                                existing_item.setCheckState(Qt.CheckState.Checked)
                        else:
                            if existing_item.checkState() != Qt.CheckState.Unchecked:
                                existing_item.setCheckState(Qt.CheckState.Unchecked)
            
            # RESTAURAR la selección visual de las filas con checkboxes marcados
            self.table.clearSelection()
            for i in range(self.table.rowCount()):
                item = self.table.item(i, 0)
                if item and item.checkState() == Qt.CheckState.Checked:
                    self.table.selectRow(i)

        finally:
            self.table.blockSignals(False)
            
            # Mostrar indicador de ordenamiento en la columna de hora (Start Time)
            # Columna 3 en vista simple, 4 en vista completa
            sort_col = 3 if self.simple_view else 4
            self.table.horizontalHeader().setSortIndicator(sort_col, Qt.SortOrder.AscendingOrder)

            if sorting_was_enabled:
                self.table.setSortingEnabled(True)
            
            self.update_counter()
            
            # Enable Auto Assign only if there are schedules
            self.auto_assign_btn.setEnabled(len(self.schedules) > 0)
    
    def on_filter_changed(self):
        """Callback cuando cambia el filtro - con debouncing para mejor performance."""
        # Reiniciar el timer cada vez que el usuario escribe
        self.filter_timer.stop()
        self.filter_timer.start()
    
    def on_time_filter_changed(self, text: str):
        """Callback cuando cambia el filtro de tiempo."""
        if text == "All Times":
            self.filter_time = ""
        else:
            self.filter_time = text
        self.update_table()
    
    def populate_time_filter(self):
        """Populate time filter dropdown with unique times from schedules in 24h format."""
        # Block signals to prevent triggering updates while populating
        self.filter_time_combo.blockSignals(True)
        
        # Get current selection
        current_selection = self.filter_time_combo.currentText()
        
        # Clear existing items
        self.filter_time_combo.clear()
        self.filter_time_combo.addItem("All Times")
        
        # Extract unique start times from schedules and convert to 24h (HOURLY ONLY)
        unique_hours = set()
        for schedule in self.schedules:
            if schedule.start_time:
                # Handle comma-separated times
                times = [t.strip() for t in schedule.start_time.split(',')]
                for time_12h in times:
                    if time_12h:
                        # Convert to 24h format
                        time_24h = schedule._convert_single_time_to_24h(time_12h)
                        # Extract Hour
                        if ':' in time_24h:
                            hour = time_24h.split(':')[0]
                            unique_hours.add(f"{int(hour):02d}:00")
        
        # Sort times and add to combobox
        sorted_times = sorted(list(unique_hours))
        for time in sorted_times:
             self.filter_time_combo.addItem(time)
        
        # Restore previous selection if it still exists
        index = self.filter_time_combo.findText(current_selection)
        if index >= 0:
            self.filter_time_combo.setCurrentIndex(index)
        else:
            self.filter_time_combo.setCurrentIndex(0)
        
        # Re-enable signals
        self.filter_time_combo.blockSignals(False)
    
    def _apply_filters(self):
        """Aplica los filtros después del debouncing."""
        self.filter_instructor = self.filter_instructor_input.text()
        self.filter_program = self.filter_program_input.text()
        self.update_table()
    
    def clear_filters(self):
        """Limpia todos los filtros."""
        self.filter_instructor_input.clear()
        self.filter_program_input.clear()
        self.filter_time_combo.setCurrentIndex(0)  # Reset to "All Times"
        self.show_overlaps_cb.setChecked(False)
        self.filter_instructor = ""
        self.filter_program = ""
        self.filter_time = ""
        self.update_table()
    
    def toggle_simple_view(self):
        """Alterna entre vista simple y completa."""
        self.simple_view = self.simple_view_cb.isChecked()
        
        # Guardar el estado de selección ANTES de cambiar la vista
        selected_schedules = set()
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                schedule = item.data(Qt.ItemDataRole.UserRole)
                selected_schedules.add(id(schedule))
        
        # Guardar el estado del header checkbox
        header_was_on = self.header.isOn
        
        # Limpiar completamente la tabla antes de cambiar el número de columnas
        self.table.setRowCount(0)
        
        # Cambiar número de columnas y headers
        if self.simple_view:
            self.table.setColumnCount(8)  # Checkbox, Date, Area, Time, Instructor, Program/Group, Mins, Units
            self.table.setHorizontalHeaderLabels([
                "", "Date", "Area", "Time", "Instructor", "Program/Group", "Mins", "Units"
            ])
            # Ajustar anchos de columna para vista simple
            self.table.setColumnWidth(0, 40)
            self.table.setColumnWidth(1, 120)
            self.table.setColumnWidth(2, 120)
            self.table.setColumnWidth(3, 120)  # Time column más ancha
            self.table.setColumnWidth(4, 200)
            self.table.setColumnWidth(5, 600)
            self.table.setColumnWidth(6, 80)
            self.table.setColumnWidth(7, 80)
        else:
            self.table.setColumnCount(11)  # Vista completa
            self.table.setHorizontalHeaderLabels([
                "", "Date", "Shift", "Area", "Start Time", "End Time",
                "Code", "Instructor", "Program/Group", "Mins", "Units"
            ])
            # Restaurar anchos de columna originales
            column_widths = {
                0: 40, 1: 120, 2: 100, 3: 120, 4: 120, 5: 120,
                6: 120, 7: 180, 8: 380, 9: 80, 10: 80
            }
            for col, width in column_widths.items():
                self.table.setColumnWidth(col, width)
        
        # Actualizar la tabla con los datos
        self.update_table()
        
        # RESTAURAR el estado de selección DESPUÉS de actualizar la tabla
        self.table.blockSignals(True)
        try:
            for i in range(self.table.rowCount()):
                item = self.table.item(i, 0)
                if item:
                    schedule = item.data(Qt.ItemDataRole.UserRole)
                    if id(schedule) in selected_schedules:
                        item.setCheckState(Qt.CheckState.Checked)
                        # Seleccionar visualmente la fila también
                        self.table.selectRow(i)
            
            # Restaurar el estado del header checkbox
            self.header.isOn = header_was_on
            self.header.viewport().update()
            
            self.update_counter()
        finally:
            self.table.blockSignals(False)

    def on_selection_changed(self):
        """Callback cuando cambia la selección (Sincronización Bidireccional)."""
        # Evitar recursión si estamos actualizando desde los checkboxes
        if self.table.signalsBlocked():
            return

        self.table.blockSignals(True)
        try:
            selected_rows = {index.row() for index in self.table.selectedIndexes()}
            
            # Actualizar solo los checkboxes necesarios
            for i in range(self.table.rowCount()):
                item = self.table.item(i, 0)
                if not item: continue
                
                should_be_checked = i in selected_rows
                current_state = item.checkState() == Qt.CheckState.Checked
                
                if should_be_checked != current_state:
                    item.setCheckState(Qt.CheckState.Checked if should_be_checked else Qt.CheckState.Unchecked)
                    
                    # Actualizar persistencia manualmente ya que las señales están bloqueadas
                    schedule = item.data(Qt.ItemDataRole.UserRole)
                    if schedule:
                        if should_be_checked:
                            self.selected_schedule_ids.add(id(schedule))
                        else:
                            self.selected_schedule_ids.discard(id(schedule))
            
            self.update_counter()
        finally:
            self.table.blockSignals(False)

    def on_item_changed(self, item):
        """Maneja cambios en los items (checkboxes) -> Actualiza selección."""
        if item.column() == 0:
            # Evitar recursión si estamos actualizando desde la selección
            if self.table.signalsBlocked():
                return

            self.table.blockSignals(True)
            try:
                row = item.row()
                schedule = item.data(Qt.ItemDataRole.UserRole)
                
                if item.checkState() == Qt.CheckState.Checked:
                    if schedule: self.selected_schedule_ids.add(id(schedule))
                    
                    # Seleccionar fila sin deseleccionar otras (modo multi)
                    selection_model = self.table.selectionModel()
                    selection_model.select(self.table.model().index(row, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
                else:
                    if schedule: self.selected_schedule_ids.discard(id(schedule))
                    
                    # Deseleccionar fila
                    selection_model = self.table.selectionModel()
                    selection_model.select(self.table.model().index(row, 0), QItemSelectionModel.SelectionFlag.Deselect | QItemSelectionModel.SelectionFlag.Rows)
                
                self.update_counter()
                
                # Sincronizar header
                if item.checkState() == Qt.CheckState.Unchecked and self.header.isOn:
                    self.header.isOn = False
                    self.header.viewport().update()
            finally:
                self.table.blockSignals(False)

    def toggle_all_rows(self, state: bool):
        """Marca o desmarca todas las filas - OPTIMIZADO con operaciones batch."""
        self.table.blockSignals(True)
        try:
            check_state = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
            row_count = self.table.rowCount()
            
            # Actualizar selección visual primero (más rápido)
            if state:
                self.table.selectAll()
            else:
                self.table.clearSelection()
            
            # Actualizar checkboxes en batch (sin desencadenar eventos individuales)
            for i in range(row_count):
                item = self.table.item(i, 0)
                if item:
                    item.setCheckState(check_state)
                    # Actualizar persistencia
                    schedule = item.data(Qt.ItemDataRole.UserRole)
                    if schedule:
                        if state:
                            self.selected_schedule_ids.add(id(schedule))
                        else:
                            self.selected_schedule_ids.discard(id(schedule))
                
            self.update_counter()
        finally:
            self.table.blockSignals(False)

    def update_counter(self):
        """Actualiza el contador y etiquetas de estado."""
        total = len(self.schedules)
        visible = self.table.rowCount()
        
        # Contar marcados
        checked_count = 0
        for i in range(visible):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked_count += 1
        
        selected = checked_count
        
        # Calcular overlaps (optimizado)
        overlaps_count = 0
        if self.show_overlaps_cb.isChecked() or len(self.visible_schedules) < 2000:
             conflicts = self.find_conflicts(self.visible_schedules)
             overlaps_count = len(conflicts)
        else:
             overlaps_count = "?"
        
        # Actualizar Stats Labels
        if visible < total:
            self.records_label.setText(f"Records: {visible}/{total}")
        else:
            self.records_label.setText(f"Records: {total}")
            
        self.overlaps_label.setText(f"Overlaps: {overlaps_count}")
            
        # Actualizar Selection Label
        self.selection_label.setText(f"Selected: {selected}")

    def _format_schedule_for_clipboard(self, schedule: Schedule) -> str:
        """Formatea un horario para el portapapeles según el formato solicitado."""
        start = schedule._convert_to_24h(schedule.start_time)
        end = schedule._convert_to_24h(schedule.end_time)
        
        return f"{schedule.date}\n{schedule.program}\n{start} - {end}"

    def copy_all_schedule(self):
        """Copia todo el horario al portapapeles."""
        if not self.schedules:
            custom_message_box(self, "Warning", "No data to copy", QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok)
            return
        
        lines = []
        for schedule in self.schedules:
            line = "\t".join(schedule.to_list())
            lines.append(line)
        
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        self.status_label.setText(f"✓ Copied {len(self.schedules)} records (full schedule)")
        self.error_label.setText("")
    
    def copy_instructors(self):
        """Copia la lista de instructores únicos al portapapeles."""
        if not self.schedules:
            custom_message_box(self, "Warning", "No data to copy", QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok)
            return
        
        # Obtener instructores únicos
        instructors = sorted(set(schedule.instructor for schedule in self.schedules))
        
        text = "\n".join(instructors)
        QApplication.clipboard().setText(text)
        self.status_label.setText(f"✓ Copied {len(instructors)} unique instructor(s)")
        self.error_label.setText("")
    
    def select_all(self):
        """Selecciona o deselecciona todo (vía checkbox header)."""
        # Invertir estado actual del header
        new_state = not self.header.isOn
        self.header.isOn = new_state
        self.header.checkBoxClicked.emit(new_state)
        self.header.viewport().update()

    def copy_selected(self):
        """Copia las filas seleccionadas (marcadas) al portapapeles."""
        rows_to_copy = []
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() == Qt.CheckState.Checked:
                rows_to_copy.append(i)
        
        if not rows_to_copy:
            custom_message_box(self, "Warning", "No rows selected", QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok)
            return

        lines = []
        for row in rows_to_copy:
            # Obtener el Schedule desde los datos almacenados en la fila (col 0)
            first_item = self.table.item(row, 0)
            schedule = first_item.data(Qt.ItemDataRole.UserRole)
            line = self._format_schedule_for_clipboard(schedule)
            lines.append(line)

        text = "\n\n".join(lines)
        QApplication.clipboard().setText(text)
        self.status_label.setText(f"✓ Copied {len(rows_to_copy)} record(s)")
        self.error_label.setText("")
    
    def show_context_menu(self, position):
        """Muestra el menú contextual al hacer click derecho en la tabla."""
        # Crear menú contextual
        context_menu = QMenu(self)
        context_menu.setStyleSheet(self.get_menu_style())
        
        # Obtener la fila donde se hizo click
        row = self.table.rowAt(position.y())
        
        if row >= 0:  # Asegurar que se hizo click en una fila válida
            # Verificar si hay filas marcadas
            checked_count = 0
            for i in range(self.table.rowCount()):
                if self.table.item(i, 0).checkState() == Qt.CheckState.Checked:
                    checked_count += 1
            
            if checked_count > 0:
                # Múltiples filas seleccionadas (marcadas)
                copy_action = context_menu.addAction(f"Copy {checked_count} selected Rows")
                copy_action.triggered.connect(self.copy_selected)
                                
                delete_action = context_menu.addAction(f"Delete {checked_count} selected Rows")
                delete_action.triggered.connect(self.delete_selected)
                
                context_menu.addSeparator()
                
                deselect_action = context_menu.addAction("Deselect All")
                deselect_action.triggered.connect(lambda: self.toggle_all_rows(False))
            else:
                # Solo una fila (click derecho sin selección previa)
                copy_action = context_menu.addAction("Copy Row")
                copy_action.triggered.connect(lambda: self.copy_single_row(row))
            
            # Mostrar el menú en la posición del cursor
            context_menu.exec(self.table.viewport().mapToGlobal(position))
    
    def copy_single_row(self, row: int):
        """Copia una sola fila al portapapeles."""
        if row < 0 or row >= self.table.rowCount():
            return
        
        # Obtener el Schedule desde los datos almacenados en la fila
        first_item = self.table.item(row, 0)
        schedule = first_item.data(Qt.ItemDataRole.UserRole)
        line = self._format_schedule_for_clipboard(schedule)
        
        QApplication.clipboard().setText(line)
        self.status_label.setText("✓ Copied 1 record")
        self.error_label.setText("")

    def delete_selected(self):
        """Elimina las filas seleccionadas - CORREGIDO para trabajar con filtros Y ordenamiento."""
        rows_to_delete = []
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() == Qt.CheckState.Checked:
                rows_to_delete.append(i)
        
        if not rows_to_delete:
            custom_message_box(self, "Warning", "No rows selected", QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok)
            return

        count = len(rows_to_delete)
        reply = custom_message_box(
            self,
            "Confirm deletion",
            f"Are you sure you want to delete {count} record(s)?",
            QMessageBox.Icon.Question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Obtener los objetos Schedule directamente desde los datos de la tabla
            schedules_to_delete = []
            for row in rows_to_delete:
                first_item = self.table.item(row, 0)
                schedule = first_item.data(Qt.ItemDataRole.UserRole)
                schedules_to_delete.append(schedule)
            
            # Eliminar de la lista principal
            for schedule in schedules_to_delete:
                if schedule in self.schedules:
                    self.schedules.remove(schedule)
            
            # Limpiar selección visual y estado del header checkbox
            self.table.clearSelection()
            self.header.isOn = False
            self.header.viewport().update()
            
            self.populate_time_filter()  # Update time filter dropdown
            self.update_table()
            self.status_label.setText(f"✓ Deleted {count} record(s)")
            self.error_label.setText("")

    def clear_all(self):
        """Limpia todos los datos."""
        if not self.schedules:
            return

        reply = custom_message_box(
            self,
            "Confirm deletion",
            "Are you sure you want to delete ALL data?",
            QMessageBox.Icon.Question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.schedules.clear()
            self.table.setRowCount(0)
            self.populate_time_filter()  # Update time filter dropdown
            self.update_counter()
            self.auto_assign_btn.setEnabled(False)
            self.status_label.setText("✓ All data has been deleted")
            self.error_label.setText("")

    def export_to_excel(self):
        """Exporta los datos a Excel."""
        if not self.schedules:
            custom_message_box(self, "Warning", "No data to export", QMessageBox.Icon.Warning, QMessageBox.StandardButton.Ok)
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"schedule_{timestamp}.xlsx"

        # Ruta completa: Downloads + nombre de archivo
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        default_full_path = os.path.join(downloads_path, default_name)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel file",
            default_full_path,  # Ruta completa con nombre de archivo
            "Excel Files (*.xlsx)"
        )

        if file_path:
            try:
                data = [s.to_list() for s in self.schedules]
                df = pd.DataFrame(data, columns=[
                    "date", "shift", "area", "start_time", "end_time",
                    "code", "instructor", "program", "minutes", "units"
                ])
                df.to_excel(file_path, index=False, engine="openpyxl")
                
                self.status_label.setText(f"✓ File exported: {os.path.basename(file_path)}")
                self.error_label.setText("")
            except Exception as e:
                custom_message_box(self, "Error", f"Export error: {str(e)}", QMessageBox.Icon.Critical, QMessageBox.StandardButton.Ok)

    def open_auto_assign_modal(self):
        """Abre el modal de asignación automática."""
        dialog = AutoAssignDialog(self)
        # Pasar los horarios actuales (filtrados o todos, según lógica de negocio)
        # Aquí pasamos todos los horarios cargados
        dialog.schedules = self.schedules 
        
        # Iniciar procesamiento automáticamente
        dialog.process_data()
        
        if dialog.exec():
            # El diálogo se cerró con "Execute" (aceptar)
            pass

    def open_meeting_search_dialog(self):
        """Abre el diálogo de búsqueda de reuniones."""
        dialog = MeetingSearchDialog(self)
        dialog.exec()

        




    def get_schedule_minutes(self, time_str: str) -> int:
        """Convierte una hora 'HH:MM AM/PM' a minutos desde medianoche."""
        try:
            time_str = time_str.strip().upper()
            is_pm = 'PM' in time_str
            is_am = 'AM' in time_str
            
            clean_time = time_str.replace('AM', '').replace('PM', '').strip()
            
            if ':' in clean_time:
                parts = clean_time.split(':')
                hours = int(parts[0])
                minutes = int(parts[1])
            else:
                hours = int(clean_time)
                minutes = 0
                
            if is_pm and hours != 12:
                hours += 12
            elif is_am and hours == 12:
                hours = 0
                
            return hours * 60 + minutes
        except:
            return -1

    def find_conflicts(self, schedules: List[Schedule]) -> List[Schedule]:
        """Encuentra horarios con conflictos (mismo instructor o grupo a la misma hora)."""
        conflicting_map = {}  # id -> Schedule
        
        # Agrupar por fecha para reducir comparaciones
        by_date = {}
        for s in schedules:
            if s.date not in by_date:
                by_date[s.date] = []
            by_date[s.date].append(s)
            
        for date, date_schedules in by_date.items():
            n = len(date_schedules)
            for i in range(n):
                s1 = date_schedules[i]
                
                # Helper para obtener rangos de tiempo (start, end) en minutos
                def get_time_ranges(start_str, end_str):
                    starts = [t.strip() for t in start_str.split(',')]
                    ends = [t.strip() for t in end_str.split(',')]
                    ranges = []
                    for st, en in zip(starts, ends):
                        start_min = self.get_schedule_minutes(st)
                        end_min = self.get_schedule_minutes(en)
                        if start_min != -1 and end_min != -1:
                            ranges.append((start_min, end_min))
                    return ranges

                ranges1 = get_time_ranges(s1.start_time, s1.end_time)
                
                for j in range(i + 1, n):
                    s2 = date_schedules[j]
                    ranges2 = get_time_ranges(s2.start_time, s2.end_time)
                    
                    has_overlap = False
                    for start1, end1 in ranges1:
                        for start2, end2 in ranges2:
                            # Verificar superposición: max(start1, start2) < min(end1, end2)
                            if max(start1, start2) < min(end1, end2):
                                has_overlap = True
                                break
                        if has_overlap:
                            break
                    
                    if has_overlap:
                        # Verificar conflicto de Instructor
                        if s1.instructor.strip().lower() == s2.instructor.strip().lower():
                            conflicting_map[id(s1)] = s1
                            conflicting_map[id(s2)] = s2
                        
                        # Verificar conflicto de Grupo
                        if s1.program.strip() and s2.program.strip() and s1.program.strip().lower() == s2.program.strip().lower():
                            conflicting_map[id(s1)] = s1
                            conflicting_map[id(s2)] = s2
                            
        return list(conflicting_map.values())

    # ============================================================================
    # AUTO-UPDATE SYSTEM
    # ============================================================================
    
    def check_updates(self):
        """Inicia la verificación de actualizaciones."""
        print("Checking for updates...")
        version_manager.update_available.connect(self.on_update_available)
        version_manager.no_update.connect(lambda: print("No updates available."))
        version_manager.error.connect(self.on_update_error)
        version_manager.download_progress.connect(self.on_download_progress)
        version_manager.download_complete.connect(self.on_download_complete)
        
        version_manager.check_for_updates()

    def on_update_available(self, version, url, notes):
        """Muestra diálogo de actualización OBLIGATORIA."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Update Required")
        msg.setText(f"A new version ({version}) is available.")
        msg.setInformativeText(f"This update is mandatory to continue using Chronos.\n\nRelease Notes:\n{notes}")
        msg.setIcon(QMessageBox.Icon.Warning)
        # Solo botón de Update (Yes)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes)
        msg.button(QMessageBox.StandardButton.Yes).setText("Update Now")
        
        # Bloquear cierre con X si es posible, o manejar el resultado
        msg.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            # Iniciar descarga
            self.download_dialog = QProgressDialog("Downloading update...", None, 0, 100, self) # Sin botón cancelar
            self.download_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            self.download_dialog.setCancelButton(None) # Deshabilitar cancelar
            self.download_dialog.show()
            version_manager.download_update(url)
        else:
            # Si cierran el diálogo de alguna forma, salir de la app
            sys.exit(0)

    def on_download_progress(self, percent):
        """Actualiza la barra de progreso de descarga."""
        if hasattr(self, 'download_dialog'):
            self.download_dialog.setValue(percent)

    def on_download_complete(self, file_path):
        """Instala la actualización descargada."""
        if hasattr(self, 'download_dialog'):
            self.download_dialog.close()
            
        # Aplicar directamente sin preguntar, ya que es obligatorio
        version_manager.apply_update(file_path)

    def on_update_error(self, error_msg):
        """Muestra error de actualización."""
        if hasattr(self, 'download_dialog'):
            self.download_dialog.close()
        
        QMessageBox.critical(self, "Update Error", f"Failed to update: {error_msg}\nThe application will now close.")
        sys.exit(1)


# ============================================================================
# MAIN
# ============================================================================

def main():
    app = QApplication(sys.argv)
    
    # Estilo global
    app.setStyle("Fusion")
    
    # Intentar restaurar sesión guardada
    supabase_client = None
    user_info = None
    config = None
    
    print("Checking for saved session...")
    session_data = session_manager.load_session()
    
    if session_data:
        # Sesión restaurada exitosamente
        supabase_client, user_info, config = session_data
        auth_manager.set_client(supabase_client) # Registrar cliente autenticado
        print(f"✓ Auto-login successful for {user_info.get('email', 'user')}")
    else:
        # No hay sesión guardada o expiró, mostrar login
        print("No saved session found, showing login dialog...")
        login_dialog = LoginDialog()
        if login_dialog.exec() != QDialog.DialogCode.Accepted:
            # Usuario canceló o falló el login
            config_manager.clear_cache()
            sys.exit(0)
        
        # Obtener datos del login
        supabase_client = login_dialog.supabase_client
        user_info = login_dialog.user_info
        config = login_dialog.config
        auth_manager.set_client(supabase_client) # Registrar cliente autenticado
    
    # Obtener configuración descifrada
    global ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET
    ZOOM_CLIENT_ID = config.get("ZOOM_CLIENT_ID")
    ZOOM_CLIENT_SECRET = config.get("ZOOM_CLIENT_SECRET")
    
    # Verificar que se cargaron las credenciales
    if not ZOOM_CLIENT_ID or not ZOOM_CLIENT_SECRET:
        QMessageBox.critical(
            None,
            "Configuration Error",
            "Could not load Zoom credentials from the database."
        )
        sys.exit(1)
    
    # Iniciar aplicación principal
    window = SchedulePlanner()
    
    # Limpiar credenciales al cerrar
    def cleanup():
        config_manager.clear_cache()
        print("Session cleaned up")
    
    app.aboutToQuit.connect(cleanup)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
