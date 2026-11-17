import os
import re
import math
import struct
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Optional, Union

HEBREW_MONTHS = [
    "תשרי", "חשון", "חשוון", "כסלו", "טבת", "שבט", 
    "אדר", "אדר א", "אדר ב", "ניסן", "אייר", "סיון", 
    "תמוז", "אב", "אלול"
]

def get_israel_sunset_time(d: date) -> time:
    """
    Calculates approximate solar sunset time for Israel (Mitzpe Ramon / Jerusalem).
    Uses solar declination and equation of time to calculate sunset accurate within ~2 minutes.
    """
    try:
        day_of_year = d.timetuple().tm_yday
        declination = 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))
        lat_rad = math.radians(31.2)  # Central Israel latitude
        dec_rad = math.radians(declination)
        cos_ha = -math.tan(lat_rad) * math.tan(dec_rad)
        cos_ha = max(-1.0, min(1.0, cos_ha))
        ha_deg = math.degrees(math.acos(cos_ha))
        sunset_hours_after_noon = ha_deg / 15.0
        
        # Israel Daylight Saving Time approx: late March to late October
        is_dst = (date(d.year, 3, 27) <= d <= date(d.year, 10, 27))
        tz_offset = 3.0 if is_dst else 2.0
        
        b = math.radians((360 / 364) * (day_of_year - 81))
        eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
        solar_noon_minutes = 12 * 60 - 4 * (34.9 - 15 * tz_offset) - eot
        sunset_minutes = solar_noon_minutes + (sunset_hours_after_noon * 60)
        
        sh = int(sunset_minutes // 60)
        sm = int(sunset_minutes % 60)
        return time(sh, sm)
    except Exception:
        # Fallback to standard seasonal sunset
        m = d.month
        if m in (11, 12, 1):
            return time(16, 45)
        elif m in (5, 6, 7, 8):
            return time(19, 40)
        else:
            return time(18, 0)

def get_hebrew_date_str(dt: Optional[datetime] = None, check_sunset: bool = False) -> str:
    """
    Converts a datetime object to a filesystem-friendly Hebrew date string (e.g. 'ה כסלו תשפז').
    In the yeshiva, recordings and lectures throughout the evening/night seder belong to that day's date,
    transitioning at midnight (00:00). check_sunset defaults to False.
    """
    if dt is None:
        dt = datetime.now()

    target_date = dt.date()
    if check_sunset:
        try:
            sunset_t = get_israel_sunset_time(target_date)
            if dt.time() >= sunset_t:
                target_date = target_date + timedelta(days=1)
        except Exception:
            pass

    try:
        from pyluach import dates
        heb_date = dates.HebrewDate.from_pydate(target_date)
        raw_str = heb_date.hebrew_date_string() # e.g. "כ״ד חשון תשפ״ז"
        
        # Remove gershayim and apostrophes to make it safe for filenames
        clean_str = raw_str.replace('״', '').replace('׳', '').replace('"', '').replace("'", "")
        # Keep clean single spaces between words
        clean_str = re.sub(r'\s+', ' ', clean_str.strip())
        return clean_str
    except Exception as e:
        print(f"Warning: Hebrew date conversion failed ({e}), using Gregorian fallback.")
        return target_date.strftime("%Y-%m-%d")

def extract_hebrew_date_from_filename(filename: str) -> Optional[str]:
    """
    Checks if the filename already contains an explicit Hebrew date in parentheses.
    Example: '(כד חשון תשפז) 11-32.mp3' -> 'כד חשון תשפז'
    """
    m = re.search(r"\(([^)]+)\)", os.path.basename(filename))
    if m:
        content = m.group(1).replace("_", " ").strip()
        if any(h_month in content for h_month in HEBREW_MONTHS):
            return clean_hebrew_date_str(content)
    return None

def clean_hebrew_date_str(date_str: str) -> str:
    """Cleans apostrophes and extra spaces from Hebrew date string."""
    clean = date_str.replace('״', '').replace('׳', '').replace('"', '').replace("'", "")
    return re.sub(r'\s+', ' ', clean.strip())

def parse_iso_or_flexible_datetime(s: str) -> Optional[datetime]:
    """Tries to parse various ISO and common datetime strings."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    formats = [
        ("%Y-%m-%d %H:%M:%S", None),
        ("%Y-%m-%d %H:%M", None),
        ("%Y-%m-%dT%H:%M:%S", None),
        ("%Y-%m-%dT%H:%M:%SZ", None),
        ("%Y-%m-%dT%H:%M", None),
        ("%Y-%m-%d", None),
        ("%Y%m%d_%H%M%S", 15),
        ("%Y%m%d_%H%M", 13),
        ("%Y%m%d%H%M%S", 14),
        ("%Y%m%d", 8),
    ]
    for fmt, exact_len in formats:
        candidate = s[:len(fmt) + 2].rstrip("Z")
        if exact_len is not None and len(s.rstrip("Z")) != exact_len:
            continue
        try:
            return datetime.strptime(candidate, fmt)
        except (ValueError, TypeError):
            continue
    return None

def parse_filename_datetime(filename: str) -> Optional[datetime]:
    """
    Extracts full recording datetime from filename pattern.
    Handles Olympus, Sony, Philips, and common yeshiva recorder naming conventions.
    """
    stem = re.sub(r'\.(mp3|wav|m4a|wma|ogg|aac|flac)$', '', os.path.basename(filename), flags=re.I)
    
    # Pattern 1: YYYYMMDD[_-]HHMM[SS] (e.g. 20261114_110230, 20261114-1102)
    m = re.search(r'(20\d{2})[_-]?(0[1-9]|1[0-2])[_-]?(0[1-9]|[12]\d|3[01])[_\s\-T]+([01]\d|2[0-3])[.:\-_]?([0-5]\d)(?:[.:\-_]?([0-5]\d))?', stem)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6) or 0))
        except ValueError:
            pass

    # Pattern 2: YYMMDD[_-]HHMM[SS] (e.g. 261103_1159 -> 2026-11-03 11:59)
    m = re.search(r'\b(2[0-9]|3[0-5])(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[_\s\-]+([01]\d|2[0-3])([0-5]\d)(?:([0-5]\d))?\b', stem)
    if m:
        try:
            return datetime(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6) or 0))
        except ValueError:
            pass

    # Pattern 3: DDMMYY[_-]HHMM[SS] (e.g. 141126_1102 -> 2026-11-14 11:02)
    m = re.search(r'\b(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])(2[0-9]|3[0-5])[_\s\-]+([01]\d|2[0-3])([0-5]\d)(?:([0-5]\d))?\b', stem)
    if m:
        try:
            return datetime(2000 + int(m.group(3)), int(m.group(2)), int(m.group(1)), int(m.group(4)), int(m.group(5)), int(m.group(6) or 0))
        except ValueError:
            pass

    # Pattern 4: DD[._-]MM[._-]YYYY [ _-] HH[.:_-]MM
    m = re.search(r'(0[1-9]|[12]\d|3[01])[.\-_](0[1-9]|1[0-2])[.\-_](20\d{2})[_\s\-]+([01]\d|2[0-3])[.:\-_]([0-5]\d)', stem)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), int(m.group(4)), int(m.group(5)))
        except ValueError:
            pass

    # Pattern 5: YYYY-MM-DD [ _-] HH[.:_-]MM
    m = re.search(r'(20\d{2})[.\-_](0[1-9]|1[0-2])[.\-_](0[1-9]|[12]\d|3[01])[_\s\-]+([01]\d|2[0-3])[.:\-_]([0-5]\d)', stem)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))
        except ValueError:
            pass

    return None

def parse_filename_time_only(filename: str) -> Optional[time]:
    """
    Extracts time HH:MM from filename when date is not present or in Hebrew format.
    Handles '(כד חשון תשפז) 11-32.mp3', 'mp3.3_11.02', '11.02.mp3', etc.
    """
    stem = re.sub(r'\.(mp3|wav|m4a|wma|ogg|aac|flac)$', '', os.path.basename(filename), flags=re.I)
    
    # Pattern A: Suffix or standalone time e.g. '11.02' or '11-32' or '13.14'
    m = re.search(r'(?:[\s_\-(]|^)([01]\d|2[0-3])[.\-_:]([0-5]\d)(?:[.\-_:]([0-5]\d))?(?:[\s_\-)]|$)', stem)
    if m:
        try:
            return time(int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
        except ValueError:
            pass
    return None

def extract_wav_riff_datetime(file_path: Path) -> Optional[datetime]:
    """Reads broadcast WAV (bext) chunk or INFO chunk creation datetime."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)
            if len(header) < 12 or header[:4] != b'RIFF' or header[8:12] != b'WAVE':
                return None
            while True:
                chunk_hdr = f.read(8)
                if len(chunk_hdr) < 8:
                    break
                chunk_id, chunk_size = struct.unpack('<4sI', chunk_hdr)
                if chunk_id == b'bext':
                    bext_data = f.read(min(chunk_size, 1024))
                    if len(bext_data) >= 338:
                        d_str = bext_data[320:330].decode('ascii', errors='ignore').strip('\x00 ')
                        t_str = bext_data[330:338].decode('ascii', errors='ignore').strip('\x00 ')
                        if re.match(r'^\d{4}-\d{2}-\d{2}$', d_str) and re.match(r'^\d{2}:\d{2}:\d{2}$', t_str):
                            return datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M:%S")
                    break
                else:
                    f.seek(chunk_size, 1)
    except Exception:
        pass
    return None

def extract_audio_metadata_datetime(filepath: Union[str, Path]) -> Optional[datetime]:
    """
    Extracts original recording date and time embedded in audio file metadata:
    - MP3: ID3v2 TDRC, TDAT+TIME+TYER, TXXX:recorded_at
    - WAV: RIFF bext (Broadcast Wave), ICRD
    - MP4/M4A: ©day
    """
    p = Path(filepath) if isinstance(filepath, (str, Path)) else None
    if not p or not p.is_file():
        return None

    ext = p.suffix.lower()
    
    # 1. MP3 ID3
    if ext == ".mp3":
        try:
            from mutagen.mp3 import MP3
            audio = MP3(str(p))
            if audio.tags:
                tdrc = audio.tags.get("TDRC")
                if tdrc and tdrc.text:
                    parsed = parse_iso_or_flexible_datetime(str(tdrc.text[0]))
                    if parsed:
                        return parsed

                tdat = audio.tags.get("TDAT")
                time_tag = audio.tags.get("TIME")
                tyer = audio.tags.get("TYER")
                if tyer and tdat and time_tag:
                    try:
                        y = int(str(tyer.text[0]))
                        d = int(str(tdat.text[0])[:2])
                        mo = int(str(tdat.text[0])[2:4])
                        h = int(str(time_tag.text[0])[:2])
                        mi = int(str(time_tag.text[0])[2:4])
                        return datetime(y, mo, d, h, mi)
                    except Exception:
                        pass

                for txxx in audio.tags.getall("TXXX"):
                    if txxx.desc.lower() in ("recorded_at", "recording_time", "creation_time"):
                        parsed = parse_iso_or_flexible_datetime(str(txxx.text[0]))
                        if parsed:
                            return parsed
        except Exception:
            pass

    # 2. WAV RIFF
    elif ext == ".wav":
        dt = extract_wav_riff_datetime(p)
        if dt:
            return dt

    # 3. MP4 / M4A
    elif ext in (".m4a", ".mp4", ".aac"):
        try:
            from mutagen.mp4 import MP4
            audio = MP4(str(p))
            day_tag = audio.tags.get("\xa9day")
            if day_tag and day_tag[0]:
                parsed = parse_iso_or_flexible_datetime(str(day_tag[0]))
                if parsed:
                    return parsed
        except Exception:
            pass

    return None

def extract_sony_icd_datetime(file_path: Union[str, Path]) -> Optional[datetime]:
    """
    Extracts Sony IC Recorder (ICD-UX570, ICD-PX470, etc.) hardware recording timestamp
    directly from the ID3/GEOB header chunk. Takes <0.001s by reading only the first 4KB.
    """
    try:
        p = Path(file_path) if isinstance(file_path, (str, Path)) else None
        if not p or not p.is_file():
            return None
        with open(p, "rb") as f:
            chunk = f.read(4096)
        if chunk.startswith(b"ID3"):
            m = re.search(rb'(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])[T ]([01]\d|2[0-3]):([0-5]\d):([0-5]\d)', chunk)
            if m:
                y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
                if 2000 <= y <= 2040:
                    return datetime(y, mo, d, h, mi, s)
    except Exception:
        pass
    return None

def extract_recording_datetime(
    filepath: Union[str, Path], 
    stat_obj: Optional[os.stat_result] = None
) -> datetime:
    """
    Master function: Extracts the true recording datetime of an audio file.
    Hierarchy:
    1. Full date & time embedded in filename.
    2. Sony IC Recorder internal hardware metadata (GEOB/ID3).
    3. Time-only embedded in filename combined with file stat date.
    4. Original recorder file system modification timestamp (st_mtime / st_ctime).
    5. Fallback to audio metadata or current datetime.
    """
    p = Path(filepath) if isinstance(filepath, (str, Path)) else None
    fn = p.name if p else str(filepath)

    # 1. Fast in-memory check: Full datetime from filename (e.g. 261115_1949, 20261115_1949)
    fn_dt = parse_filename_datetime(fn)
    if fn_dt and 2000 <= fn_dt.year <= 2040:
        return fn_dt

    # 2. Check Sony IC Recorder embedded hardware timestamp (reading only 4KB)
    if p and p.is_file() and p.suffix.lower() == ".mp3":
        sony_dt = extract_sony_icd_datetime(p)
        if sony_dt:
            return sony_dt

    # 2. File system modification timestamp (already in memory from os.scandir)
    base_dt = None
    if stat_obj:
        base_dt = datetime.fromtimestamp(stat_obj.st_mtime)
    elif p and p.exists():
        try:
            st = p.stat()
            base_dt = datetime.fromtimestamp(st.st_mtime)
        except Exception:
            pass

    # 3. Time-only embedded in filename combined with file stat date (e.g. '19.49.mp3', '(ה כסלו) 19.49.mp3')
    fn_time = parse_filename_time_only(fn)
    if fn_time:
        target_d = base_dt.date() if base_dt else datetime.now().date()
        return datetime.combine(target_d, fn_time)

    # 4. Use file system timestamp directly if valid
    if base_dt and 2000 <= base_dt.year <= 2040:
        return base_dt

    # 5. Fallback: Internal audio metadata (only when filename & stat have no valid time)
    if p and p.is_file():
        try:
            meta_dt = extract_audio_metadata_datetime(p)
            if meta_dt and 2000 <= meta_dt.year <= 2040:
                return meta_dt
        except Exception:
            pass

    return base_dt if base_dt else datetime.now()

    return datetime.now()
