"""
Chronos - Workers Package
Background workers para operaciones asíncronas.
"""

import os
import logging
from typing import List
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QThread, pyqtSignal

from app.models.schedule import Schedule
from app.services.excel_service import (
    parse_excel_file, 
    parse_exported_excel_file, 
    detect_file_type
)
from app.services.auth_service import auth_service
from app.services.zoom_service import zoom_service
import utils


logger = logging.getLogger(__name__)


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
                file_type = detect_file_type(file_path)
                
                if file_type == "exported":
                    schedules = parse_exported_excel_file(file_path)
                else:
                    schedules = parse_excel_file(file_path)
                
                all_schedules.extend(schedules)
            except Exception as e:
                logger.exception(f"Error processing file: {file_path}")
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
        logger.debug("AssignmentWorker started")
        results = []
        errors = []
        
        try:
            self.progress.emit("Connecting to Supabase...")
            supabase = auth_service.get_client()
            
            # 1. Fetch Zoom Users
            self.progress.emit("Fetching Zoom Users...")
            users_response = supabase.table("zoom_users").select(
                "id, first_name, last_name, display_name, email"
            ).execute()
            
            users_by_id = {}
            users_by_name = {}
            
            for u in users_response.data:
                uid = u["id"]
                dname = u.get("display_name")
                fname = u.get("first_name", "").strip()
                lname = u.get("last_name", "").strip()
                full_name = f"{fname} {lname}".strip()
                
                if not dname:
                    dname = full_name
                
                u["display_name"] = dname
                u["full_name"] = full_name
                
                users_by_id[uid] = u
                
                c_dname = utils.canonical(dname)
                if c_dname:
                    users_by_name[c_dname] = u
                    
                c_fullname = utils.canonical(full_name)
                if c_fullname and c_fullname != c_dname:
                    users_by_name[c_fullname] = u
            
            # 2. Fetch Zoom Meetings
            self.progress.emit("Fetching Zoom Meetings...")
            zoom_meetings = []
            page_size = 1000
            offset = 0
            
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
            
            # Build meetings map
            meetings_map = {"by_topic": {}, "list": []}
        
            for m in zoom_meetings:
                try:
                    host_data = users_by_id.get(m.get("host_id"))
                    m["host_name"] = host_data.get("display_name", "Unknown") if host_data else "Unknown"
                    
                    topic = m.get("topic", "")
                    c_topic = utils.canonical(topic)
                    
                    meetings_map["list"].append(m)
                    if c_topic:
                        meetings_map["by_topic"][c_topic] = m
                except Exception:
                    continue

            # 3. Pre-compute choices for fuzzy matching
            instructor_choices = {}
            for u in users_by_id.values():
                instructor_choices[utils.normalizar_cadena(u["display_name"])] = u
                if u.get("full_name"):
                    instructor_choices[utils.normalizar_cadena(u["full_name"])] = u
            
            meeting_choices = {utils.normalizar_cadena(m["topic"]): m for m in meetings_map["list"]}

            # 4. Process Schedules
            for i, schedule in enumerate(self.schedules):
                if i % 10 == 0:
                    self.progress.emit(f"Analyzing {i+1}/{len(self.schedules)}...")
                
                status = "not_found"
                match_reason = "No match found"
                meeting_id = ""
                
                raw_instr = schedule.instructor
                raw_prog = schedule.program
                
                c_instr = utils.canonical(raw_instr)
                c_prog = utils.canonical(raw_prog)
                
                found_meeting = None
                found_instructor = None
                
                # Search instructor
                found_instructor = users_by_name.get(c_instr)
                if not found_instructor:
                    found_instructor = utils.fuzzy_find(raw_instr, instructor_choices)

                # Search meeting
                found_meeting = meetings_map["by_topic"].get(c_prog)
                if not found_meeting:
                    found_meeting = utils.fuzzy_find(raw_prog, meeting_choices, threshold=75)
                
                # Determine status
                if found_meeting and found_instructor:
                    if found_meeting.get("host_id") == found_instructor.get("id"):
                        status = "assigned"
                        match_reason = "-"
                        meeting_id = found_meeting.get("meeting_id")
                    else:
                        status = "to_update"
                        match_reason = "-"
                        meeting_id = found_meeting.get("meeting_id")
                        
                elif found_meeting and not found_instructor:
                    status = "to_update"
                    match_reason = "Instructor not found"
                    meeting_id = found_meeting.get("meeting_id")
                    
                elif not found_meeting and found_instructor:
                    status = "not_found"
                    meeting_id = "-"
                    match_reason = "Meeting not found"
                
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
            logger.exception("Error in AssignmentWorker")
            errors.append(str(e))
            
        self.finished.emit(results, errors)


class UpdateWorker(QThread):
    """Worker thread para ejecutar la reasignación en Zoom y BD."""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(list, list)  # success_list, error_list

    def __init__(self, assignments: List[dict], update_recurrence: bool = False):
        super().__init__()
        self.assignments = assignments
        self.update_recurrence = update_recurrence

    def run(self):
        logger.debug("UpdateWorker started")
        successes = []
        errors = []
        
        try:
            self.progress.emit("Connecting to Supabase...")
            supabase = auth_service.get_client()
            
            # 1. Get Zoom Token (and refresh if needed)
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
            
            # Recurrence settings (if updating recurrence)
            recurrence_settings = None
            start_time_str = None
            if self.update_recurrence:
                from datetime import datetime, timedelta
                # Base settings - will override start_time per item
                end_date = datetime.now() + timedelta(days=120)
                end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                recurrence_settings = {
                    "type": 2,  # Weekly
                    "repeat_interval": 1,
                    "weekly_days": "2,3,4,5,6",  # Mon-Fri
                    "end_date_time": end_date_str
                }
            
            # 2. Process assignments
            total = len(self.assignments)
            update_recurrence = self.update_recurrence
            
            def process_assignment(item, token):
                """Process single assignment."""
                meeting_id = item["meeting_id"]
                new_host_email = item["new_host_email"]
                new_host_id = item["new_host_id"]
                topic = item.get("topic", "")
                row_start_time = item.get("start_time", "09:00")  # Default 9:00 AM
                
                try:
                    # Update host
                    zoom_service.update_meeting_host(token, meeting_id, new_host_email)
                    
                    # Update recurrence if enabled
                    if update_recurrence and recurrence_settings:
                        from datetime import datetime, timedelta
                        # Parse row start_time (HH:MM format)
                        try:
                            hour, minute = map(int, row_start_time.split(":"))
                        except:
                            hour, minute = 9, 0
                        
                        start_date = datetime.now() + timedelta(days=1)
                        start_date = start_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        item_start_time_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
                        
                        zoom_service.update_meeting(
                            access_token=token,
                            meeting_id=meeting_id,
                            topic=topic,
                            start_time=item_start_time_str,
                            duration=60,
                            recurrence=recurrence_settings
                        )
                    
                    # Update DB
                    supabase.table("zoom_meetings").update({
                        "host_id": new_host_id
                    }).eq("meeting_id", meeting_id).execute()
                    
                    return {"success": True, "topic": topic, "meeting_id": meeting_id}
                except Exception as e:
                    return {"success": False, "topic": topic, "error": str(e)}
            
            # Process with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for item in self.assignments:
                    future = executor.submit(process_assignment, item, current_token)
                    futures.append(future)
                
                for i, future in enumerate(futures):
                    self.progress.emit(f"Updating {i+1}/{total}...")
                    result = future.result()
                    if result["success"]:
                        successes.append(result)
                    else:
                        errors.append(result)
                        
        except Exception as e:
            logger.exception("Error in UpdateWorker")
            errors.append({"success": False, "error": str(e)})
            
        self.finished.emit(successes, errors)


class MeetingSearchWorker(QThread):
    """Worker thread para buscar reuniones en Supabase."""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(list, list)  # meetings, errors

    def run(self):
        logger.debug("MeetingSearchWorker started")
        meetings = []
        errors = []
        
        try:
            self.progress.emit("Connecting to database...")
            supabase = auth_service.get_client()
            
            self.progress.emit("Fetching meetings...")
            
            # Paginated fetch
            page_size = 1000
            offset = 0
            
            while True:
                response = supabase.table("zoom_meetings")\
                    .select("meeting_id, topic, host_id, created_at")\
                    .range(offset, offset + page_size - 1)\
                    .execute()
                    
                if not response.data:
                    break
                    
                meetings.extend(response.data)
                
                if len(response.data) < page_size:
                    break
                    
                offset += page_size
                self.progress.emit(f"Loading meetings... ({len(meetings)})")
            
            # Fetch users for host names
            self.progress.emit("Fetching user data...")
            users_resp = supabase.table("zoom_users").select("id, display_name, first_name, last_name").execute()
            
            users_by_id = {}
            for u in users_resp.data:
                uid = u["id"]
                dname = u.get("display_name") or f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                users_by_id[uid] = dname
            
            # Add host names to meetings
            for m in meetings:
                host_id = m.get("host_id")
                m["host_name"] = users_by_id.get(host_id, "Unknown")
                
        except Exception as e:
            logger.exception("Error in MeetingSearchWorker")
            errors.append(str(e))
            
        self.finished.emit(meetings, errors)


from app.workers.link_creation import LinkCreationWorker

__all__ = [
    "ExcelWorker",
    "AssignmentWorker", 
    "UpdateWorker",
    "MeetingSearchWorker",
    "LinkCreationWorker"
]
