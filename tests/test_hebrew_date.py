from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace

import pytest
from mutagen.id3 import ID3, TDAT, TIME, TDRC, TXXX, TYER
from mutagen.mp3 import MP3

from core import hebrew_date
from tests.conftest import make_valid_mp3_bytes, make_valid_wav_bytes


def test_get_israel_sunset_time_seasonal_bounds():
    winter_sunset = hebrew_date.get_israel_sunset_time(date(2026, 12, 21))
    summer_sunset = hebrew_date.get_israel_sunset_time(date(2026, 6, 21))

    assert isinstance(winter_sunset, time)
    assert isinstance(summer_sunset, time)
    assert time(16, 0) <= winter_sunset <= time(17, 30)
    assert time(19, 0) <= summer_sunset <= time(20, 15)


def test_get_hebrew_date_str_format_and_sunset_shift():
    morning = datetime(2026, 11, 14, 10, 0, 0)
    late_night = datetime(2026, 11, 14, 23, 30, 0)
    next_day = datetime(2026, 11, 15, 10, 0, 0)

    heb_morning = hebrew_date.get_hebrew_date_str(morning, check_sunset=False)
    heb_night_no_shift = hebrew_date.get_hebrew_date_str(late_night, check_sunset=False)
    heb_night_shifted = hebrew_date.get_hebrew_date_str(late_night, check_sunset=True)
    heb_next_day = hebrew_date.get_hebrew_date_str(next_day, check_sunset=False)

    assert heb_morning == heb_night_no_shift
    assert heb_night_shifted == heb_next_day
    assert heb_morning != heb_next_day
    for ch in ('"', "'", "״", "׳"):
        assert ch not in heb_morning


def test_extract_hebrew_date_from_filename_and_clean():
    assert hebrew_date.extract_hebrew_date_from_filename("(כד חשון תשפז) 11-32.mp3") == "כד חשון תשפז"
    assert hebrew_date.extract_hebrew_date_from_filename('(כ"ד_חשון_תשפ״ז) 11-32.mp3') == "כד חשון תשפז"
    assert hebrew_date.extract_hebrew_date_from_filename("(12345) recording.mp3") is None
    assert hebrew_date.extract_hebrew_date_from_filename("plain_filename.mp3") is None
    assert hebrew_date.clean_hebrew_date_str('כ"ד   חשון\tתשפ״ז׳') == "כד חשון תשפז"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-11-14 11:02:30", datetime(2026, 11, 14, 11, 2, 30)),
        ("2026-11-14T11:02:30Z", datetime(2026, 11, 14, 11, 2, 30)),
        ("2026-11-14T11:02", datetime(2026, 11, 14, 11, 2)),
        ("2026-11-14", datetime(2026, 11, 14, 0, 0)),
        ("20261114_110230", datetime(2026, 11, 14, 11, 2, 30)),
        ("20261114_1102", datetime(2026, 11, 14, 11, 2)),
        ("2026-11-14 11:02", datetime(2026, 11, 14, 11, 2)),
        ("", None),
        ("invalid-date", None),
    ],
)
def test_parse_iso_or_flexible_datetime(raw, expected):
    assert hebrew_date.parse_iso_or_flexible_datetime(raw) == expected


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("20261114_110230.mp3", datetime(2026, 11, 14, 11, 2, 30)),
        ("REC_20261114-1102.wav", datetime(2026, 11, 14, 11, 2)),
        ("261103_1159.mp3", datetime(2026, 11, 3, 11, 59)),
        ("141126_1102.mp3", datetime(2026, 11, 14, 11, 2)),
        ("14.11.2026_11.02.mp3", datetime(2026, 11, 14, 11, 2)),
        ("2026-11-14 11:02.mp3", datetime(2026, 11, 14, 11, 2)),
        ("shiur_no_date.mp3", None),
    ],
)
def test_parse_filename_datetime(filename, expected):
    assert hebrew_date.parse_filename_datetime(filename) == expected


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("(כד חשון תשפז) 11-32.mp3", time(11, 32)),
        ("19.49.mp3", time(19, 49)),
        ("track_08_15_05.mp3", time(8, 15, 5)),
        ("shiur_rabbi.mp3", None),
    ],
)
def test_parse_filename_time_only(filename, expected):
    assert hebrew_date.parse_filename_time_only(filename) == expected


def test_extract_wav_riff_datetime(tmp_path: Path):
    bext_wav = tmp_path / "bext.wav"
    bext_wav.write_bytes(make_valid_wav_bytes(bext_date="2026-11-14", bext_time="19:30:15"))
    assert hebrew_date.extract_wav_riff_datetime(bext_wav) == datetime(2026, 11, 14, 19, 30, 15)

    plain_wav = tmp_path / "plain.wav"
    plain_wav.write_bytes(make_valid_wav_bytes())
    assert hebrew_date.extract_wav_riff_datetime(plain_wav) is None

    not_wav = tmp_path / "bad.wav"
    not_wav.write_bytes(b"NOT_RIFF_DATA")
    assert hebrew_date.extract_wav_riff_datetime(not_wav) is None


def test_extract_sony_icd_datetime(tmp_path: Path):
    sony_mp3 = tmp_path / "sony.mp3"
    payload = b"ID3\x03\x00\x00\x00\x00\x00\x40GEOB\x00\x00\x00\x20SonyRec2026-11-14T19:45:12\x00"
    sony_mp3.write_bytes(payload + make_valid_mp3_bytes())
    assert hebrew_date.extract_sony_icd_datetime(sony_mp3) == datetime(2026, 11, 14, 19, 45, 12)

    normal_mp3 = tmp_path / "normal.mp3"
    normal_mp3.write_bytes(make_valid_mp3_bytes())
    assert hebrew_date.extract_sony_icd_datetime(normal_mp3) is None


def test_extract_audio_metadata_datetime_variants(tmp_path: Path):
    # 1. TDRC
    p_tdrc = tmp_path / "tdrc.mp3"
    p_tdrc.write_bytes(make_valid_mp3_bytes())
    mp3_tdrc = MP3(str(p_tdrc))
    mp3_tdrc.add_tags()
    mp3_tdrc.tags.add(TDRC(encoding=3, text=["2026-11-14T14:20:00"]))
    mp3_tdrc.save()
    assert hebrew_date.extract_audio_metadata_datetime(p_tdrc) == datetime(2026, 11, 14, 14, 20, 0)

    # 2. TDAT + TIME + TYER (ID3v2.3)
    p_v23 = tmp_path / "v23.mp3"
    p_v23.write_bytes(make_valid_mp3_bytes())
    tags_v23 = ID3()
    tags_v23.add(TYER(encoding=3, text=["2026"]))
    tags_v23.add(TDAT(encoding=3, text=["1411"]))
    tags_v23.add(TIME(encoding=3, text=["1930"]))
    tags_v23.save(str(p_v23), v2_version=3)
    assert hebrew_date.extract_audio_metadata_datetime(p_v23) == datetime(2026, 11, 14, 19, 30)

    # 3. TXXX:recorded_at
    p_txxx = tmp_path / "txxx.mp3"
    p_txxx.write_bytes(make_valid_mp3_bytes())
    mp3_txxx = MP3(str(p_txxx))
    mp3_txxx.add_tags()
    mp3_txxx.tags.add(TXXX(encoding=3, desc="recorded_at", text=["2026-11-14 18:15:00"]))
    mp3_txxx.save()
    assert hebrew_date.extract_audio_metadata_datetime(p_txxx) == datetime(2026, 11, 14, 18, 15, 0)


def test_extract_recording_datetime_hierarchy(tmp_path: Path):
    # 1. Full datetime in filename takes top priority over Sony header and stat
    f1 = tmp_path / "20261114_103000.mp3"
    f1.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x302025-01-01T08:00:00" + make_valid_mp3_bytes())
    assert hebrew_date.extract_recording_datetime(f1) == datetime(2026, 11, 14, 10, 30, 0)

    # 2. Sony ICD hardware timestamp takes priority over time-only filename and stat
    f2 = tmp_path / "22.00.mp3"
    f2.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x302026-11-10T16:40:05" + make_valid_mp3_bytes())
    assert hebrew_date.extract_recording_datetime(f2) == datetime(2026, 11, 10, 16, 40, 5)

    # 3. Time-only in filename + file stat date
    f3 = tmp_path / "(ה כסלו תשפז) 19.49.mp3"
    f3.write_bytes(make_valid_mp3_bytes())
    stat_dt = datetime(2026, 11, 15, 8, 0, 0)
    assert hebrew_date.extract_recording_datetime(
        f3, stat_obj=SimpleNamespace(st_mtime=stat_dt.timestamp())
    ) == datetime(2026, 11, 15, 19, 49, 0)

    # 4. File stat mtime directly when filename has no date/time
    f4 = tmp_path / "lesson.mp3"
    f4.write_bytes(make_valid_mp3_bytes())
    assert hebrew_date.extract_recording_datetime(
        f4, stat_obj=SimpleNamespace(st_mtime=stat_dt.timestamp())
    ) == stat_dt

    # 5. Audio metadata fallback when stat_obj year is out of valid range [2000..2040]
    f5 = tmp_path / "meta_fallback.mp3"
    f5.write_bytes(make_valid_mp3_bytes())
    mp3_f5 = MP3(str(f5))
    mp3_f5.add_tags()
    mp3_f5.tags.add(TDRC(encoding=3, text=["2026-11-12T20:15:00"]))
    mp3_f5.save()
    old_stat = SimpleNamespace(st_mtime=datetime(1995, 1, 1, 0, 0, 0).timestamp())
    assert hebrew_date.extract_recording_datetime(f5, stat_obj=old_stat) == datetime(2026, 11, 12, 20, 15, 0)
