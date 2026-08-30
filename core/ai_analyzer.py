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
    """Cleans a string to make it safe for filesystem names while preserving standard spaces."""
    if not text:
        return ""
    # Remove illegal filesystem characters
    cleaned = re.sub(r'[\\/*?:"<>|]', "", text.strip())
    # Collapse multiple spaces/tabs into a single space
    cleaned = re.sub(r'[ \t]+', " ", cleaned)
    return cleaned.strip()

def fix_spoken_gematria_and_letters(text: str) -> str:
    """
    Converts spelled-out Hebrew letter names and phonetic Whisper artifacts
    to standard Hebrew letter abbreviations (e.g. 'צדיק ב' -> 'צב', 'צדיג' -> 'צג', 'יוד אלף' -> 'יא').
    """
    if not text:
        return ""

    t = text

    # Handle phonetic 'צדיג' / 'צדיק' combinations
    t = re.sub(r'\b(צדיק|צדיג|צדי)\s*(אלף|א[\'׳]?)\b', 'צא', t)
    t = re.sub(r'\b(צדיק|צדיג|צדי)\s*(בית|ב[\'׳]?)\b', 'צב', t)
    t = re.sub(r'\b(צדיק|צדיג|צדי)\s*(גימל|ג[\'׳]?)\b', 'צג', t)
    t = re.sub(r'\b(צדיק|צדיג|צדי)\s*(דלת|ד[\'׳]?)\b', 'צד', t)
    t = re.sub(r'\b(צדיק|צדיג|צדי)\s*(הא|ה[\'׳]?)\b', 'צה', t)
    t = re.sub(r'\b(צדיק|צדיג|צדי)\s*(ויו|ו[\'׳]?)\b', 'צו', t)
    t = re.sub(r'\b(צדיק|צדיג|צדי)\s*(זיין|זין|ז[\'׳]?)\b', 'צז', t)
    t = re.sub(r'\b(צדיק|צדיג|צדי)\s*(חית|ח[\'׳]?)\b', 'צח', t)
    t = re.sub(r'\b(צדיק|צדיג|צדי)\s*(טית|ט[\'׳]?)\b', 'צט', t)
    # Whisper phonetic 'צדיג' alone (e.g. 'דף צדיג עמוד ב') -> 'דף צג עמוד ב'
    t = re.sub(r'\bצדיג\b', 'צג', t)
    t = re.sub(r'(?<=\b(דף|פרק|סימן|סעיף|פסקה|שיעור|אות|הלכה)\s)צדיק\b', 'צ', t)

    # Handle 'יוד' combinations
    t = re.sub(r'\b(יוד|יו\'\'ד)\s*(אלף|א[\'׳]?)\b', 'יא', t)
    t = re.sub(r'\b(יוד|יו\'\'ד)\s*(בית|ב[\'׳]?)\b', 'יב', t)
    t = re.sub(r'\b(יוד|יו\'\'ד)\s*(גימל|ג[\'׳]?)\b', 'יג', t)
    t = re.sub(r'\b(יוד|יו\'\'ד)\s*(דלת|ד[\'׳]?)\b', 'יד', t)
    t = re.sub(r'\b(יוד|יו\'\'ד)\s*(הא|ה[\'׳]?)\b', 'טו', t)
    t = re.sub(r'\b(יוד|יו\'\'ד)\s*(ויו|ו[\'׳]?)\b', 'טז', t)
    t = re.sub(r'\b(יוד|יו\'\'ד)\s*(זיין|זין|ז[\'׳]?)\b', 'יז', t)
    t = re.sub(r'\b(יוד|יו\'\'ד)\s*(חית|ח[\'׳]?)\b', 'יח', t)
    t = re.sub(r'\b(יוד|יו\'\'ד)\s*(טית|ט[\'׳]?)\b', 'יט', t)
    t = re.sub(r'(?<=\b(דף|פרק|סימן|סעיף|פסקה|שיעור|אות|הלכה)\s)יוד\b', 'י', t)

    # Handle 'כף' combinations
    t = re.sub(r'\bכף\s*(אלף|א[\'׳]?)\b', 'כא', t)
    t = re.sub(r'\bכף\s*(בית|ב[\'׳]?)\b', 'כב', t)
    t = re.sub(r'\bכף\s*(גימל|ג[\'׳]?)\b', 'כג', t)
    t = re.sub(r'\bכף\s*(דלת|ד[\'׳]?)\b', 'כד', t)
    t = re.sub(r'\bכף\s*(הא|ה[\'׳]?)\b', 'כה', t)
    t = re.sub(r'\bכף\s*(ויו|ו[\'׳]?)\b', 'כו', t)
    t = re.sub(r'\bכף\s*(זיין|זין|ז[\'׳]?)\b', 'כז', t)
    t = re.sub(r'\bכף\s*(חית|ח[\'׳]?)\b', 'כח', t)
    t = re.sub(r'\bכף\s*(טית|ט[\'׳]?)\b', 'כט', t)
    t = re.sub(r'(?<=\b(דף|פרק|סימן|סעיף|פסקה|שיעור|אות|הלכה)\s)כף\b', 'כ', t)

    # Handle 'למד' combinations
    t = re.sub(r'\bלמד\s*(אלף|א[\'׳]?)\b', 'לא', t)
    t = re.sub(r'\bלמד\s*(בית|ב[\'׳]?)\b', 'לב', t)
    t = re.sub(r'\bלמד\s*(גימל|ג[\'׳]?)\b', 'לג', t)
    t = re.sub(r'\bלמד\s*(דלת|ד[\'׳]?)\b', 'לד', t)
    t = re.sub(r'\bלמד\s*(הא|ה[\'׳]?)\b', 'לה', t)
    t = re.sub(r'\bלמד\s*(ויו|ו[\'׳]?)\b', 'לו', t)
    t = re.sub(r'\bלמד\s*(זיין|זין|ז[\'׳]?)\b', 'לז', t)
    t = re.sub(r'\bלמד\s*(חית|ח[\'׳]?)\b', 'לח', t)
    t = re.sub(r'\bלמד\s*(טית|ט[\'׳]?)\b', 'לט', t)
    t = re.sub(r'(?<=\b(דף|פרק|סימן|סעיף|פסקה|שיעור|אות|הלכה)\s)למד\b', 'ל', t)

    # Handle 'קוף', 'ריש' combinations
    t = re.sub(r'\bקוף\s*(אלף|א[\'׳]?)\b', 'קא', t)
    t = re.sub(r'\bקוף\s*(בית|ב[\'׳]?)\b', 'קב', t)
    t = re.sub(r'\bקוף\s*(גימל|ג[\'׳]?)\b', 'קג', t)
    t = re.sub(r'\bקוף\s*(דלת|ד[\'׳]?)\b', 'קד', t)
    t = re.sub(r'(?<=\b(דף|פרק|סימן|סעיף|פסקה|שיעור|אות|הלכה)\s)קוף\b', 'ק', t)

    t = re.sub(r'\bריש\s*(אלף|א[\'׳]?)\b', 'רא', t)
    t = re.sub(r'\bריש\s*(בית|ב[\'׳]?)\b', 'רב', t)
    t = re.sub(r'\bריש\s*(גימל|ג[\'׳]?)\b', 'רג', t)
    t = re.sub(r'\bריש\s*(דלת|ד[\'׳]?)\b', 'רד', t)
    t = re.sub(r'(?<=\b(דף|פרק|סימן|סעיף|פסקה|שיעור|אות|הלכה)\s)ריש\b', 'ר', t)

    # Single letter names after typical prefixes (e.g. 'פרק אלף' -> 'פרק א', 'דף בית' -> 'דף ב')
    letter_map = {
        'אלף': 'א', 'בית': 'ב', 'גימל': 'ג', 'דלת': 'ד', 'הא': 'ה',
        'ויו': 'ו', 'זיין': 'ז', 'זין': 'ז', 'חית': 'ח', 'טית': 'ט',
        'יוד': 'י', 'כף': 'כ', 'למד': 'ל', 'מם': 'מ', 'נון': 'נ',
        'סמך': 'ס', 'פה': 'פ', 'צדיק': 'צ', 'קוף': 'ק', 'ריש': 'ר',
        'שין': 'ש', 'תיו': 'ת'
    }
    for name, let in letter_map.items():
        t = re.sub(rf'(?<=\b(דף|פרק|סימן|סעיף|פסקה|שיעור|אות|הלכה|חלק|עמוד)\s){name}\b', let, t)

    # Clean double spaces
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def normalize_rabbi_name(name: Optional[str]) -> Optional[str]:
    """
    Strictly matches the Rabbi's name against the known rabbis in config.
    Returns the canonical full name from RABBIS_LIST, or None if no valid match.
    """
    if not name:
        return None
    trimmed = name.strip()
    
    if trimmed.lower() in ("null", "none", "לא ידוע", "לא זוהה", "רב אחר", "כללי"):
        return None

    rabbis_list = getattr(config, "RABBIS_LIST", config.KNOWN_RABBIS)
    
    # 1. Exact match or with 'הרב'
    for known in rabbis_list:
        if known == trimmed or known == f"הרב {trimmed}":
            return known
            
    # 2. Normalized match (remove prefixes, spaces, normalize letters)
    def simplify(s: str) -> str:
        s = s.replace("הרב", "").replace("ר'", "").replace('"', '').replace("'", "")
        s = s.replace("ע", "א").replace("ת", "ט").replace("כ", "ק").replace("-", " ")
        return re.sub(r'\s+', '', s.strip())
        
    sim_trimmed = simplify(trimmed)
    if not sim_trimmed:
        return None

    # Exact simplified match
    for known in rabbis_list:
        if simplify(known) == sim_trimmed:
            return known

    # First name / unique substring match (e.g. 'דרור' -> 'הרב דרור שילה', 'יוסי' -> 'הרב יוסי הורביץ')
    matched = []
    for known in rabbis_list:
        known_parts = known.replace("הרב", "").replace("ר'", "").split()
        first_name = known_parts[0] if known_parts else ""
        if len(first_name) >= 3 and simplify(first_name) == sim_trimmed:
            matched.append(known)
            
    if len(matched) == 1:
        return matched[0]

    # Check if sim_trimmed contains first and last name or vice versa
    for known in rabbis_list:
        sim_known = simplify(known)
        if len(sim_trimmed) >= 4 and (sim_trimmed in sim_known or sim_known in sim_trimmed):
            return known

    # Strict enforcement: if not matched to a known rabbi, return None
    return None

def normalize_topic(topic: Any) -> Any:
    """Normalizes topic value, converting placeholder strings to None and fixing Hebrew letter names."""
    if not topic or not isinstance(topic, str):
        return None
    trimmed = topic.strip()
    if trimmed.lower() in NO_TOPIC_VALUES:
        return None
    
    # Automatically fix spelled out Gematria and letter names (e.g. 'צדיק ב' -> 'צב')
    fixed = fix_spoken_gematria_and_letters(trimmed)
    return fixed

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

    # Focus on the intro announcement words
    words = transcript.split()
    focused_transcript = " ".join(words[:45]) if len(words) > 45 else transcript

    print(f"[AI] Extracting entities from transcript (first {len(focused_transcript.split())} words): \"{focused_transcript}\"")

    rabbis_list = getattr(config, "RABBIS_LIST", config.KNOWN_RABBIS)
    known_rabbis_str = ", ".join(rabbis_list)
    prompt = (
        "אתה עוזר חכם למערכת מיון שיעורי תורה בישיבה. תפקידך לחלץ מתוך תמלול השיעור את שם הרב ואת נושא השיעור.\n"
        f"רשימת רבני הישיבה המוכרים בלבד: {known_rabbis_str}.\n\n"
        "שים לב לחוקים והנחיות קריטיות:\n"
        "1. זיהוי שם הרב (אכיפה קשיחה):\n"
        "   - חובה לבחור את שם הרב אך ורק מתוך רשימת רבני הישיבה שצוינה למעלה!\n"
        "   - אם התלמיד בהכרזה אמר שם פרטי או קיצור (למשל: 'הרב דרור', 'הרב יוסי', 'הרב שמריהו', 'הרב ערן', 'הרב אמיר', 'הרב קובי', 'הרב אבי'), התאם אותו לשם המלא המתאים מהרשימה.\n"
        "   - אם השם שגוי/משובש קלות (למשל: 'דור שינו' -> 'הרב דרור שילה', 'הרב שמיר הוא' -> 'הרב שמריהו הופמן', 'עבורי'/'אורי' -> 'הרב אורי שטרנברג'), בחר את השם המתאים מהרשימה.\n"
        "   - אם לא הוזכר בהכרזה במפורש אחד מרבני הישיבה מהרשימה, חובה להחזיר null עבור rabbi (אל תמציא שמות שלא ברשימה!).\n\n"
        "2. נושא השיעור:\n"
        "   - חלץ את נושא השיעור המלא (שם הספר, המסכת, הפרק, הפסקה או הסוגיה) כפי שהוכרז בהכרזת הפתיחה.\n"
        "   - חובה להמיר שמות אותיות ומספרים מדוברים לפורמט תורני מקוצר:\n"
        "     'צדיק ב' / 'צדיק בית' -> 'צב'\n"
        "     'צדיק ג' / 'צדיג' -> 'צג'\n"
        "     'צדיק ד' -> 'צד'\n"
        "     'יוד אלף' -> 'יא'\n"
        "     'יוד בית' -> 'יב'\n"
        "     'כף ב' -> 'כב'\n"
        "     'פרק אלף' -> 'פרק א'\n"
        "     'דף בית' -> 'דף ב' וכו'.\n"
        "   - התמקד בנושא שהוכרז. אל תכניס לנושא דברי פתיחה, שאלות, סיפורים או משפטים שמתחילים בגוף השיעור (כגון 'טוב אנחנו נתחיל', 'נחזור למה שאמרנו', דיבורים של תלמידים וכו').\n"
        "   - אם לא צוין נושא בהכרזה, החזר null עבור topic.\n\n"
        "דוגמאות:\n"
        "---\n"
        "קלט: \"הרב ערן, חבורה באורות התחייה, יום שני, ד' אלול, פרק כז'.\"\n"
        "פלט: {\"rabbi\": \"הרב ערן היימן\", \"topic\": \"אורות התחייה פרק כז\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"ג' אלול, הרב דרור עורות התשובה, פרק יוד אלף פסקה א'. טוב, אז אנחנו נתחיל...\"\n"
        "פלט: {\"rabbi\": \"הרב דרור שילה\", \"topic\": \"אורות התשובה פרק יא פסקה א\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"הרב יוסי, עיון, בבא מציעא, פרק השואל, דף צדיג עמוד ב', שמירה כדנתרי אינשי, ה' אלול. אתה אומר את המשנה...\"\n"
        "פלט: {\"rabbi\": \"הרב יוסי הורביץ\", \"topic\": \"עיון בבא מציעא פרק השואל דף צג עמוד ב שמירה כדנתרי אינשי\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"יא אלול, הרב אבי טילמן, שיעור בתפארת ישראל, שיעור שני.\"\n"
        "פלט: {\"rabbi\": \"הרב אבי טילמן\", \"topic\": \"תפארת ישראל שיעור שני\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"הרב קובי, אורות התשובה, פרק יז. אז ראינו אתמול...\"\n"
        "פלט: {\"rabbi\": \"הרב קובי דביר\", \"topic\": \"אורות התשובה פרק יז\", \"status\": \"identified\"}\n"
        "---\n"
        "קלט: \"אוקיי, צריך קליאת הזהירות. הנה האמצעים אשר נקנה בם בזריזות...\"\n"
        "פלט: {\"rabbi\": null, \"topic\": null, \"status\": \"unidentified\"}\n"
        "---\n\n"
        f"התמלול לעיבוד:\n\"\"\"\n{focused_transcript}\n\"\"\"\n\n"
        "חובה להחזיר אך ורק אובייקט JSON תקין (ללא שום טקסט נוסף) במבנה הבא:\n"
        "{\n"
        "  \"rabbi\": \"שם הרב המלא מתוך הרשימה בלבד\" | null,\n"
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

        # Post-process and normalize strictly
        rabbi = normalize_rabbi_name(raw_rabbi)
        topic = normalize_topic(raw_topic)
        
        # Fundamental Rule: Strict Rabbi Enforcement
        # If no recognized Rabbi from the yeshiva list was found, mark as unidentified
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
    Format: 'שם הרב_נושא השיעור_(תאריך).mp3' (underscores only between sections, spaces inside).
    Returns a tuple of (filename, is_identified_bool).
    """
    hebrew_date_str = get_hebrew_date_str(file_dt) # e.g. "יא אלול תשפו"
    status = metadata.get("status", "unidentified")
    rabbi = metadata.get("rabbi")
    topic = metadata.get("topic")

    if status == "identified" and rabbi:
        clean_rabbi = clean_name_for_filename(rabbi)
        if topic:
            clean_topic = clean_name_for_filename(topic)
            filename = f"{clean_rabbi}_{clean_topic}_({hebrew_date_str}){original_extension}"
        else:
            filename = f"{clean_rabbi}_({hebrew_date_str}){original_extension}"
        return filename, True
    else:
        filename = f"לסיווג ידני_({hebrew_date_str}){original_extension}"
        return filename, False


