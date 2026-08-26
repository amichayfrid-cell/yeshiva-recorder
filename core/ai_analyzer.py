import json
import re
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import requests

import config
from core.hebrew_date import get_hebrew_date_str

KNOWN_TITLES = ("הרב", "ראש הישיבה", 'מו"ר', "מרן", "הגאון", "האדמו\"ר")
NO_TOPIC_VALUES = ("לא צוין", "אין", "ללא", "ללא נושא", "null", "none", "לא ידוע", "לא נאמר", "")

def clean_name_for_filename(text: str) -> str:
    """Cleans a string to make it safe for filesystem names."""
    if not text:
        return ""
    # Replace spaces with underscores and remove problematic filesystem characters
    cleaned = re.sub(r'[\\/*?:"<>|]', "", text.strip())
    cleaned = re.sub(r'\s+', "_", cleaned)
    return cleaned

def normalize_rabbi_name(name: str) -> str:
    """Ensures the Rabbi's name starts with a proper honorific title and matches known rabbis."""
    if not name:
        return ""
    trimmed = name.strip()
    has_title = False
    for title in KNOWN_TITLES:
        if trimmed.startswith(title):
            has_title = True
            break
    if not has_title:
        trimmed = f"הרב {trimmed}"

    # Match against known rabbis in config
    for known in config.KNOWN_RABBIS:
        clean_known = known.replace("הרב", "").strip().replace("ע", "א")
        clean_trimmed = trimmed.replace("הרב", "").strip().replace("ע", "א")
        if clean_known == clean_trimmed:
            return known

    return trimmed

def normalize_topic(topic: Any) -> Any:
    """Normalizes topic value, converting placeholder strings to None."""
    if not topic or not isinstance(topic, str):
        return None
    trimmed = topic.strip().lower()
    if trimmed in NO_TOPIC_VALUES:
        return None
    return topic.strip()

def extract_metadata_from_text(transcript: str) -> Dict[str, Any]:
    """
    Sends the transcribed text to Gemma 4 via Ollama for structured entity extraction.
    Returns a dictionary with 'rabbi', 'topic', and 'status'.
    """
    if not transcript or len(transcript.strip()) < 3:
        print("[AI] Transcript is empty or too short. Marking as unidentified.")
        return {
            "rabbi": None,
            "topic": None,
            "status": "unidentified"
        }

    # Focus on the first 40 words where the intro announcement always resides
    words = transcript.split()
    focused_transcript = " ".join(words[:40]) if len(words) > 40 else transcript

    print(f"[AI] Extracting entities from transcript (first {len(focused_transcript.split())} words): \"{focused_transcript}\"")

    known_rabbis_str = ", ".join(config.KNOWN_RABBIS)
    prompt = (
        "אתה עוזר חכם למערכת מיון שיעורי תורה בישיבה. תפקידך לחלץ מתוך תמלול השיעור את שם הרב ואת נושא השיעור.\n"
        f"רשימת רבני הישיבה המוכרים: {known_rabbis_str}.\n\n"
        "שים לב להנחיות הבאות:\n"
        "1. זיהוי שם הרב: אם השם בתמלול נשמע דומה לאחד מרבני הישיבה (למשל 'דור שינו' -> 'הרב דרור שילה', 'הרב שמיר הוא'/'הרשמיהו' -> 'הרב שמריהו', 'עבורי' -> 'הרב אורי', 'אבי תלמן' -> 'הרב אבי טילמן'), תקן ובחר את השם המדויק מרשימת הרבנים. אם מדובר ברב אחר, חלץ את שמו המלא.\n"
        "2. נושא השיעור: חלץ את הנושא המדויק. שים לב לתקן שמות אותיות ומספרים לפורמט תורני מקובל: 'צדיק ב' -> 'צב', 'יוד אלף' -> 'יא', 'הלכה א' וכו'.\n"
        "3. שיחות רקע: התעלם לחלוטין מדיבורים של תלמידים, רעשים ומשפטים לא קשורים (כגון 'תביא כיסאות', 'אפשר לשבת פה').\n"
        "4. אם לא זוהה שם רב בטקסט, החזר null עבור rabbi.\n\n"
        "דוגמאות:\n"
        "---\n"
        "קלט: \"הרב ערן, המשך סימן צדיק ב', סעיף ב', סוגיית טיפת חלב שנפלה לגדרה, ו' אלול...\"\n"
        "פלט: {\"rabbi\": \"הרב ערן\", \"topic\": \"איסור והיתר סימן צב סעיף ב טיפת חלב שנפלה לקדרה\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"הרב דור שינו, אורות התשובה, פרק יא פסקה עד שנייה. דיברנו אתמול...\"\n"
        "פלט: {\"rabbi\": \"הרב דרור שילה\", \"topic\": \"אורות התשובה פרק יא\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"עבורי, יום בבא מציע, יאוש שלא מדעת, י' אלול...\"\n"
        "פלט: {\"rabbi\": \"הרב אורי\", \"topic\": \"עיון בבא מציעא יאוש שלא מדעת\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"חטא חשוון הרב אבי תלמן, תפארת ישראל, שיעור מספר 5.\"\n"
        "פלט: {\"rabbi\": \"הרב אבי טילמן\", \"topic\": \"חבורה תפארת ישראל שיעור 5\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"הרב שמיר הוא שיעור עיון, סוגיית דרך חינוך, יום חמישי, ז' אלול...\"\n"
        "פלט: {\"rabbi\": \"הרב שמריהו\", \"topic\": \"עיון דרך הינוח\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"יום שני, ד' אלול, הרב עמיר, תפילה. טוב, אפשר לשבת בשולחן הזה גם...\"\n"
        "פלט: {\"rabbi\": \"הרב אמיר\", \"topic\": \"תפילה\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"שיעור ראיון, שיעור סיכום סוגיית החינוך, יום שני...\"\n"
        "פלט: {\"rabbi\": null, \"topic\": null, \"status\": \"unidentified\"}\n"
        "---\n\n"
        f"התמלול לעיבוד:\n\"\"\"\n{focused_transcript}\n\"\"\"\n\n"
        "חובה להחזיר אך ורק אובייקט JSON תקין (ללא שום טקסט נוסף) במבנה הבא:\n"
        "{\n"
        "  \"rabbi\": \"שם הרב\" | null,\n"
        "  \"topic\": \"נושא השיעור\" | null,\n"
        "  \"status\": \"identified\" | \"unidentified\"\n"
        "}"
    )

    payload = {
        "model": config.MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "num_predict": 120,
            "temperature": 0.1
        }
    }

    try:
        response = requests.post(config.OLLAMA_URL, json=payload, timeout=config.AI_TIMEOUT_SEC)
        response.raise_for_status()
        result = response.json()

        response_text = result.get("response", "").strip()
        print(f"[AI] Raw JSON Response: {response_text}")

        # Extract JSON block in case it's wrapped in markdown
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)

        # Parse JSON
        parsed = json.loads(response_text)
        raw_rabbi = parsed.get("rabbi")
        raw_topic = parsed.get("topic")

        # Post-process and normalize
        rabbi = normalize_rabbi_name(raw_rabbi) if raw_rabbi else None
        topic = normalize_topic(raw_topic)
        
        # Fundamental Rule: If a valid Rabbi was extracted, the file MUST be classified as identified
        status = "identified" if rabbi else "unidentified"

        return {
            "rabbi": rabbi,
            "topic": topic,
            "status": status
        }

    except Exception as e:
        print(f"[AI] Error during LLM entity extraction: {e}")
        return {
            "rabbi": None,
            "topic": None,
            "status": "unidentified"
        }

def generate_target_filename(
    metadata: Dict[str, Any],
    original_extension: str = ".mp3",
    file_dt: Optional[datetime] = None
) -> Tuple[str, bool]:
    """
    Generates a standardized filename based on AI metadata and Hebrew date of original file.
    Returns a tuple of (filename, is_identified_bool).
    """
    hebrew_date_str = get_hebrew_date_str(file_dt)
    status = metadata.get("status", "unidentified")
    rabbi = metadata.get("rabbi")
    topic = metadata.get("topic")

    if status == "identified" and rabbi:
        clean_rabbi = clean_name_for_filename(rabbi)
        if topic:
            clean_topic = clean_name_for_filename(topic)
            filename = f"{clean_rabbi}_{clean_topic}_{hebrew_date_str}{original_extension}"
        else:
            filename = f"{clean_rabbi}_{hebrew_date_str}{original_extension}"
        return filename, True
    else:
        filename = f"לסיווג_ידני_{hebrew_date_str}{original_extension}"
        return filename, False
