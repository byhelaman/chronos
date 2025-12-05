"""
Chronos - Link Creation Worker
Worker for creating Zoom links for a list of programs.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from PyQt6.QtCore import QThread, pyqtSignal

from app.services.auth_service import auth_service
from app.services.zoom_service import zoom_service
import utils

logger = logging.getLogger(__name__)


class LinkCreationWorker(QThread):
    """Worker thread para crear/actualizar links de Zoom."""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(list, list, str)  # results, errors, mode

    def __init__(self, items: List[Dict], mode: str = "verify"):
        """
        Args:
            items: List of dicts with {program, status, meeting_id} for create mode,
                   or just list of program strings for verify mode
            mode: "verify" or "create"
        """
        super().__init__()
        self.items = items
        self.mode = mode

    def run(self):
        logger.debug(f"LinkCreationWorker started in {self.mode} mode")
        results = []
        errors = []
        
        try:
            self.progress.emit("Connecting to database...")
            supabase = auth_service.get_client()
            
            # === VERIFY MODE ===
            if self.mode == "verify":
                programs = [item.strip() if isinstance(item, str) else item.get("program", "").strip() 
                           for item in self.items]
                programs = [p for p in programs if p]
                
                # Fetch existing meetings
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
                
                # Process each program
                total = len(programs)
                for i, program in enumerate(programs):
                    self.progress.emit(f"Processing {i+1}/{total}: {program}")
                    
                    normalized_prog = utils.normalizar_cadena(program)
                    
                    # Check if exists
                    found_meeting = None
                    if normalized_prog in meeting_choices:
                        found_meeting = meeting_choices[normalized_prog]
                        match_type = "Exact match"
                    else:
                        found_meeting = utils.fuzzy_find(program, meeting_choices, threshold=85)
                        match_type = "Fuzzy match"
                    
                    if found_meeting:
                        results.append({
                            "program": program,
                            "status": "existing",
                            "meeting_id": found_meeting["meeting_id"],
                            "join_url": found_meeting.get("join_url", ""),
                            "message": f"{match_type}: {found_meeting.get('topic')}"
                        })
                    else:
                        results.append({
                            "program": program,
                            "status": "ready",
                            "meeting_id": "-",
                            "join_url": "-",
                            "message": "Ready to create"
                        })
            
            # === CREATE MODE ===
            else:
                self.progress.emit("Fetching Zoom Token...")
                token_resp = supabase.table("zoom_tokens").select("access_token, expires_at").limit(1).execute()
                if not token_resp.data:
                    raise Exception("No Zoom token found in database. Please sync first.")
                
                token_data = token_resp.data[0]
                current_token = token_data["access_token"]
                
                # Check if token is expired and refresh
                from datetime import datetime
                expires_at = token_data.get("expires_at")
                if expires_at:
                    try:
                        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                        if datetime.now(expires_dt.tzinfo) >= expires_dt:
                            self.progress.emit("Refreshing Zoom Token...")
                            current_token = zoom_service.refresh_token(supabase)
                    except Exception as refresh_err:
                        logger.warning(f"Could not check/refresh token: {refresh_err}")
                
                # Recurrence settings
                start_date = datetime.now() + timedelta(days=1)
                start_date = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
                start_time_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
                end_date = start_date + timedelta(days=180)
                end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                recurrence = {
                    "type": 2,  # Weekly
                    "repeat_interval": 1,
                    "weekly_days": "2,3,4,5,6",  # Mon-Fri
                    "end_date_time": end_date_str
                }
                
                # Process items
                total = len(self.items)
                for i, item in enumerate(self.items):
                    program = item.get("program", "")
                    status = item.get("status", "")
                    meeting_id = item.get("meeting_id", "")
                    
                    self.progress.emit(f"Processing {i+1}/{total}: {program}")
                    
                    # Skip items that are not actionable
                    if status not in ["ready", "to_update"]:
                        results.append(item)  # Keep original
                        continue
                    
                    try:
                        if status == "ready":
                            # CREATE new meeting
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
                            
                        elif status == "to_update":
                            # UPDATE existing meeting
                            zoom_service.update_meeting(
                                access_token=current_token,
                                meeting_id=meeting_id,
                                topic=program,
                                start_time=start_time_str,
                                duration=60,
                                recurrence=recurrence
                            )
                            
                            # Update topic in DB
                            supabase.table("zoom_meetings").update({
                                "topic": program
                            }).eq("meeting_id", meeting_id).execute()
                            
                            results.append({
                                "program": program,
                                "status": "updated",
                                "meeting_id": meeting_id,
                                "join_url": item.get("join_url", ""),
                                "message": "Updated successfully"
                            })
                            
                    except Exception as e:
                        logger.error(f"Error processing {program}: {e}")
                        results.append({
                            "program": program,
                            "status": "error",
                            "meeting_id": meeting_id or "-",
                            "join_url": item.get("join_url", "-"),
                            "message": str(e)
                        })
                        errors.append(f"{program}: {str(e)}")
            
        except Exception as e:
            logger.exception("Error in LinkCreationWorker")
            errors.append(str(e))
            
        self.finished.emit(results, errors, self.mode)
