"""
Chronos v2 - Schedule Model
Represents a single schedule entry.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class Schedule:
    """Represents a single schedule entry."""
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
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Schedule':
        """Create from dictionary."""
        return cls(**data)

    def to_list(self) -> List:
        """Convert to list for export/clipboard (internal snake_case format)."""
        return [
            self.date, self.shift, self.area, self.start_time,
            self.end_time, self.code, self.instructor, self.program,
            self.minutes, str(self.units)
        ]
    
    def to_list_display(self) -> List:
        """Convert to list for table display (24h format)."""
        return [
            self.date, self.shift, self.area, 
            self._convert_to_24h(self.start_time),
            self._convert_to_24h(self.end_time), 
            self.code, self.instructor, self.program,
            self.minutes, str(self.units)
        ]
    
    def _convert_to_24h(self, time_12h: str) -> str:
        """Convert time from 12h to 24h format."""
        try:
            if ',' in time_12h:
                times = time_12h.split(',')
                converted = [self._convert_single_time_to_24h(t.strip()) for t in times]
                return ', '.join(converted)
            else:
                return self._convert_single_time_to_24h(time_12h)
        except:
            return time_12h

    def _convert_single_time_to_24h(self, time_str: str) -> str:
        """Convert a single time string from 12h to 24h format."""
        try:
            time_str = time_str.strip().upper()
            is_pm = 'PM' in time_str
            is_am = 'AM' in time_str
            time_clean = time_str.replace('AM', '').replace('PM', '').strip()
            
            if ':' in time_clean:
                hours, minutes = time_clean.split(':')
                hours = int(hours)
                minutes = int(minutes)
            else:
                hours = int(time_clean)
                minutes = 0
            
            if is_pm and hours != 12:
                hours += 12
            elif is_am and hours == 12:
                hours = 0
            
            return f"{hours:02d}:{minutes:02d}"
        except:
            return time_str

    def __hash__(self):
        """Hash for efficient O(1) comparisons."""
        return hash((self.date, self.shift, self.area, self.start_time, 
                     self.end_time, self.code, self.instructor, self.program))
    
    def __eq__(self, other):
        """Optimized equality comparison."""
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
