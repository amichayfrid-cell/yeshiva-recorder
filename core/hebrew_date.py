import re
from datetime import datetime
from typing import Optional

def get_hebrew_date_str(dt: Optional[datetime] = None) -> str:
    """
    Converts a datetime object to a filesystem-friendly Hebrew date string (e.g. 'יב_אלול_תשפו').
    If pyluach is not available, falls back to ISO format.
    """
    if dt is None:
        dt = datetime.now()

    try:
        from pyluach import dates
        heb_date = dates.HebrewDate.from_pydate(dt.date())
        raw_str = heb_date.hebrew_date_string() # e.g. "י״ב אלול תשפ״ו"
        
        # Remove gershayim and apostrophes to make it safe for filenames
        clean_str = raw_str.replace('״', '').replace('׳', '').replace('"', '').replace("'", "")
        # Replace spaces with underscores
        clean_str = re.sub(r'\s+', '_', clean_str.strip())
        return clean_str
    except Exception as e:
        print(f"Warning: Hebrew date conversion failed ({e}), using Gregorian fallback.")
        return dt.strftime("%Y-%m-%d")
