"""
ALPR Systeem - Vertalingen
============================
Taalondersteuning voor de GUI (Nederlands en Engels).
"""

import threading

LANGUAGES = {
    "nl": {
        "name": "Nederlands",

        # Zijbalk
        "app_title": "ALPR",
        "app_subtitle": "Kentekenherkenning",
        "nav_label": "NAVIGATIE",
        "nav_images": "Afbeeldingen",
        "nav_video": "Video / Camera",
        "nav_history": "Geschiedenis",
        "nav_settings": "Instellingen",
        "status_loading": "Laden...",
        "status_ready": "Gereed",
        "status_error": "Fout!",
        "model_label": "Model",

        # Afbeeldingen pagina
        "images_title": "Afbeeldingen",
        "btn_analyze": "Analyseer",
        "btn_analyzing": "Bezig...",
        "btn_stop": "Stop",
        "btn_open_file": "Open Bestand",
        "btn_open_dir": "Open Map",
        "results_title": "Resultaten",
        "stat_found": "Gevonden",
        "stat_time": "Tijd (ms)",
        "stat_confidence": "Confidence",
        "placeholder_image": "Klik 'Open Bestand' of sleep een afbeelding hierheen",
        "no_results": "Nog geen kentekens gedetecteerd.\n\nLaad een afbeelding en klik\n'Analyseer' om te starten.",
        "no_results_found": "Geen kentekens gevonden.\n\nProbeer de confidence\ndrempel te verlagen.",
        "drag_drop_hint": "(of sleep bestand hierheen)",

        # Video pagina
        "video_title": "Video / Camera",
        "btn_open_video": "Open Video",
        "btn_start_camera": "Start Camera",
        "btn_stop_video": "Stop",
        "live_detection": "Live Detectie",
        "stat_fps": "FPS",
        "stat_unique": "Uniek",
        "frame_skip": "Frame skip:",
        "placeholder_video": "Open een videobestand of start de camera",

        # Geschiedenis pagina
        "history_title": "Geschiedenis",
        "btn_export_csv": "Exporteer CSV",
        "btn_clear_history": "Wis Geschiedenis",
        "col_plate": "Kenteken",
        "col_detection": "Detectie",
        "col_ocr": "OCR",
        "col_time": "Tijd",
        "history_empty": "Nog geen detecties in de geschiedenis.\nVerwerk afbeeldingen of video om te beginnen.",
        "confirm_clear": "Weet je zeker dat je alle geschiedenis wilt wissen?",
        "exported_msg": "Resultaten opgeslagen:",
        "no_data": "Er is nog geen geschiedenis om te exporteren.",

        # Instellingen pagina
        "settings_title": "Instellingen",
        "section_detection": "Detectie (YOLOv8)",
        "conf_threshold": "Confidence drempel",
        "conf_threshold_desc": "Minimale score om een kenteken te accepteren",
        "iou_threshold": "IoU drempel (NMS)",
        "iou_threshold_desc": "Non-Maximum Suppression overlap drempel",
        "section_preprocessing": "Preprocessing",
        "prep_resize": "Resize naar doelgrootte",
        "prep_grayscale": "Grijswaarden conversie",
        "prep_denoise": "Ruisreductie",
        "prep_contrast": "CLAHE contrastverhoging",
        "prep_sharpen": "Verscherping",
        "prep_binarize": "Adaptieve binarisatie",
        "denoise_strength": "Denoise sterkte",
        "denoise_strength_desc": "Hogere waarde = meer smoothing, minder detail",
        "section_colorfilter": "Kleurfilter",
        "colorfilter_enable": "Kleurfilter inschakelen",
        "plate_mode_label": "Kenteken modus",
        "vehicle_mode_label": "Voertuig Type",
        "option_car": "Auto (Langwerpig)",
        "option_scooter": "Scooter (Vierkant)",
        "option_both": "Allebei",
        "color_threshold": "Kleurdrempel",
        "color_threshold_desc": "Min. percentage pixels om een kleur toe te wijzen",
        "section_ocr": "OCR (EasyOCR)",
        "ocr_conf_min": "Minimale OCR confidence",
        "ocr_conf_min_desc": "Tekst met lagere confidence wordt genegeerd",
        "section_model": "Model",
        "btn_browse": "Bladeren",
        "btn_reload_model": "Model Herladen",
        "section_language": "Taal / Language",
        "language_label": "Interfacetaal",

        # Voortgang / Progress bar
        "progress_detecting": "Kentekens detecteren...",
        "progress_classifying": "Kleuren classificeren...",
        "progress_preprocessing": "Voorverwerking...",
        "progress_ocr": "Tekst herkennen (OCR)...",
        "progress_complete": "Klaar!",
        "progress_initializing": "Pipeline initialiseren...",

        # Ontwikkelaarsmodus
        "section_devmode": "Ontwikkelaarsmodus",
        "dev_mode_label": "Dev mode inschakelen",
        "dev_mode_desc": "Toon backend logging, timing en stappen",
        "dev_console": "Ontwikkelaarsconsole",
        "dev_clear": "Wis Log",
        "dev_no_logs": "Geen logs. Scan een afbeelding om output te zien.",

        # Dialogen
        "dialog_select_image": "Selecteer afbeelding",
        "dialog_select_dir": "Selecteer map met afbeeldingen",
        "dialog_select_video": "Selecteer video",
        "dialog_select_model": "Selecteer YOLOv8 model",
        "dialog_export_csv": "Exporteer als CSV",
        "dialog_no_images": "Geen afbeeldingen gevonden in deze map.",
        "dialog_load_error": "Kan afbeelding niet laden:",
        "dialog_video_error": "Kan videobron niet openen.",
        "dialog_pipeline_error": "Kan pipeline niet laden:",
        "dialog_model_not_found": "Modelbestand niet gevonden:",
        "dialog_not_ready": "Pipeline is nog niet geladen.",
        "dialog_scan_error": "Er ging iets mis:",
        "dialog_clear_title": "Wis geschiedenis",
        "dialog_exported_title": "Geexporteerd",
        "dialog_no_data_title": "Geen data",
        "dialog_error_title": "Fout",
        "dialog_load_error_title": "Fout bij laden",
        "dialog_scan_error_title": "Verwerkingsfout",

        # Brontype
        "source_image": "afbeelding",
        "source_video": "video",

        # Venstertitel
        "window_title": "ALPR Systeem \u2014 Kentekenherkenning",

        # Herlaad
        "reloading": "Herladen...",

        # Bestandstypen
        "filetypes_images": "Afbeeldingen",
        "filetypes_all": "Alle bestanden",
        "filetypes_video": "Video",
        "filetypes_model": "PyTorch model",
        "filetypes_csv": "CSV bestand",
    },

    "en": {
        "name": "English",

        # Sidebar
        "app_title": "ALPR",
        "app_subtitle": "License Plate Recognition",
        "nav_label": "NAVIGATION",
        "nav_images": "Images",
        "nav_video": "Video / Camera",
        "nav_history": "History",
        "nav_settings": "Settings",
        "status_loading": "Loading...",
        "status_ready": "Ready",
        "status_error": "Error!",
        "model_label": "Model",

        # Images page
        "images_title": "Images",
        "btn_analyze": "Analyze",
        "btn_analyzing": "Processing...",
        "btn_stop": "Stop",
        "btn_open_file": "Open File",
        "btn_open_dir": "Open Folder",
        "results_title": "Results",
        "stat_found": "Found",
        "stat_time": "Time (ms)",
        "stat_confidence": "Confidence",
        "placeholder_image": "Click 'Open File' or drag an image here",
        "no_results": "No license plates detected yet.\n\nLoad an image and click\n'Analyze' to start.",
        "no_results_found": "No license plates found.\n\nTry lowering the confidence\nthreshold.",
        "drag_drop_hint": "(or drag and drop file here)",

        # Video page
        "video_title": "Video / Camera",
        "btn_open_video": "Open Video",
        "btn_start_camera": "Start Camera",
        "btn_stop_video": "Stop",
        "live_detection": "Live Detection",
        "stat_fps": "FPS",
        "stat_unique": "Unique",
        "frame_skip": "Frame skip:",
        "placeholder_video": "Open a video file or start the camera",

        # History page
        "history_title": "History",
        "btn_export_csv": "Export CSV",
        "btn_clear_history": "Clear History",
        "col_plate": "Plate",
        "col_detection": "Detection",
        "col_ocr": "OCR",
        "col_time": "Time",
        "history_empty": "No detections in history yet.\nProcess images or video to get started.",
        "confirm_clear": "Are you sure you want to clear all history?",
        "exported_msg": "Results saved:",
        "no_data": "No history data to export yet.",

        # Settings page
        "settings_title": "Settings",
        "section_detection": "Detection (YOLOv8)",
        "conf_threshold": "Confidence threshold",
        "conf_threshold_desc": "Minimum score to accept a license plate",
        "iou_threshold": "IoU threshold (NMS)",
        "iou_threshold_desc": "Non-Maximum Suppression overlap threshold",
        "section_preprocessing": "Preprocessing",
        "prep_resize": "Resize to target size",
        "prep_grayscale": "Grayscale conversion",
        "prep_denoise": "Noise reduction",
        "prep_contrast": "CLAHE contrast enhancement",
        "prep_sharpen": "Sharpening",
        "prep_binarize": "Adaptive binarization",
        "denoise_strength": "Denoise strength",
        "denoise_strength_desc": "Higher value = more smoothing, less detail",
        "section_colorfilter": "Color Filter",
        "colorfilter_enable": "Enable color filter",
        "plate_mode_label": "Plate mode",
        "vehicle_mode_label": "Vehicle Type",
        "option_car": "Car (Rectangular)",
        "option_scooter": "Scooter (Square)",
        "option_both": "Both",
        "color_threshold": "Color threshold",
        "color_threshold_desc": "Min. pixel percentage to assign a color",
        "section_ocr": "OCR (EasyOCR)",
        "ocr_conf_min": "Minimum OCR confidence",
        "ocr_conf_min_desc": "Text below this confidence is ignored",
        "section_model": "Model",
        "btn_browse": "Browse",
        "btn_reload_model": "Reload Model",
        "section_language": "Taal / Language",
        "language_label": "Interface language",

        # Progress bar
        "progress_detecting": "Detecting plates...",
        "progress_classifying": "Classifying colors...",
        "progress_preprocessing": "Preprocessing...",
        "progress_ocr": "Reading text (OCR)...",
        "progress_complete": "Done!",
        "progress_initializing": "Initializing pipeline...",

        # Developer mode
        "section_devmode": "Developer Mode",
        "dev_mode_label": "Enable dev mode",
        "dev_mode_desc": "Show backend logging, timing and steps",
        "dev_console": "Developer Console",
        "dev_clear": "Clear Log",
        "dev_no_logs": "No logs yet. Scan an image to see output.",

        # Dialogs
        "dialog_select_image": "Select image",
        "dialog_select_dir": "Select folder with images",
        "dialog_select_video": "Select video",
        "dialog_select_model": "Select YOLOv8 model",
        "dialog_export_csv": "Export as CSV",
        "dialog_no_images": "No images found in this folder.",
        "dialog_load_error": "Cannot load image:",
        "dialog_video_error": "Cannot open video source.",
        "dialog_pipeline_error": "Cannot load pipeline:",
        "dialog_model_not_found": "Model file not found:",
        "dialog_not_ready": "Pipeline is not loaded yet.",
        "dialog_scan_error": "Something went wrong:",
        "dialog_clear_title": "Clear history",
        "dialog_exported_title": "Exported",
        "dialog_no_data_title": "No data",
        "dialog_error_title": "Error",
        "dialog_load_error_title": "Loading error",
        "dialog_scan_error_title": "Processing error",

        # Source type
        "source_image": "image",
        "source_video": "video",

        # Window title
        "window_title": "ALPR System \u2014 License Plate Recognition",

        # Reload
        "reloading": "Reloading...",

        # File types
        "filetypes_images": "Images",
        "filetypes_all": "All files",
        "filetypes_video": "Video",
        "filetypes_model": "PyTorch model",
        "filetypes_csv": "CSV file",
    },
}


# Thread-local taalinstelling (standaard Nederlands per thread)
_lang_local = threading.local()


def _get_lang() -> str:
    """Geef de actieve taalcode voor de huidige thread."""
    return getattr(_lang_local, "lang", "nl")


def set_language(lang_code: str):
    """Stel de actieve taal in voor de huidige thread."""
    if lang_code in LANGUAGES:
        _lang_local.lang = lang_code


def get_language() -> str:
    """Geef de actieve taalcode terug."""
    return _get_lang()


def t(key: str) -> str:
    """
    Vertaal een sleutel naar de huidige taal.

    Args:
        key: De vertaalsleutel (bijv. "btn_analyze")

    Returns:
        De vertaalde tekst, of de sleutel zelf als fallback
    """
    return LANGUAGES.get(_get_lang(), LANGUAGES["nl"]).get(key, key)
