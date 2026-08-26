import json
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import config

_lock = threading.Lock()

def _load_notes() -> List[Dict[str, Any]]:
    """Loads notes from notes.json safely."""
    if not config.NOTES_FILE.exists():
        return []
    try:
        with open(config.NOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []

def _save_notes(notes: List[Dict[str, Any]]) -> None:
    """Saves notes to notes.json atomically."""
    temp_file = config.NOTES_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
        temp_file.replace(config.NOTES_FILE)
    except OSError as e:
        print(f"[NotesManager] Error saving notes: {e}")
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)

def add_note(filename: str, content: str, filepath: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new note for a specific audio recording.
    """
    with _lock:
        notes = _load_notes()
        note_id = f"note_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}"
        clean_filename = Path(filename).name if filename else "unknown"
        
        new_note = {
            "id": note_id,
            "filename": clean_filename,
            "filepath": str(filepath) if filepath else "",
            "content": content.strip(),
            "created_at": datetime.now().isoformat(),
            "status": "open",
            "resolved_at": None,
            "resolved_by": None,
            "resolution_note": None
        }
        
        notes.insert(0, new_note)
        _save_notes(notes)
        return new_note

def get_notes(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves all notes, optionally filtered by status ('open' or 'resolved').
    """
    with _lock:
        notes = _load_notes()
        if status:
            return [n for n in notes if n.get("status") == status]
        return notes

def get_notes_for_file(filename: str) -> List[Dict[str, Any]]:
    """
    Retrieves all notes associated with a given filename.
    """
    clean_name = Path(filename).name
    with _lock:
        notes = _load_notes()
        return [n for n in notes if n.get("filename") == clean_name]

def resolve_note(note_id: str, resolved_by: str = "admin", resolution_note: str = "") -> bool:
    """
    Marks a note as resolved.
    """
    with _lock:
        notes = _load_notes()
        updated = False
        for n in notes:
            if n.get("id") == note_id:
                n["status"] = "resolved"
                n["resolved_at"] = datetime.now().isoformat()
                n["resolved_by"] = resolved_by
                n["resolution_note"] = resolution_note
                updated = True
                break
        if updated:
            _save_notes(notes)
        return updated

def delete_note(note_id: str) -> bool:
    """
    Permanently removes a note by ID.
    """
    with _lock:
        notes = _load_notes()
        initial_len = len(notes)
        notes = [n for n in notes if n.get("id") != note_id]
        if len(notes) != initial_len:
            _save_notes(notes)
            return True
        return False
