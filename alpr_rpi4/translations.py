"""
ALPR System — Translations
============================
Language support (Dutch and English) — shared with v2.
Used by any text output that needs localisation.
"""

import threading

LANGUAGES = {
    "nl": {
        "name": "Nederlands",
        "app_title": "ALPR",
        "app_subtitle": "Kentekenherkenning",
        "status_loading": "Laden...",
        "status_ready": "Gereed",
        "status_error": "Fout!",
        "progress_detecting": "Kentekens detecteren...",
        "progress_classifying": "Kleuren classificeren...",
        "progress_preprocessing": "Voorverwerking...",
        "progress_ocr": "Tekst herkennen (OCR)...",
        "progress_complete": "Klaar!",
        "progress_initializing": "Pipeline initialiseren...",
    },
    "en": {
        "name": "English",
        "app_title": "ALPR",
        "app_subtitle": "License Plate Recognition",
        "status_loading": "Loading...",
        "status_ready": "Ready",
        "status_error": "Error!",
        "progress_detecting": "Detecting plates...",
        "progress_classifying": "Classifying colors...",
        "progress_preprocessing": "Preprocessing...",
        "progress_ocr": "Reading text (OCR)...",
        "progress_complete": "Done!",
        "progress_initializing": "Initializing pipeline...",
    },
}

_lang_local = threading.local()


def _get_lang() -> str:
    return getattr(_lang_local, "lang", "en")


def set_language(lang_code: str):
    if lang_code in LANGUAGES:
        _lang_local.lang = lang_code


def get_language() -> str:
    return _get_lang()


def t(key: str) -> str:
    return LANGUAGES.get(_get_lang(), LANGUAGES["en"]).get(key, key)
