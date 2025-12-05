"""
Chronos - Excel Service
Servicio para parsing y procesamiento de archivos Excel.
"""

import re
import logging
from typing import List, Optional

import pandas as pd

from app.models.schedule import Schedule


logger = logging.getLogger(__name__)


# =============================================================================
# FUNCIONES AUXILIARES DE EXTRACCIÓN
# =============================================================================

def extract_parenthesized_schedule(text: str) -> str:
    """Extrae contenido entre paréntesis."""
    matches = re.findall(r"\((.*?)\)", str(text))
    return ", ".join(matches) if matches else str(text)


def extract_keyword_from_text(text: str) -> Optional[str]:
    """Extrae keywords predefinidos del texto."""
    predefined_keywords = ["CORPORATE", "HUB", "LA MOLINA", "BAW", "KIDS"]
    for keyword in predefined_keywords:
        if re.search(rf"\b{keyword}\b", str(text), re.IGNORECASE):
            return keyword
    return None


def filter_special_tags(text: str) -> Optional[str]:
    """Filtra tags especiales del texto."""
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
    """Extrae duración o keyword del texto."""
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
    """Formatea períodos de tiempo."""
    return string.replace("a.m.", "AM").replace("p.m.", "PM")


def determine_shift_by_time(start_time: str) -> str:
    """Determina el turno basado en la hora de inicio."""
    try:
        start_time_24h = pd.to_datetime(start_time).strftime("%H:%M")
        return "P. ZUÑIGA" if start_time_24h < "14:00" else "H. GARCIA"
    except Exception:
        return "H. GARCIA"


# =============================================================================
# FUNCIONES DE PARSING
# =============================================================================

def parse_excel_file(file_path: str) -> List[Schedule]:
    """
    Parsea un archivo Excel original y extrae una lista de horarios.
    
    Args:
        file_path: Ruta al archivo Excel
        
    Returns:
        Lista de objetos Schedule
        
    Raises:
        Exception: Si hay error al parsear el archivo
    """
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

                # Pre-calcular conteos de grupos para evitar O(N^2)
                try:
                    group_counts = df.iloc[6:, 17].value_counts().to_dict()
                except (KeyError, IndexError):
                    group_counts = {}

                # Usar itertuples para iteración rápida
                for row in df.iloc[6:].itertuples(index=False, name=None):
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
        logger.exception(f"Error parsing Excel file: {file_path}")
        raise Exception(f"Error al parsear el archivo: {str(e)}")

    return schedules


def parse_exported_excel_file(file_path: str) -> List[Schedule]:
    """
    Parsea un archivo Excel exportado (ya procesado) y carga los horarios.
    
    Args:
        file_path: Ruta al archivo Excel exportado
        
    Returns:
        Lista de objetos Schedule
        
    Raises:
        Exception: Si hay error al parsear el archivo
    """
    schedules: List[Schedule] = []
    
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
        
        # Verificar columnas esperadas (snake_case)
        expected_columns = [
            "date", "shift", "area", "start_time", "end_time", 
            "code", "instructor", "program", "minutes", "units"
        ]
        
        if not all(col in df.columns for col in expected_columns):
            raise Exception("File format doesn't match exported schedule format")
        
        for _, row in df.iterrows():
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
            except Exception:
                continue
    
    except Exception as e:
        logger.exception(f"Error parsing exported Excel file: {file_path}")
        raise Exception(f"Error parsing exported file: {str(e)}")
    
    return schedules


def detect_file_type(file_path: str) -> str:
    """
    Detecta si es un archivo original o exportado.
    
    Args:
        file_path: Ruta al archivo Excel
        
    Returns:
        "exported" o "original"
    """
    try:
        df = pd.read_excel(file_path, engine="openpyxl", nrows=1)
        
        # Si tiene las columnas de un archivo exportado (snake_case)
        if "start_time" in df.columns and "end_time" in df.columns:
            return "exported"
        else:
            return "original"
    except Exception:
        return "original"  # Por defecto asumir original
