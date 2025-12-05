"""
Chronos - Schedule Model
Representa una entrada individual de horario.
"""

from dataclasses import dataclass, asdict
from typing import List


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

    def to_dict(self) -> dict:
        """Convierte el schedule a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Schedule":
        """Crea un Schedule desde un diccionario."""
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
        except (ValueError, AttributeError):
            return time_12h  # Retornar original si hay error de formato
    
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
        except (ValueError, AttributeError):
            return time_str  # Retornar original si hay error de parsing
    
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
