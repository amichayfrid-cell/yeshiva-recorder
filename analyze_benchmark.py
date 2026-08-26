import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Ensure parent directory is in path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config

def load_history(history_file_path: Path) -> List[Dict[str, Any]]:
    """Loads and returns history records from the given JSON file path."""
    if not history_file_path.exists():
        print(f"[!] History file not found: {history_file_path}")
        return []

    try:
        with open(history_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        print(f"[!] Error parsing {history_file_path}: {e}")
        return []

def format_duration(seconds: float) -> str:
    """Formats seconds into human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = int(seconds // 60)
    rem_secs = seconds % 60
    return f"{mins}m {rem_secs:.1f}s"

def analyze_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes statistical metrics and aggregations from history records."""
    total = len(records)
    if total == 0:
        return {}

    identified_count = 0
    unidentified_count = 0
    rabbis_dist: Dict[str, int] = {}
    durations: List[float] = []
    unidentified_items = []
    identified_items = []

    for idx, rec in enumerate(records, start=1):
        status = rec.get("status", "unknown")
        meta = rec.get("metadata", {})
        rabbi = meta.get("rabbi")
        topic = meta.get("topic")
        transcript = meta.get("transcript", "")
        duration = meta.get("duration_sec")

        if duration is not None and isinstance(duration, (int, float)):
            durations.append(float(duration))

        is_identified = (status == "sorted" or meta.get("status") == "identified") and rabbi is not None

        item_info = {
            "index": idx,
            "original_filename": rec.get("original_filename", ""),
            "final_filepath": rec.get("final_filepath", ""),
            "rabbi": rabbi,
            "topic": topic,
            "status": "identified" if is_identified else "unidentified",
            "duration_sec": duration,
            "transcript": transcript,
            "sha256": rec.get("sha256")
        }

        if is_identified:
            identified_count += 1
            rabbis_dist[rabbi] = rabbis_dist.get(rabbi, 0) + 1
            identified_items.append(item_info)
        else:
            unidentified_count += 1
            unidentified_items.append(item_info)

    # Timing calculations
    avg_duration = sum(durations) / len(durations) if durations else 0.0
    min_duration = min(durations) if durations else 0.0
    max_duration = max(durations) if durations else 0.0
    durations_sorted = sorted(durations)
    median_duration = durations_sorted[len(durations_sorted) // 2] if durations_sorted else 0.0
    total_processing_time = sum(durations)

    return {
        "total": total,
        "identified_count": identified_count,
        "identified_pct": (identified_count / total) * 100 if total > 0 else 0,
        "unidentified_count": unidentified_count,
        "unidentified_pct": (unidentified_count / total) * 100 if total > 0 else 0,
        "rabbis_dist": dict(sorted(rabbis_dist.items(), key=lambda x: x[1], reverse=True)),
        "avg_duration": avg_duration,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "median_duration": median_duration,
        "total_processing_time": total_processing_time,
        "durations_available": len(durations),
        "identified_items": identified_items,
        "unidentified_items": unidentified_items,
        "all_items": identified_items + unidentified_items
    }

def print_terminal_report(stats: Dict[str, Any]):
    """Prints a beautiful and clear benchmark summary in the terminal."""
    if not stats:
        print("\n[!] No records found in history to analyze.\n")
        return

    print("\n" + "=" * 70)
    print(" 📊 דוח ניתוח וביצועים - מבחן שיעורי תורה (Benchmark Report)")
    print("=" * 70)

    print(f"\n📁 סך הכל שיעורים שעובדו: {stats['total']}")
    print(f"✅ זוהו בהצלחה:           {stats['identified_count']} ({stats['identified_pct']:.1f}%)")
    print(f"⚠️ נשלחו לסיווג ידני:     {stats['unidentified_count']} ({stats['unidentified_pct']:.1f}%)")

    if stats["durations_available"] > 0:
        print("\n⏱️ זמני עיבוד (חיתוך + תמלול STT + חילוץ AI):")
        print(f"  • זמן ממוצע לשיעור:     {format_duration(stats['avg_duration'])}")
        print(f"  • חציון זמן עיבוד:      {format_duration(stats['median_duration'])}")
        print(f"  • שיעור הכי מהיר:       {format_duration(stats['min_duration'])}")
        print(f"  • שיעור הכי איטי:       {format_duration(stats['max_duration'])}")
        print(f"  • סה\"כ זמן עיבוד כולל:  {format_duration(stats['total_processing_time'])}")

    if stats["rabbis_dist"]:
        print("\n👑 התפלגות שיעורים לפי רבנים שזוהו:")
        for rabbi, count in stats["rabbis_dist"].items():
            pct = (count / stats["identified_count"]) * 100 if stats["identified_count"] > 0 else 0
            bar = "█" * int(pct / 5)
            print(f"  • {rabbi:<18} | {count:>2} שיעורים ({pct:>4.1f}%) {bar}")

    if stats["unidentified_items"]:
        print("\n" + "-" * 70)
        print("🔍 פירוט שיעורים שנשלחו לסיווג ידני (טעוני בדיקה/כיול):")
        print("-" * 70)
        for item in stats["unidentified_items"]:
            orig = item["original_filename"]
            transcript = item["transcript"] or "*(תמלול ריק או ללא שמע)*"
            print(f"\n[#{item['index']}] קובץ מקורי: {orig}")
            print(f"  תמלול ה-STT שנקלט: \"{transcript}\"")
            if not item["rabbi"]:
                print("  סיבת אי-זיהוי: לא נמצא שם רב מוכר בתמלול הפתיח.")

    print("\n" + "=" * 70)
    print("✓ סיום הדוח.")
    print("=" * 70 + "\n")

def generate_markdown_report(stats: Dict[str, Any], output_file: Path) -> None:
    """Exports a comprehensive Markdown report of the benchmark."""
    if not stats:
        return

    lines = []
    lines.append("# דוח תוצאות ומדדי ביצוע - מבחן שיעורי תורה (Benchmark Report)\n")
    lines.append(f"- **תאריך הפקה:** `{Path(output_file).stem}`")
    lines.append(f"- **סך הכל קבצים שעובדו:** `{stats['total']}`")
    lines.append(f"- **אחוז זיהוי מוצלח:** `{stats['identified_pct']:.1f}%` ({stats['identified_count']}/{stats['total']})")
    lines.append(f"- **אחוז סיווג ידני:** `{stats['unidentified_pct']:.1f}%` ({stats['unidentified_count']}/{stats['total']})\n")

    if stats["durations_available"] > 0:
        lines.append("## ⏱️ מדדי זמני עיבוד\n")
        lines.append("| מדד | משך זמן |")
        lines.append("| :--- | :--- |")
        lines.append(f"| **זמן ממוצע לשיעור** | {format_duration(stats['avg_duration'])} |")
        lines.append(f"| **חציון זמן עיבוד** | {format_duration(stats['median_duration'])} |")
        lines.append(f"| **זמן מינימלי (הכי מהיר)** | {format_duration(stats['min_duration'])} |")
        lines.append(f"| **זמן מקסימלי (הכי איטי)** | {format_duration(stats['max_duration'])} |")
        lines.append(f"| **סך הכל זמן עיבוד כולל** | {format_duration(stats['total_processing_time'])} |\n")

    if stats["rabbis_dist"]:
        lines.append("## 👑 התפלגות רבנים שזוהו\n")
        lines.append("| שם הרב | כמות שיעורים | אחוז מסך המזוהים |")
        lines.append("| :--- | :---: | :---: |")
        for rabbi, count in stats["rabbis_dist"].items():
            pct = (count / stats["identified_count"]) * 100 if stats["identified_count"] > 0 else 0
            lines.append(f"| {rabbi} | {count} | {pct:.1f}% |")
        lines.append("")

    lines.append("## 📋 פירוט מלא של כל השיעורים במבחן\n")
    lines.append("| # | שם מקורי | שם יעד שנוצר | רב | נושא | סטטוס | משך |")
    lines.append("| :-: | :--- | :--- | :--- | :--- | :-: | :-: |")

    # Combine identified and unidentified sorted by index
    all_sorted = sorted(stats["all_items"], key=lambda x: x["index"])
    for item in all_sorted:
        target_name = Path(item["final_filepath"]).name if item["final_filepath"] else "-"
        rabbi_str = item["rabbi"] or "-"
        topic_str = item["topic"] or "-"
        status_icon = "✅ מזוהה" if item["status"] == "identified" else "⚠️ סיווג ידני"
        dur_str = f"{item['duration_sec']:.1f}s" if item["duration_sec"] is not None else "-"
        lines.append(f"| {item['index']} | `{item['original_filename']}` | `{target_name}` | {rabbi_str} | {topic_str} | {status_icon} | {dur_str} |")
    lines.append("")

    if stats["unidentified_items"]:
        lines.append("## 🔍 ניתוח מעמיק של שיעורים לסיווג ידני\n")
        for item in stats["unidentified_items"]:
            lines.append(f"### שיעור #{item['index']}: `{item['original_filename']}`")
            lines.append(f"- **קובץ יעד:** `{Path(item['final_filepath']).name}`")
            lines.append(f"- **תמלול הפתיח שנקלט:** \"{item['transcript']}\"")
            lines.append(f"- **אבחנה:** לא אותר שם רב מרשימת רבני הישיבה בתמלול.\n")

    output_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"[✓] Markdown report successfully saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Analyze Yeshiva Recorder benchmark history log.")
    parser.add_argument(
        "--history",
        type=str,
        default=str(config.HISTORY_FILE),
        help="Path to history.json file (default: data/history.json)"
    )
    parser.add_argument(
        "--export",
        type=str,
        default="",
        help="Optional path to export a detailed Markdown report (e.g. benchmark_results.md)"
    )

    args = parser.parse_args()
    history_path = Path(args.history)
    
    records = load_history(history_path)
    stats = analyze_records(records)
    print_terminal_report(stats)

    if args.export:
        export_path = Path(args.export)
        generate_markdown_report(stats, export_path)

if __name__ == "__main__":
    main()
