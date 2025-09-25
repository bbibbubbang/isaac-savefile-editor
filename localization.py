from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple

_DATA_DIR = Path(__file__).resolve().parent
_I18N_DIR = _DATA_DIR / "i18n"
_UI_TRANSLATIONS_PATH = _I18N_DIR / "ui_translations.json"
_AUTO_OVERWRITE_STEPS_PATH = _I18N_DIR / "auto_overwrite_steps.json"

_ENGLISH_STEPS: Tuple[str, ...] = (
    "1. Click 'Select Source Save File' to choose the reference save file.",
    "2. Click 'Select Target Save File' to choose the in-game save to overwrite.",
    "3. Check 'Overwrite Automatically' to save the paths and copy the source file automatically on startup.",
)
_KOREAN_STEPS: Tuple[str, ...] = (
    "1. '원본 세이브파일 열기' 버튼을 눌러 기준이 되는 세이브파일을 선택하세요.",
    "2. '덮어쓰기할 세이브파일 열기' 버튼을 눌러 실제 게임 세이브파일을 선택하세요.",
    "3. '세이브파일 자동 덮어쓰기'를 체크하면 경로가 저장되고, 프로그램 실행 시 원본 세이브파일이 자동으로 덮어쓰기 경로에 복사됩니다.",
)

_LANGUAGE_CANONICAL_MAP: Dict[str, str] = {
    "": "",
    "bg": "bul",
    "bul": "bul",
    "cs": "cs_cz",
    "cz": "cs_cz",
    "cs_cz": "cs_cz",
    "de": "de",
    "de_de": "de",
    "el": "el_gr",
    "el_gr": "el_gr",
    "en": "en_us",
    "en_us": "en_us",
    "en_gb": "en_us",
    "english": "en_us",
    "es": "spa",
    "es_es": "spa",
    "es_mx": "spa",
    "fr": "fr",
    "fr_fr": "fr",
    "it": "it",
    "it_it": "it",
    "ja": "ja_jp",
    "ja_jp": "ja_jp",
    "jp": "ja_jp",
    "ko": "ko_kr",
    "ko_kr": "ko_kr",
    "korean": "ko_kr",
    "nl": "nl_nl",
    "nl_nl": "nl_nl",
    "pl": "pl",
    "pl_pl": "pl",
    "pt": "pt",
    "pt_pt": "pt",
    "pt_br": "pt_br",
    "pt-br": "pt_br",
    "ro": "ro_ro",
    "ro_ro": "ro_ro",
    "ru": "ru",
    "ru_ru": "ru",
    "spa": "spa",
    "tr": "tr_tr",
    "tr_tr": "tr_tr",
    "uk": "uk_ua",
    "ua": "uk_ua",
    "uk_ua": "uk_ua",
    "vi": "vi",
    "vi_vn": "vi",
    "zh": "zh_cn",
    "zh_cn": "zh_cn",
    "zh-cn": "zh_cn",
    "zh_hans": "zh_cn",
}

_LANGUAGE_DISPLAY_NAMES: Dict[str, str] = {
    "bul": "Български",
    "cs_cz": "Čeština",
    "de": "Deutsch",
    "el_gr": "Ελληνικά",
    "en_us": "English",
    "fr": "Français",
    "it": "Italiano",
    "ja_jp": "日本語",
    "ko_kr": "한국어",
    "nl_nl": "Nederlands",
    "pl": "Polski",
    "pt": "Português",
    "pt_br": "Português (Brasil)",
    "ro_ro": "Română",
    "ru": "Русский",
    "spa": "Español",
    "tr_tr": "Türkçe",
    "uk_ua": "Українська",
    "vi": "Tiếng Việt",
    "zh_cn": "简体中文",
}


def _normalize_language_code(code: str) -> str:
    return str(code or "").strip().lower().replace("-", "_")


def _canonicalize_language_code(code: str) -> str:
    normalized = _normalize_language_code(code)
    return _LANGUAGE_CANONICAL_MAP.get(normalized, normalized)


def _iter_language_candidates(code: str) -> Iterable[str]:
    normalized = _normalize_language_code(code)
    candidates = [normalized]
    canonical = _canonicalize_language_code(normalized)
    if canonical != normalized:
        candidates.append(canonical)
    if "_" in normalized:
        base = normalized.split("_", 1)[0]
        candidates.append(base)
        canonical_base = _canonicalize_language_code(base)
        if canonical_base != base:
            candidates.append(canonical_base)
    candidates.extend(["en_us", "en"])
    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        canonical_candidate = _canonicalize_language_code(candidate)
        if canonical_candidate not in seen:
            seen.add(canonical_candidate)
            yield canonical_candidate


@lru_cache(maxsize=1)
def _load_ui_translations() -> Dict[str, Dict[str, str]]:
    try:
        raw = json.loads(_UI_TRANSLATIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    translations: Dict[str, Dict[str, str]] = {}
    for english_text, mapping in raw.items():
        if not isinstance(english_text, str) or not isinstance(mapping, dict):
            continue
        normalized_map = {
            _canonicalize_language_code(key): str(value)
            for key, value in mapping.items()
            if isinstance(value, str) and value.strip()
        }
        if normalized_map:
            translations[english_text] = normalized_map
    return translations


@lru_cache(maxsize=1)
def _load_auto_overwrite_steps() -> Dict[str, Tuple[str, ...]]:
    steps: Dict[str, Tuple[str, ...]] = {
        "en_us": _ENGLISH_STEPS,
        "ko_kr": _KOREAN_STEPS,
    }
    try:
        raw = json.loads(_AUTO_OVERWRITE_STEPS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return steps
    for code, value in raw.items():
        if not isinstance(value, (list, tuple)):
            continue
        normalized = tuple(str(item) for item in value if isinstance(item, str) and item.strip())
        if normalized:
            steps[_canonicalize_language_code(code)] = normalized
    return steps


def translate_ui_string(language_code: str, english: str, korean: str) -> str:
    english = english or ""
    if not english:
        return ""
    mapping = _load_ui_translations().get(english)
    if not mapping:
        return ""
    for candidate in _iter_language_candidates(language_code):
        translated = mapping.get(candidate)
        if translated:
            return translated
    return ""


def get_language_display_name(code: str, default: str) -> str:
    canonical = _canonicalize_language_code(code)
    if canonical in _LANGUAGE_DISPLAY_NAMES:
        return _LANGUAGE_DISPLAY_NAMES[canonical]
    base = canonical.split("_", 1)[0]
    if base in _LANGUAGE_DISPLAY_NAMES:
        return _LANGUAGE_DISPLAY_NAMES[base]
    return default


def get_auto_overwrite_steps(language_code: str) -> Sequence[str]:
    steps = _load_auto_overwrite_steps()
    for candidate in _iter_language_candidates(language_code):
        if candidate in steps:
            return steps[candidate]
    return steps["en_us"]


def is_english(code: str) -> bool:
    canonical = _canonicalize_language_code(code)
    return canonical.startswith("en")


def is_korean(code: str) -> bool:
    canonical = _canonicalize_language_code(code)
    return canonical == "ko_kr"
