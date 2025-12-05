"""
Chronos - Link Creation Worker
Worker for creating Zoom links for a list of programs.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from app.services.auth_service import auth_service
from app.services.zoom_service import zoom_service
import utils

logger = logging.getLogger(__name__)


class LinkCreationWorker(QThread):
    """Worker thread para crear links de Zoom para una lista de programas."""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(list, list)  # results, errors

    def __init__(self, programs: List[str], mode: str = "verify"):
        super().__init__()
        self.programs = [p.strip() for p in programs if p.strip()]
        self.mode = mode

    def run(self):
        logger.debug(f"LinkCreationWorker started in {self.mode} mode")
        results = []
        errors = []
        
        try:
            self.progress.emit("Connecting to database...")
            supabase = auth_service.get_client()
            
            # 1. Get Zoom Token (Needed for both modes to be safe, or just create)
            if self.mode == "create":
                self.progress.emit("Fetching Zoom Token...")
                token_resp = supabase.table("zoom_tokens").select("access_token").limit(1).execute()
                if not token_resp.data:
                    raise Exception("No Zoom token found in database. Please sync first.")
                current_token = token_resp.data[0]["access_token"]
            
            # 2. Fetch existing meetings (Always needed to check duplicates/verify)
            self.progress.emit("Checking existing meetings...")
            existing_meetings = []
            page_size = 1000
            offset = 0
            
            while True:
                response = supabase.table("zoom_meetings")\
                    .select("meeting_id, topic, join_url")\
                    .range(offset, offset + page_size - 1)\
                    .execute()
                if not response.data:
                    break
                existing_meetings.extend(response.data)
                if len(response.data) < page_size:
                    break
                offset += page_size
                
            # Create a map for fuzzy lookup
            meeting_choices = {
                utils.normalizar_cadena(m["topic"]): m 
                for m in existing_meetings 
                if m.get("topic")
            }
            
            # 3. Process programs
            total = len(self.programs)
            
            # Recurrence settings (Only for create)
            if self.mode == "create":
                start_date = datetime.now() + timedelta(days=1)
                start_date = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
                start_time_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
                end_date = start_date + timedelta(days=180)
                end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                recurrence = {
                    "type": 2, "repeat_interval": 1,
                    "weekly_days": str(start_date.weekday() + 1),
                    "end_date_time": end_date_str
                }
            
            for i, program in enumerate(self.programs):
                self.progress.emit(f"Processing {i+1}/{total}: {program}")
                
                normalized_prog = utils.normalizar_cadena(program)
                
                # 1. Exact Match
                found_meeting = None
                if normalized_prog in meeting_choices:
                    found_meeting = meeting_choices[normalized_prog]
                    match_type = "Exact match"
                else:
                    # 2. Fuzzy Match
                    found_meeting = utils.fuzzy_find(program, meeting_choices, threshold=85)
                    match_type = "Fuzzy match"
                
                # Check if exists
                if found_meeting:
                    results.append({
                        "program": program,
                        "status": "existing",
                        "meeting_id": found_meeting["meeting_id"],
                        "join_url": found_meeting.get("join_url", ""),
                        "message": f"{match_type}: {found_meeting.get('topic')}"
                    })
                    continue
                
                # If verify mode, mark as ready
                if self.mode == "verify":
                    results.append({
                        "program": program,
                        "status": "ready",
                        "meeting_id": "-",
                        "join_url": "-",
                        "message": "Ready to create"
                    })
                    continue
                
                # CREATE MODE
                try:
                    meeting = zoom_service.create_meeting(
                        access_token=current_token,
                        user_id="me",
                        topic=program,
                        start_time=start_time_str,
                        duration=60,
                        recurrence=recurrence
                    )
                    
                    # Save to DB
                    meeting_data = {
                        "meeting_id": str(meeting["id"]),
                        "uuid": meeting.get("uuid"),
                        "host_id": meeting.get("host_id"),
                        "topic": meeting.get("topic"),
                        "type": meeting.get("type"),
                        "duration": meeting.get("duration"),
                        "timezone": meeting.get("timezone"),
                        "join_url": meeting.get("join_url"),
                        "created_at": meeting.get("created_at")
                    }
                    
                    supabase.table("zoom_meetings").upsert(meeting_data).execute()
                    
                    results.append({
                        "program": program,
                        "status": "created",
                        "meeting_id": str(meeting["id"]),
                        "join_url": meeting.get("join_url"),
                        "message": "Created successfully"
                    })
                    
                except Exception as e:
                    logger.error(f"Error creating meeting for {program}: {e}")
                    results.append({
                        "program": program,
                        "status": "error",
                        "meeting_id": "-",
                        "join_url": "-",
                        "message": str(e)
                    })
                    errors.append(f"{program}: {str(e)}")
            
        except Exception as e:
            logger.exception("Error in LinkCreationWorker")
            errors.append(str(e))
            
        self.finished.emit(results, errors)
