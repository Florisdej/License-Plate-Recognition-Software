#!/usr/bin/env python3
"""
ALPR Systeem - Grafische Interface
====================================
Moderne GUI voor Automatic License Plate Recognition.
Gebouwd met CustomTkinter voor een professioneel donker thema.

Features:
  - Taalwisseling (NL / EN)
  - Voortgangsbalk tijdens scannen
  - Ontwikkelaarsmodus (dev console)

Gebruik:
    python gui.py
    python gui.py --model pad/naar/best.pt
"""

import sys
import os
import cv2
import time
import threading
import queue
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from PIL import Image, ImageTk, ImageDraw, ImageFont

import warnings
# Onderdruk specifieke PyTorch MPS warning op macOS
warnings.filterwarnings("ignore", message=".*pin_memory.*")

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk

# Voeg project root toe aan path
sys.path.insert(0, str(Path(__file__).parent))
import config
from translations import t, set_language, get_language, LANGUAGES

# ──────────────────────────────────────────────────────────────
#  Thema & Kleuren
# ──────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class Colors:
    """Centraal kleurenschema — donkergrijs / zwart thema."""
    BG_DARK       = "#0e0e0e"
    BG_MEDIUM     = "#181818"
    BG_LIGHT      = "#262626"
    BG_CARD       = "#2c2c2c"
    ACCENT        = "#d4d4d4"
    ACCENT_HOVER  = "#ffffff"
    SUCCESS       = "#4ade80"
    WARNING       = "#facc15"
    ERROR         = "#f87171"
    TEXT_PRIMARY   = "#e4e4e7"
    TEXT_SECONDARY = "#a1a1aa"
    TEXT_MUTED     = "#636366"
    BORDER         = "#303030"
    PLATE_BOX      = "#4ade80"
    PLATE_TEXT_BG  = "#4ade80"
    DEV_BG         = "#111111"
    DEV_BORDER     = "#2a2a2a"


# ──────────────────────────────────────────────────────────────
#  Hulpfuncties
# ──────────────────────────────────────────────────────────────

def cv2_to_pil(cv_image: np.ndarray) -> Image.Image:
    """Converteer OpenCV afbeelding (BGR) naar PIL Image (RGB)."""
    rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def fit_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    """Schaal afbeelding passend binnen max afmetingen met behoud van ratio."""
    ratio = min(max_width / image.width, max_height / image.height)
    if ratio >= 1:
        return image
    new_size = (int(image.width * ratio), int(image.height * ratio))
    return image.resize(new_size, Image.LANCZOS)


def draw_detections_on_pil(pil_image: Image.Image, results, scale: float = 1.0) -> Image.Image:
    """Teken bounding boxes en labels op een PIL image."""
    draw = ImageDraw.Draw(pil_image)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except (OSError, IOError):
        try:
            # macOS fallback
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
        except (OSError, IOError):
            font = ImageFont.load_default()
            font_small = font

    box_colors = {"BLUE": "#60a5fa", "YELLOW": "#facc15", "UNKNOWN": Colors.PLATE_BOX}

    for r in results:
        x1, y1, x2, y2 = [int(c * scale) for c in r.bbox]

        # Kleur op basis van classificatie
        plate_color = getattr(r, "plate_color", "UNKNOWN")
        box_color = box_colors.get(plate_color, Colors.PLATE_BOX)
        text_fill = "#000000"

        # Bounding box
        draw.rectangle([x1, y1, x2, y2], outline=box_color, width=3)

        # Label met kleur-indicator
        label = f" {r.plate_text}  [{plate_color}]  ({r.detection_confidence:.0%}) "
        bbox = font.getbbox(label)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        label_y = max(0, y1 - text_h - 8)
        draw.rectangle(
            [x1, label_y, x1 + text_w + 12, label_y + text_h + 8],
            fill=box_color,
        )
        draw.text((x1 + 6, label_y + 2), label, fill=text_fill, font=font)

    return pil_image


# ──────────────────────────────────────────────────────────────
#  Resultaat Card Widget
# ──────────────────────────────────────────────────────────────

class PlateCard(ctk.CTkFrame):
    """Kaartje dat één gedetecteerd kenteken toont."""

    def __init__(self, parent, plate_text: str, det_conf: float,
                 ocr_conf: float, thumbnail: Optional[Image.Image] = None,
                 timestamp: str = "", plate_color: str = "UNKNOWN", **kwargs):
        super().__init__(parent, fg_color=Colors.BG_CARD, corner_radius=10, **kwargs)

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        # Thumbnail
        if thumbnail:
            thumb = thumbnail.resize((90, 36), Image.LANCZOS)
            self._thumb_img = ctk.CTkImage(thumb, size=(90, 36))
            thumb_label = ctk.CTkLabel(self, image=self._thumb_img, text="")
            thumb_label.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=10)

        # Kenteken tekst (groot)
        plate_label = ctk.CTkLabel(
            self, text=plate_text,
            font=ctk.CTkFont(family="Courier", size=22, weight="bold"),
            text_color=Colors.SUCCESS,
        )
        plate_label.grid(row=0, column=1, sticky="sw", padx=4, pady=(10, 0))

        # Kleur badge
        color_map = {"BLUE": "#60a5fa", "YELLOW": "#facc15", "UNKNOWN": Colors.TEXT_MUTED}
        badge_color = color_map.get(plate_color, Colors.TEXT_MUTED)

        color_badge = ctk.CTkLabel(
            self, text=f" {plate_color} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#000000" if plate_color == "YELLOW" else "#ffffff",
            fg_color=badge_color, corner_radius=4,
        )
        color_badge.grid(row=0, column=2, sticky="se", padx=(4, 12), pady=(10, 0))

        # Confidence + timestamp
        conf_text = f"Det: {det_conf:.0%}   OCR: {ocr_conf:.0%}"
        if timestamp:
            conf_text += f"   •   {timestamp}"

        conf_label = ctk.CTkLabel(
            self, text=conf_text,
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY,
        )
        conf_label.grid(row=1, column=1, sticky="nw", padx=4, pady=(0, 10))


# ──────────────────────────────────────────────────────────────
#  Statistieken Widget
# ──────────────────────────────────────────────────────────────

class StatWidget(ctk.CTkFrame):
    """Klein statistiek-kaartje met waarde en label."""

    def __init__(self, parent, value: str, label: str,
                 value_color: str = Colors.ACCENT, **kwargs):
        super().__init__(parent, fg_color=Colors.BG_CARD, corner_radius=10, **kwargs)

        self._value_label = ctk.CTkLabel(
            self, text=value,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=value_color,
        )
        self._value_label.pack(pady=(12, 2))

        self._desc_label = ctk.CTkLabel(
            self, text=label,
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY,
        )
        self._desc_label.pack(pady=(0, 12))

    def set_value(self, value: str):
        self._value_label.configure(text=value)

    def set_label(self, label: str):
        self._desc_label.configure(text=label)


# ──────────────────────────────────────────────────────────────
#  Hoofdapplicatie
# ──────────────────────────────────────────────────────────────

class ALPRApp(ctk.CTk):
    """Hoofdvenster van de ALPR GUI-applicatie."""

    def __init__(self, model_path: Optional[str] = None):
        super().__init__()

        # Venster configuratie
        self.title(t("window_title"))
        self.geometry("1440x900")
        self.minsize(1024, 700)
        self.configure(fg_color=Colors.BG_DARK)

        # State
        self.pipeline = None
        self.model_path = model_path or str(config.MODEL_PATH)
        self.current_image = None       # Originele cv2 image
        self.current_pil = None         # Weergave PIL image
        self.current_results = []
        self.all_results_history = []   # Geschiedenis van alle detecties
        self.video_running = False
        self.video_paused = False
        self.video_cap = None
        self._after_id = None
        self._scan_cancelled = False
        self.dev_mode = config.DEV_MODE
        self._dev_log_entries = []      # Log berichten voor dev console

        # Thread-safe callback queue
        self._callback_queue = queue.Queue()

        # Layout
        self._build_layout()

        # Start polling voor thread-safe callbacks
        self._poll_callback_queue()

        # Bindings voor sneltoetsen
        self.bind("<space>", self._toggle_video_pause)
        self.bind("<Command-o>", lambda e: self._load_image())
        self.bind("<Control-o>", lambda e: self._load_image())

        # Start pipeline laden in achtergrond
        self._show_loading()
        threading.Thread(target=self._init_pipeline, daemon=True).start()

    def _toggle_video_pause(self, event=None):
        """Pauzeer/hervat video als de videopagina actief is."""
        if self.video_running and self.video_cap:
            self.video_paused = not self.video_paused
            if self.video_paused:
                if self._after_id:
                    self.after_cancel(self._after_id)
                    self._after_id = None
                self._dev_log("[Video] Gepauzeerd", "info")
            else:
                self._dev_log("[Video] Hervat", "info")
                self._process_video_frame()

    def _bind_scroll_events(self, scrollable_frame):
        """
        Forceer correcte scrollwerking op macOS door events te binden bij hover.
        Vermindert 'jank' door kleine events te accumuleren.
        """
        scrollable_frame._scroll_accumulator = 0

        def _on_mousewheel(event):
            try:
                # macOS gebruikt event.delta, Windows event.delta/120
                if sys.platform == "darwin":
                    # Accumuleer delta
                    scrollable_frame._scroll_accumulator += event.delta
                    
                    # Drempel: pas scrollen bij >= 4 accumulated units
                    threshold = 4
                    if abs(scrollable_frame._scroll_accumulator) >= threshold:
                        steps = -1 * (scrollable_frame._scroll_accumulator // threshold)
                        scrollable_frame._parent_canvas.yview_scroll(steps, "units")
                        scrollable_frame._scroll_accumulator %= threshold
                    return "break"
                else:
                    # Windows
                    delta = int(-1 * (event.delta / 120))
                    scrollable_frame._parent_canvas.yview_scroll(delta, "units")
                    return "break"
            except Exception:
                pass

        def _bind(event):
            scrollable_frame.bind_all("<MouseWheel>", _on_mousewheel)
            scrollable_frame.bind_all("<Button-4>", lambda e: scrollable_frame._parent_canvas.yview_scroll(-1, "units"))
            scrollable_frame.bind_all("<Button-5>", lambda e: scrollable_frame._parent_canvas.yview_scroll(1, "units"))

        def _unbind(event):
            scrollable_frame.unbind_all("<MouseWheel>")
            scrollable_frame.unbind_all("<Button-4>")
            scrollable_frame.unbind_all("<Button-5>")

        scrollable_frame.bind("<Enter>", _bind)
        scrollable_frame.bind("<Leave>", _unbind)

    def _schedule(self, callback):
        """Schedule een callback thread-safe op de main thread via de queue."""
        self._callback_queue.put(callback)

    def _poll_callback_queue(self):
        """Poll de callback queue en voer callbacks uit op de main thread."""
        try:
            while True:
                callback = self._callback_queue.get_nowait()
                try:
                    callback()
                except Exception as e:
                    import traceback
                    print(f"[GUI] Error in callback: {e}")
                    traceback.print_exc()
        except queue.Empty:
            pass
        # Plan volgende poll
        self.after(50, self._poll_callback_queue)

    # ──────────────────────────────────────────────────────
    #  Layout Builder
    # ──────────────────────────────────────────────────────

    def _build_layout(self):
        """Bouw de volledige GUI-layout."""

        # Grid configuratie — 3 rijen: sidebar+content | dev panel
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # dev panel

        # ─── Zijbalk (links) ───
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color=Colors.BG_MEDIUM,
                                     corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        # ─── Hoofd content (rechts) ───
        self.main_frame = ctk.CTkFrame(self, fg_color=Colors.BG_DARK, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # Pagina's (frames die worden gewisseld)
        self.pages = {}
        self._build_image_page()
        self._build_video_page()
        self._build_settings_page()
        self._build_history_page()

        # Dev panel (onder de content)
        self._build_dev_panel()

        # Toon standaard de afbeeldingen-pagina
        self._show_page("image")

    def _build_sidebar(self):
        """Bouw de navigatie-zijbalk."""

        # Logo / titel
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(24, 8))

        ctk.CTkLabel(
            logo_frame, text=t("app_title"),
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=Colors.ACCENT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            logo_frame, text=t("app_subtitle"),
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY,
        ).pack(anchor="w")

        # Scheidingslijn
        ctk.CTkFrame(self.sidebar, height=1, fg_color=Colors.BORDER).pack(
            fill="x", padx=16, pady=(16, 8)
        )

        # Navigatie label
        ctk.CTkLabel(
            self.sidebar, text=t("nav_label"),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=Colors.TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(12, 4))

        # Nav knoppen
        self.nav_buttons = {}
        nav_items = [
            ("image",    "nav_images"),
            ("video",    "nav_video"),
            ("history",  "nav_history"),
            ("settings", "nav_settings"),
        ]

        for page_id, t_key in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=f"  {t(t_key)}", anchor="w",
                font=ctk.CTkFont(size=13),
                fg_color="transparent", text_color=Colors.TEXT_PRIMARY,
                hover_color=Colors.BG_LIGHT, height=40,
                corner_radius=8,
                command=lambda pid=page_id: self._show_page(pid),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[page_id] = btn

        # Spacer
        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Dev mode snelknop
        self.sidebar_dev_btn = ctk.CTkButton(
            self.sidebar, text="DEV", anchor="center",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=Colors.BG_LIGHT if not self.dev_mode else Colors.WARNING,
            text_color=Colors.TEXT_MUTED if not self.dev_mode else "#000000",
            hover_color=Colors.BG_CARD, height=28, width=60,
            corner_radius=6,
            command=self._toggle_dev_mode,
        )
        self.sidebar_dev_btn.pack(padx=12, pady=(0, 8))

        # Status indicator onderin
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color=Colors.BG_LIGHT,
                                          corner_radius=10)
        self.status_frame.pack(fill="x", padx=12, pady=(0, 16))

        self.status_dot = ctk.CTkLabel(
            self.status_frame, text="●",
            font=ctk.CTkFont(size=10),
            text_color=Colors.WARNING,
        )
        self.status_dot.pack(side="left", padx=(12, 6), pady=10)

        self.status_label = ctk.CTkLabel(
            self.status_frame, text=t("status_loading"),
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY,
        )
        self.status_label.pack(side="left", pady=10)

        # Model pad onderin
        model_name = Path(self.model_path).name
        ctk.CTkLabel(
            self.sidebar, text=f"{t('model_label')}: {model_name}",
            font=ctk.CTkFont(size=10),
            text_color=Colors.TEXT_MUTED,
        ).pack(padx=16, pady=(0, 12))

    # ──────────────────────────────────────────────────────
    #  Pagina: Afbeeldingen
    # ──────────────────────────────────────────────────────

    def _build_image_page(self):
        """Bouw de afbeeldingen-verwerkingspagina."""
        page = ctk.CTkFrame(self.main_frame, fg_color=Colors.BG_DARK)
        self.pages["image"] = page

        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(2, weight=1)  # row 0=toolbar, 1=progress, 2=content

        # ─── Toolbar bovenaan ───
        toolbar = ctk.CTkFrame(page, fg_color=Colors.BG_MEDIUM, height=56,
                                corner_radius=0)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.grid_propagate(False)

        ctk.CTkLabel(
            toolbar, text=f"  {t('images_title')}",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left", padx=16)

        # Knoppen rechts in toolbar
        self.btn_stop_scan = ctk.CTkButton(
            toolbar, text=t("btn_stop"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Colors.ERROR, hover_color="#fca5a5",
            width=80, height=34, corner_radius=8,
            command=self._stop_scan,
        )
        # Stop-knop wordt pas getoond tijdens scannen

        self.btn_process_img = ctk.CTkButton(
            toolbar, text=t("btn_analyze"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
            width=120, height=34, corner_radius=8,
            command=self._process_current_image,
            state="disabled",
        )
        self.btn_process_img.pack(side="right", padx=(4, 16), pady=11)

        self.btn_load_dir = ctk.CTkButton(
            toolbar, text=t("btn_open_dir"),
            font=ctk.CTkFont(size=13),
            fg_color=Colors.BG_LIGHT, hover_color=Colors.BG_CARD,
            width=100, height=34, corner_radius=8,
            command=self._load_image_dir,
        )
        self.btn_load_dir.pack(side="right", padx=4, pady=11)

        self.btn_load_img = ctk.CTkButton(
            toolbar, text=t("btn_open_file"),
            font=ctk.CTkFont(size=13),
            fg_color=Colors.BG_LIGHT, hover_color=Colors.BG_CARD,
            width=120, height=34, corner_radius=8,
            command=self._load_image,
        )
        self.btn_load_img.pack(side="right", padx=4, pady=11)

        # ─── Voortgangsbalk (verborgen, verschijnt tijdens scan) ───
        self.progress_frame = ctk.CTkFrame(page, fg_color=Colors.BG_MEDIUM,
                                            height=40, corner_radius=0)
        # Initieel verborgen — wordt getoond via grid() tijdens scan

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame,
            mode="indeterminate",
            height=6,
            fg_color=Colors.BG_CARD,
            progress_color=Colors.SUCCESS,
            corner_radius=3,
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(16, 8), pady=12)

        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text=t("progress_detecting"),
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY,
            width=200,
        )
        self.progress_label.pack(side="right", padx=(0, 16), pady=12)

        # ─── Canvas (midden) ───
        canvas_frame = ctk.CTkFrame(page, fg_color=Colors.BG_DARK)
        canvas_frame.grid(row=2, column=0, sticky="nsew", padx=(12, 6), pady=12)
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(0, weight=1)

        self.image_canvas = tk.Canvas(
            canvas_frame, bg=Colors.BG_MEDIUM, highlightthickness=0,
            cursor="crosshair",
        )
        self.image_canvas.grid(row=0, column=0, sticky="nsew")
        self.image_canvas.bind("<Configure>", self._on_canvas_resize)

        # Placeholder tekst op canvas
        self._draw_placeholder(t("placeholder_image"))

        # Drag & drop binding
        self.image_canvas.drop_target_register = lambda *a: None  # Fallback
        try:
            self.image_canvas.drop_target_register("DND_Files")
            self.image_canvas.dnd_bind("<<Drop>>", self._on_drop_image)
        except Exception:
            pass  # tkdnd niet beschikbaar

        # ─── Resultaten paneel (rechts) ───
        results_panel = ctk.CTkFrame(page, fg_color=Colors.BG_MEDIUM,
                                      width=320, corner_radius=12)
        results_panel.grid(row=2, column=1, sticky="nsew", padx=(6, 12), pady=12)
        results_panel.grid_propagate(False)
        results_panel.grid_columnconfigure(0, weight=1)
        results_panel.grid_rowconfigure(2, weight=1)

        # Header
        ctk.CTkLabel(
            results_panel, text=t("results_title"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))

        # Stats rij
        stats_frame = ctk.CTkFrame(results_panel, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.stat_detected = StatWidget(stats_frame, "0", t("stat_found"),
                                         value_color=Colors.SUCCESS)
        self.stat_detected.grid(row=0, column=0, padx=3, sticky="ew")

        self.stat_time = StatWidget(stats_frame, "-", t("stat_time"),
                                     value_color=Colors.ACCENT)
        self.stat_time.grid(row=0, column=1, padx=3, sticky="ew")

        self.stat_conf = StatWidget(stats_frame, "-", t("stat_confidence"),
                                     value_color=Colors.WARNING)
        self.stat_conf.grid(row=0, column=2, padx=3, sticky="ew")

        # Scrollbare kaartjes lijst
        self.results_scroll = ctk.CTkScrollableFrame(
            results_panel, fg_color="transparent",
            scrollbar_button_color=Colors.BG_LIGHT,
        )
        self.results_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 12))
        self._bind_scroll_events(self.results_scroll)
        self.results_scroll.grid_columnconfigure(0, weight=1)

        # Placeholder bij geen resultaten
        self.no_results_label = ctk.CTkLabel(
            self.results_scroll,
            text=t("no_results"),
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_MUTED,
            justify="center",
        )
        self.no_results_label.pack(pady=40)

    # ──────────────────────────────────────────────────────
    #  Pagina: Video / Camera
    # ──────────────────────────────────────────────────────

    def _build_video_page(self):
        """Bouw de video/camera-pagina."""
        page = ctk.CTkFrame(self.main_frame, fg_color=Colors.BG_DARK)
        self.pages["video"] = page

        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(1, weight=1)

        # ─── Toolbar ───
        toolbar = ctk.CTkFrame(page, fg_color=Colors.BG_MEDIUM, height=56,
                                corner_radius=0)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.grid_propagate(False)

        ctk.CTkLabel(
            toolbar, text=f"  {t('video_title')}",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left", padx=16)

        self.btn_stop_video = ctk.CTkButton(
            toolbar, text=t("btn_stop_video"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Colors.ERROR, hover_color="#fca5a5",
            width=80, height=34, corner_radius=8,
            command=self._stop_video,
            state="disabled",
        )
        self.btn_stop_video.pack(side="right", padx=(4, 16), pady=11)

        self.btn_camera = ctk.CTkButton(
            toolbar, text=t("btn_start_camera"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Colors.SUCCESS, hover_color="#86efac",
            text_color="#0e0e0e",
            width=120, height=34, corner_radius=8,
            command=self._start_camera,
        )
        self.btn_camera.pack(side="right", padx=4, pady=11)

        self.btn_load_video = ctk.CTkButton(
            toolbar, text=t("btn_open_video"),
            font=ctk.CTkFont(size=13),
            fg_color=Colors.BG_LIGHT, hover_color=Colors.BG_CARD,
            width=110, height=34, corner_radius=8,
            command=self._load_video,
        )
        self.btn_load_video.pack(side="right", padx=4, pady=11)

        # ─── Video Canvas ───
        video_canvas_frame = ctk.CTkFrame(page, fg_color=Colors.BG_DARK)
        video_canvas_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=12)
        video_canvas_frame.grid_columnconfigure(0, weight=1)
        video_canvas_frame.grid_rowconfigure(0, weight=1)

        self.video_canvas = tk.Canvas(
            video_canvas_frame, bg=Colors.BG_MEDIUM, highlightthickness=0,
        )
        self.video_canvas.grid(row=0, column=0, sticky="nsew")

        # Video placeholder
        self.video_canvas.create_text(
            400, 300,
            text=t("placeholder_video"),
            fill=Colors.TEXT_MUTED, font=("Helvetica", 14),
            tags="placeholder",
        )

        # ─── Video resultaten paneel ───
        video_results = ctk.CTkFrame(page, fg_color=Colors.BG_MEDIUM,
                                      width=320, corner_radius=12)
        video_results.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=12)
        video_results.grid_propagate(False)
        video_results.grid_columnconfigure(0, weight=1)
        video_results.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            video_results, text=t("live_detection"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))

        # Video stats
        vid_stats = ctk.CTkFrame(video_results, fg_color="transparent")
        vid_stats.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
        vid_stats.grid_columnconfigure((0, 1), weight=1)

        self.vid_stat_fps = StatWidget(vid_stats, "-", t("stat_fps"),
                                        value_color=Colors.ACCENT)
        self.vid_stat_fps.grid(row=0, column=0, padx=3, sticky="ew")

        self.vid_stat_plates = StatWidget(vid_stats, "0", t("stat_unique"),
                                           value_color=Colors.SUCCESS)
        self.vid_stat_plates.grid(row=0, column=1, padx=3, sticky="ew")

        # Frame skip slider
        skip_frame = ctk.CTkFrame(video_results, fg_color="transparent")
        skip_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 0))

        ctk.CTkLabel(
            skip_frame, text=t("frame_skip"),
            font=ctk.CTkFont(size=11),
            text_color=Colors.TEXT_SECONDARY,
        ).pack(side="left")

        self.vid_skip_label = ctk.CTkLabel(
            skip_frame, text=str(config.VIDEO_FRAME_SKIP),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=Colors.ACCENT,
        )
        self.vid_skip_label.pack(side="right")

        self.vid_skip_slider = ctk.CTkSlider(
            video_results, from_=1, to=10, number_of_steps=9,
            fg_color=Colors.BG_CARD, progress_color=Colors.ACCENT,
            button_color=Colors.ACCENT, button_hover_color=Colors.ACCENT_HOVER,
            command=self._on_frame_skip_change,
        )
        self.vid_skip_slider.set(config.VIDEO_FRAME_SKIP)
        self.vid_skip_slider.grid(row=3, column=0, sticky="ew", padx=16, pady=(2, 8))

        # Scrollbare lijst van video-detecties
        self.video_results_scroll = ctk.CTkScrollableFrame(
            video_results, fg_color="transparent",
            scrollbar_button_color=Colors.BG_LIGHT,
        )
        self._bind_scroll_events(self.video_results_scroll)
        self.video_results_scroll.grid(row=4, column=0, sticky="nsew",
                                        padx=8, pady=(4, 12))
        video_results.grid_rowconfigure(4, weight=1)

        self.video_plates_found = set()

    # ──────────────────────────────────────────────────────
    #  Pagina: Instellingen
    # ──────────────────────────────────────────────────────

    def _build_settings_page(self):
        """Bouw de instellingen-pagina."""
        page = ctk.CTkFrame(self.main_frame, fg_color=Colors.BG_DARK)
        self.pages["settings"] = page
        page.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(page, fg_color=Colors.BG_MEDIUM, height=56,
                                corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)

        ctk.CTkLabel(
            toolbar, text=f"  {t('settings_title')}",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left", padx=16)

        # Scrollbaar instellingenpaneel
        settings_scroll = ctk.CTkScrollableFrame(
            page, fg_color=Colors.BG_DARK,
            scrollbar_button_color=Colors.BG_LIGHT,
        )
        settings_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        settings_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        page.grid_rowconfigure(1, weight=1)
        settings_scroll.grid_columnconfigure(0, weight=1)
        
        # FIX: Forceer scrolling binding
        self._bind_scroll_events(settings_scroll)

        row = 0

        # ─── Sectie: Model ───
        row = self._settings_section(settings_scroll, t("section_model"), row)

        model_frame = ctk.CTkFrame(settings_scroll, fg_color="transparent")
        model_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        model_frame.grid_columnconfigure(0, weight=1)

        self.model_path_var = ctk.StringVar(value=self.model_path)
        ctk.CTkEntry(
            model_frame, textvariable=self.model_path_var,
            font=ctk.CTkFont(size=12),
            fg_color=Colors.BG_CARD, border_color=Colors.BORDER,
            text_color=Colors.TEXT_PRIMARY,
            height=36,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            model_frame, text=t("btn_browse"),
            font=ctk.CTkFont(size=12),
            fg_color=Colors.BG_LIGHT, hover_color=Colors.BG_CARD,
            width=90, height=36, corner_radius=8,
            command=self._browse_model,
        ).grid(row=0, column=1)
        row += 1

        # Herlaad knop
        ctk.CTkButton(
            settings_scroll, text=t("btn_reload_model"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
            width=160, height=38, corner_radius=8,
            command=self._reload_model,
        ).grid(row=row, column=0, sticky="w", padx=20, pady=(12, 8))
        row += 1

        # ─── Sectie: Detectie ───
        row = self._settings_section(settings_scroll, t("section_detection"), row)

        row = self._settings_slider(
            settings_scroll, t("conf_threshold"),
            t("conf_threshold_desc"),
            0.1, 0.95, config.DETECTION_CONFIDENCE, row,
            var_name="conf_threshold",
        )

        row = self._settings_slider(
            settings_scroll, t("iou_threshold"),
            t("iou_threshold_desc"),
            0.1, 0.9, config.DETECTION_IOU, row,
            var_name="iou_threshold",
        )

        # ─── Sectie: Preprocessing ───
        row = self._settings_section(settings_scroll, t("section_preprocessing"), row)

        self.preprocess_vars = {}
        prep_steps = [
            ("resize",    "prep_resize"),
            ("grayscale", "prep_grayscale"),
            ("denoise",   "prep_denoise"),
            ("contrast",  "prep_contrast"),
            ("sharpen",   "prep_sharpen"),
            ("binarize",  "prep_binarize"),
        ]
        for step_name, t_key in prep_steps:
            var = ctk.BooleanVar(value=config.PREPROCESSING.get(step_name, True))
            self.preprocess_vars[step_name] = var

            cb = ctk.CTkCheckBox(
                settings_scroll, text=f"  {t(t_key)}",
                variable=var,
                font=ctk.CTkFont(size=13),
                text_color=Colors.TEXT_PRIMARY,
                fg_color=Colors.ACCENT,
                hover_color=Colors.ACCENT_HOVER,
                checkmark_color="#ffffff",
                command=self._apply_settings,
            )
            cb.grid(row=row, column=0, sticky="w", padx=20, pady=4)
            row += 1

        row = self._settings_slider(
            settings_scroll, t("denoise_strength"),
            t("denoise_strength_desc"),
            1, 30, config.DENOISE_STRENGTH, row,
            var_name="denoise_strength", is_int=True,
        )

        # ─── Sectie: OCR ───
        row = self._settings_section(settings_scroll, t("section_ocr"), row)

        row = self._settings_slider(
            settings_scroll, t("ocr_conf_min"),
            t("ocr_conf_min_desc"),
            0.05, 0.8, config.OCR_CONFIDENCE_MIN, row,
            var_name="ocr_conf_min",
        )

        # ─── Sectie: Kleurfilter ───
        row = self._settings_section(settings_scroll, t("section_colorfilter"), row)

        self.color_filter_var = ctk.BooleanVar(value=config.COLOR_FILTER_ENABLED)
        cb_color = ctk.CTkCheckBox(
            settings_scroll, text=f"  {t('colorfilter_enable')}",
            variable=self.color_filter_var,
            font=ctk.CTkFont(size=13),
            text_color=Colors.TEXT_PRIMARY,
            fg_color=Colors.ACCENT,
            hover_color=Colors.ACCENT_HOVER,
            checkmark_color="#ffffff",
            command=self._apply_settings,
        )
        cb_color.grid(row=row, column=0, sticky="w", padx=20, pady=4)
        row += 1

        # Plate mode dropdown
        mode_frame = ctk.CTkFrame(settings_scroll, fg_color="transparent")
        mode_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=6)

        ctk.CTkLabel(
            mode_frame, text=t("plate_mode_label"),
            font=ctk.CTkFont(size=13),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left")

        self.plate_mode_var = ctk.StringVar(value=config.PLATE_MODE)
        self.plate_mode_menu = ctk.CTkOptionMenu(
            mode_frame, values=["blue", "yellow", "all"],
            variable=self.plate_mode_var,
            font=ctk.CTkFont(size=12),
            fg_color=Colors.BG_CARD, button_color=Colors.BG_LIGHT,
            button_hover_color=Colors.ACCENT,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_LIGHT,
            text_color=Colors.TEXT_PRIMARY,
            width=120,
            command=lambda _: self._apply_settings(),
        )
        self.plate_mode_menu.pack(side="right")
        row += 1

        # Vehicle mode dropdown
        vehicle_frame = ctk.CTkFrame(settings_scroll, fg_color="transparent")
        vehicle_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=6)

        ctk.CTkLabel(
            vehicle_frame, text=t("vehicle_mode_label"),
            font=ctk.CTkFont(size=13),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left")

        # Map display value to stored value
        self.vehicle_map = {
            t("option_car"): "car",
            t("option_scooter"): "scooter",
            t("option_both"): "both"
        }
        rev_map = {v: k for k, v in self.vehicle_map.items()}
        current_display = rev_map.get(config.VEHICLE_MODE, t("option_both"))

        self.vehicle_mode_var = ctk.StringVar(value=current_display)

        def _on_vehicle_change(val):
            code = self.vehicle_map.get(val, "both")
            config.VEHICLE_MODE = code
            self._apply_settings()

        self.vehicle_mode_menu = ctk.CTkOptionMenu(
            vehicle_frame, values=[t("option_both"), t("option_car"), t("option_scooter")],
            variable=self.vehicle_mode_var,
            font=ctk.CTkFont(size=12),
            fg_color=Colors.BG_CARD, button_color=Colors.BG_LIGHT,
            button_hover_color=Colors.ACCENT,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_LIGHT,
            text_color=Colors.TEXT_PRIMARY,
            width=160,
            command=_on_vehicle_change,
        )
        self.vehicle_mode_menu.pack(side="right")
        row += 1

        row = self._settings_slider(
            settings_scroll, t("color_threshold"),
            t("color_threshold_desc"),
            0.05, 0.6, config.COLOR_THRESHOLD, row,
            var_name="color_threshold",
        )

        # ─── Sectie: Taal ───
        row = self._settings_section(settings_scroll, t("section_language"), row)

        lang_frame = ctk.CTkFrame(settings_scroll, fg_color="transparent")
        lang_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=6)

        ctk.CTkLabel(
            lang_frame, text=t("language_label"),
            font=ctk.CTkFont(size=13),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left")

        lang_names = [LANGUAGES[code]["name"] for code in LANGUAGES]
        lang_codes = list(LANGUAGES.keys())
        current_name = LANGUAGES[get_language()]["name"]

        self.lang_var = ctk.StringVar(value=current_name)
        self.lang_menu = ctk.CTkOptionMenu(
            lang_frame, values=lang_names,
            variable=self.lang_var,
            font=ctk.CTkFont(size=12),
            fg_color=Colors.BG_CARD, button_color=Colors.BG_LIGHT,
            button_hover_color=Colors.ACCENT,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_hover_color=Colors.BG_LIGHT,
            text_color=Colors.TEXT_PRIMARY,
            width=160,
            command=self._on_language_change,
        )
        self.lang_menu.pack(side="right")
        row += 1

        # ─── Sectie: Dev Mode ───
        row = self._settings_section(settings_scroll, t("section_devmode"), row)

        self.dev_mode_var = ctk.BooleanVar(value=self.dev_mode)
        cb_dev = ctk.CTkCheckBox(
            settings_scroll, text=f"  {t('dev_mode_label')}",
            variable=self.dev_mode_var,
            font=ctk.CTkFont(size=13),
            text_color=Colors.TEXT_PRIMARY,
            fg_color=Colors.WARNING,
            hover_color=Colors.ACCENT_HOVER,
            checkmark_color="#000000",
            command=self._toggle_dev_mode_from_settings,
        )
        cb_dev.grid(row=row, column=0, sticky="w", padx=20, pady=4)
        row += 1

        ctk.CTkLabel(
            settings_scroll, text=t("dev_mode_desc"),
            font=ctk.CTkFont(size=10),
            text_color=Colors.TEXT_MUTED,
        ).grid(row=row, column=0, sticky="w", padx=28, pady=(0, 16))

    def _settings_section(self, parent, title: str, row: int) -> int:
        """Voeg een sectie-header toe aan instellingen."""
        ctk.CTkLabel(
            parent, text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=Colors.ACCENT,
        ).grid(row=row, column=0, sticky="w", padx=16, pady=(20, 8))
        return row + 1

    def _settings_slider(self, parent, label: str, description: str,
                          from_: float, to: float, default: float,
                          row: int, var_name: str, is_int: bool = False) -> int:
        """Voeg een slider-instelling toe."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=16, pady=6)
        frame.grid_columnconfigure(0, weight=1)

        # Label + waarde
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=label,
            font=ctk.CTkFont(size=13),
            text_color=Colors.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        fmt = "{:.0f}" if is_int else "{:.2f}"
        value_label = ctk.CTkLabel(
            header, text=fmt.format(default),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Colors.ACCENT,
        )
        value_label.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            frame, text=description,
            font=ctk.CTkFont(size=10),
            text_color=Colors.TEXT_MUTED,
        ).pack(anchor="w")

        # Slider
        def on_change(val):
            value_label.configure(text=fmt.format(val))
            self._apply_settings()

        steps = int((to - from_) * (1 if is_int else 20))
        slider = ctk.CTkSlider(
            frame, from_=from_, to=to, number_of_steps=max(steps, 2),
            fg_color=Colors.BG_CARD, progress_color=Colors.ACCENT,
            button_color=Colors.ACCENT, button_hover_color=Colors.ACCENT_HOVER,
            command=on_change,
        )
        slider.set(default)
        slider.pack(fill="x", pady=(4, 0))

        # Sla op als attribuut
        setattr(self, f"slider_{var_name}", slider)

        return row + 1

    # ──────────────────────────────────────────────────────
    #  Pagina: Geschiedenis
    # ──────────────────────────────────────────────────────

    def _build_history_page(self):
        """Bouw de geschiedenis-pagina."""
        page = ctk.CTkFrame(self.main_frame, fg_color=Colors.BG_DARK)
        self.pages["history"] = page
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(page, fg_color=Colors.BG_MEDIUM, height=56,
                                corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)

        ctk.CTkLabel(
            toolbar, text=f"  {t('history_title')}",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left", padx=16)

        ctk.CTkButton(
            toolbar, text=t("btn_export_csv"),
            font=ctk.CTkFont(size=13),
            fg_color=Colors.BG_LIGHT, hover_color=Colors.BG_CARD,
            width=120, height=34, corner_radius=8,
            command=self._export_history_csv,
        ).pack(side="right", padx=16, pady=11)

        ctk.CTkButton(
            toolbar, text=t("btn_clear_history"),
            font=ctk.CTkFont(size=13),
            fg_color=Colors.BG_LIGHT, hover_color=Colors.ERROR,
            width=140, height=34, corner_radius=8,
            command=self._clear_history,
        ).pack(side="right", padx=4, pady=11)

        # Scrollbare lijst
        self.history_scroll = ctk.CTkScrollableFrame(
            page, fg_color=Colors.BG_DARK,
            scrollbar_button_color=Colors.BG_LIGHT,
        )
        self.history_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self._bind_scroll_events(self.history_scroll)
        self.history_scroll.grid_columnconfigure(0, weight=1)

        self.history_empty_label = ctk.CTkLabel(
            self.history_scroll,
            text=t("history_empty"),
            font=ctk.CTkFont(size=13),
            text_color=Colors.TEXT_MUTED, justify="center",
        )
        self.history_empty_label.pack(pady=60)

    # ──────────────────────────────────────────────────────
    #  Dev Console Panel
    # ──────────────────────────────────────────────────────

    def _build_dev_panel(self):
        """Bouw het dev console paneel (onderaan het venster)."""
        self.dev_panel = ctk.CTkFrame(self, fg_color=Colors.DEV_BG,
                                       height=200, corner_radius=0)

        # Header balk
        dev_header = ctk.CTkFrame(self.dev_panel, fg_color=Colors.DEV_BORDER,
                                   height=32, corner_radius=0)
        dev_header.pack(fill="x")
        dev_header.pack_propagate(False)

        ctk.CTkLabel(
            dev_header, text=f"  {t('dev_console')}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Colors.WARNING,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            dev_header, text=t("dev_clear"),
            font=ctk.CTkFont(size=10),
            fg_color=Colors.BG_LIGHT, hover_color=Colors.BG_CARD,
            width=70, height=24, corner_radius=4,
            command=self._clear_dev_log,
        ).pack(side="right", padx=8, pady=4)

        # Log textbox
        self.dev_textbox = ctk.CTkTextbox(
            self.dev_panel,
            fg_color=Colors.DEV_BG,
            text_color=Colors.TEXT_SECONDARY,
            font=ctk.CTkFont(family="Courier", size=11),
            wrap="word",
            state="disabled",
            scrollbar_button_color=Colors.BG_LIGHT,
        )
        self.dev_textbox.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # Configureer kleurtags
        self.dev_textbox.tag_config("info", foreground=Colors.TEXT_SECONDARY)
        self.dev_textbox.tag_config("success", foreground=Colors.SUCCESS)
        self.dev_textbox.tag_config("warning", foreground=Colors.WARNING)
        self.dev_textbox.tag_config("error", foreground=Colors.ERROR)
        self.dev_textbox.tag_config("step", foreground="#60a5fa")
        self.dev_textbox.tag_config("timestamp", foreground=Colors.TEXT_MUTED)

        # Toon/verberg panel op basis van dev_mode
        if self.dev_mode:
            self.dev_panel.grid(row=1, column=1, sticky="ew")
        # Anders blijft het verborgen

    # ──────────────────────────────────────────────────────
    #  Pagina Navigatie
    # ──────────────────────────────────────────────────────

    def _show_page(self, page_id: str):
        """Wissel naar de opgegeven pagina."""
        # Stop video als we wegnavigeren
        if page_id != "video" and self.video_running:
            self._stop_video()

        # Verberg alle pagina's
        for pid, frame in self.pages.items():
            frame.grid_forget()

        # Toon de juiste pagina
        self.pages[page_id].grid(row=0, column=0, sticky="nsew")

        # Update nav button styling
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=Colors.BG_LIGHT, text_color=Colors.ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=Colors.TEXT_PRIMARY)

        # Refresh geschiedenis als die geopend wordt
        if page_id == "history":
            self._refresh_history()

    # ──────────────────────────────────────────────────────
    #  Taalwisseling
    # ──────────────────────────────────────────────────────

    def _on_language_change(self, selected_name: str):
        """Callback wanneer de taal wordt gewijzigd via dropdown."""
        # Zoek de taalcode op basis van de naam
        for code, lang_dict in LANGUAGES.items():
            if lang_dict["name"] == selected_name:
                if code != get_language():
                    self._change_language(code)
                break

    def _change_language(self, lang_code: str):
        """Wissel de taal en herbouw de GUI."""
        set_language(lang_code)

        # Bewaar state
        saved_image = self.current_image
        saved_results = self.current_results
        saved_history = self.all_results_history.copy()
        saved_pipeline = self.pipeline
        saved_model_path = self.model_path
        saved_dev_mode = self.dev_mode
        saved_dev_logs = self._dev_log_entries.copy()
        saved_video_running = self.video_running

        # Stop video als dat draait
        if self.video_running:
            self._stop_video()

        # Verwijder alle widgets
        for widget in self.winfo_children():
            widget.destroy()

        # Update venstertitel
        self.title(t("window_title"))

        # Herstel state
        self.pipeline = saved_pipeline
        self.current_image = saved_image
        self.current_results = saved_results
        self.all_results_history = saved_history
        self.model_path = saved_model_path
        self.dev_mode = saved_dev_mode
        self._dev_log_entries = saved_dev_logs
        self.video_running = False
        self.video_paused = False
        self.video_cap = None
        self._after_id = None
        self._scan_cancelled = False

        # Herbouw
        self._build_layout()

        # Herstel weergave
        if self.pipeline:
            self._on_pipeline_ready()

        if self.current_image is not None:
            self._update_image_canvas()
            if self.current_results:
                self._update_results_panel(self.current_results)

        # Herstel dev logs
        if saved_dev_logs:
            for entry in saved_dev_logs:
                self._append_dev_text(entry["msg"], entry["level"], entry["time"])

        self._show_page("settings")

    # ──────────────────────────────────────────────────────
    #  Dev Mode
    # ──────────────────────────────────────────────────────

    def _toggle_dev_mode(self):
        """Toggle dev mode aan/uit (vanuit sidebar knop)."""
        self.dev_mode = not self.dev_mode
        config.DEV_MODE = self.dev_mode
        self._update_dev_panel_visibility()

        # Update sidebar knop
        if self.dev_mode:
            self.sidebar_dev_btn.configure(
                fg_color=Colors.WARNING,
                text_color="#000000",
            )
        else:
            self.sidebar_dev_btn.configure(
                fg_color=Colors.BG_LIGHT,
                text_color=Colors.TEXT_MUTED,
            )

        # Sync settings checkbox
        if hasattr(self, "dev_mode_var"):
            self.dev_mode_var.set(self.dev_mode)

    def _toggle_dev_mode_from_settings(self):
        """Toggle dev mode vanuit de settings checkbox."""
        self.dev_mode = self.dev_mode_var.get()
        config.DEV_MODE = self.dev_mode
        self._update_dev_panel_visibility()

        # Update sidebar knop
        if self.dev_mode:
            self.sidebar_dev_btn.configure(
                fg_color=Colors.WARNING,
                text_color="#000000",
            )
        else:
            self.sidebar_dev_btn.configure(
                fg_color=Colors.BG_LIGHT,
                text_color=Colors.TEXT_MUTED,
            )

    def _update_dev_panel_visibility(self):
        """Toon of verberg het dev panel."""
        if self.dev_mode:
            self.dev_panel.grid(row=1, column=1, sticky="ew")
        else:
            self.dev_panel.grid_forget()

    def _dev_log(self, msg: str, level: str = "info"):
        """
        Voeg een bericht toe aan de dev console.
        Thread-safe: kan vanuit background threads aangeroepen worden.
        """
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = {"msg": msg, "level": level, "time": now}
        self._dev_log_entries.append(entry)

        # Beperk geheugengebruik
        if len(self._dev_log_entries) > 500:
            self._dev_log_entries = self._dev_log_entries[-300:]

        # Update GUI (thread-safe)
        try:
            self._schedule(lambda m=msg, l=level, n=now: self._append_dev_text(m, l, n))
        except Exception:
            pass

    def _append_dev_text(self, msg: str, level: str, timestamp: str):
        """Voeg tekst toe aan de dev textbox (moet op main thread)."""
        if not hasattr(self, "dev_textbox"):
            return
        try:
            self.dev_textbox.configure(state="normal")
            self.dev_textbox.insert("end", f"[{timestamp}] ", "timestamp")
            self.dev_textbox.insert("end", f"{msg}\n", level)
            self.dev_textbox.see("end")
            self.dev_textbox.configure(state="disabled")
        except Exception:
            pass

    def _clear_dev_log(self):
        """Wis de dev console."""
        self._dev_log_entries.clear()
        if hasattr(self, "dev_textbox"):
            self.dev_textbox.configure(state="normal")
            self.dev_textbox.delete("1.0", "end")
            self.dev_textbox.configure(state="disabled")

    # ──────────────────────────────────────────────────────
    #  Voortgangsbalk
    # ──────────────────────────────────────────────────────

    def _show_progress(self, step_key: str = "progress_detecting"):
        """Toon de voortgangsbalk met de opgegeven stap-tekst."""
        try:
            self.progress_label.configure(text=t(step_key))
            self.progress_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
            self.progress_bar.start()
        except Exception:
            pass

    def _update_progress_text(self, step_key: str):
        """Update alleen de tekst van de voortgangsbalk (thread-safe)."""
        try:
            self._schedule(lambda sk=step_key: self.progress_label.configure(text=t(sk)))
        except Exception:
            pass

    def _hide_progress(self):
        """Verberg de voortgangsbalk."""
        try:
            self.progress_bar.stop()
            self.progress_frame.grid_forget()
        except Exception:
            pass

    def _on_progress_callback(self, step_key: str):
        """Callback van pipeline voor voortgang (kan vanuit thread)."""
        self._update_progress_text(step_key)

    # ──────────────────────────────────────────────────────
    #  Pipeline Initialisatie
    # ──────────────────────────────────────────────────────

    def _show_loading(self):
        """Toon laad-indicator."""
        self.status_dot.configure(text_color=Colors.WARNING)
        self.status_label.configure(text=t("status_loading"))

    def _init_pipeline(self):
        """Initialiseer de ALPR pipeline (in achtergrondthread)."""
        try:
            from pipeline import ALPRPipeline
            self.pipeline = ALPRPipeline(
                self.model_path,
                log_callback=self._dev_log,
                progress_callback=self._on_progress_callback,
            )
            self._schedule(self._on_pipeline_ready)
        except Exception as e:
            self._schedule(lambda err=str(e): self._on_pipeline_error(err))

    def _on_pipeline_ready(self):
        """Callback wanneer pipeline geladen is."""
        self.status_dot.configure(text_color=Colors.SUCCESS)
        self.status_label.configure(text=t("status_ready"))
        self.btn_process_img.configure(state="normal")

    def _on_pipeline_error(self, error: str):
        """Callback bij pipeline-fout."""
        self.status_dot.configure(text_color=Colors.ERROR)
        self.status_label.configure(text=t("status_error"))
        messagebox.showerror(t("dialog_load_error_title"),
                              f"{t('dialog_pipeline_error')}\n\n{error}")

    # ──────────────────────────────────────────────────────
    #  Afbeelding Acties
    # ──────────────────────────────────────────────────────

    def _load_image(self):
        """Open een afbeeldingsbestand."""
        path = filedialog.askopenfilename(
            title=t("dialog_select_image"),
            filetypes=[
                (t("filetypes_images"), "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),
                (t("filetypes_all"), "*.*"),
            ],
        )
        if path:
            self._display_image(path)

    def _load_image_dir(self):
        """Open alle afbeeldingen in een map."""
        dir_path = filedialog.askdirectory(title=t("dialog_select_dir"))
        if not dir_path:
            return

        extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
        images = sorted([
            str(f) for f in Path(dir_path).iterdir()
            if f.suffix.lower() in extensions
        ])

        if not images:
            messagebox.showinfo(t("dialog_no_data_title"),
                                 t("dialog_no_images"))
            return

        # Verwerk alle afbeeldingen
        self._batch_process(images)

    def _on_drop_image(self, event):
        """Verwerk drag & drop van een afbeelding."""
        path = event.data.strip().strip("{}")
        if path and Path(path).exists():
            self._display_image(path)

    def _display_image(self, path: str):
        """Laad en toon een afbeelding op het canvas."""
        self.current_image = cv2.imread(path)
        if self.current_image is None:
            messagebox.showerror(t("dialog_error_title"),
                                  f"{t('dialog_load_error')}\n{path}")
            return

        self.current_results = []
        self._update_image_canvas()
        self._update_results_panel([])
        self.btn_process_img.configure(state="normal")
        self._dev_log(f"[GUI] Afbeelding geladen: {path}", "info")

    def _update_image_canvas(self):
        """Update het canvas met de huidige afbeelding en resultaten."""
        if self.current_image is None:
            return

        canvas_w = self.image_canvas.winfo_width()
        canvas_h = self.image_canvas.winfo_height()

        if canvas_w <= 1 or canvas_h <= 1:
            return

        # Converteer en schaal
        pil_img = cv2_to_pil(self.current_image)
        display_img = fit_image(pil_img, canvas_w - 20, canvas_h - 20)

        # Bereken schaal voor bounding boxes
        scale_x = display_img.width / pil_img.width
        scale_y = display_img.height / pil_img.height
        scale = min(scale_x, scale_y)

        # Teken detecties
        if self.current_results:
            display_img = draw_detections_on_pil(display_img, self.current_results, scale)

        # Toon op canvas
        self._canvas_image = ImageTk.PhotoImage(display_img)
        self.image_canvas.delete("all")
        x = canvas_w // 2
        y = canvas_h // 2
        self.image_canvas.create_image(x, y, image=self._canvas_image, anchor="center")

    def _on_canvas_resize(self, event):
        """Herteken bij resize."""
        if self.current_image is not None:
            self._update_image_canvas()
        else:
            self._draw_placeholder(t("placeholder_image"))

    def _draw_placeholder(self, text: str):
        """Teken placeholder tekst op het canvas."""
        self.image_canvas.delete("all")
        w = self.image_canvas.winfo_width()
        h = self.image_canvas.winfo_height()
        if w > 1 and h > 1:
            # Primaire tekst
            self.image_canvas.create_text(
                w // 2, h // 2 - 15,
                text=text, fill=Colors.TEXT_PRIMARY,
                font=("Helvetica", 16, "bold"), justify="center",
            )
            # Subtekst (hint)
            self.image_canvas.create_text(
                w // 2, h // 2 + 15,
                text=t("drag_drop_hint"), fill=Colors.TEXT_MUTED,
                font=("Helvetica", 12), justify="center",
            )

    def _process_current_image(self):
        """Verwerk de huidige afbeelding via de pipeline."""
        if self.current_image is None or self.pipeline is None:
            return

        self._scan_cancelled = False
        self.btn_process_img.pack_forget()
        self.btn_stop_scan.pack(side="right", padx=(4, 16), pady=11)
        self._show_progress("progress_detecting")
        self._dev_log("[GUI] Scan gestart...", "step")
        self.update_idletasks()

        def process():
            try:
                start = time.time()
                results = self.pipeline.process_frame_array(self.current_image)
                elapsed = time.time() - start
                self._schedule(lambda r=results, e=elapsed: self._on_image_processed(r, e))
            except Exception as ex:
                self._schedule(lambda err=str(ex): self._on_scan_error(err))

        threading.Thread(target=process, daemon=True).start()

    def _stop_scan(self):
        """Annuleer de huidige scan."""
        self._scan_cancelled = True
        self._reset_scan_buttons()
        self._hide_progress()
        self._dev_log("[GUI] Scan geannuleerd door gebruiker", "warning")

    def _reset_scan_buttons(self):
        """Herstel de toolbar knoppen na scan."""
        self.btn_stop_scan.pack_forget()
        self.btn_process_img.pack(side="right", padx=(4, 16), pady=11)
        self.btn_process_img.configure(state="normal", text=t("btn_analyze"))

    def _on_scan_error(self, error: str):
        """Callback bij verwerkingsfout."""
        self._reset_scan_buttons()
        self._hide_progress()
        self._dev_log(f"[GUI] FOUT bij verwerking: {error}", "error")
        messagebox.showerror(t("dialog_scan_error_title"),
                              f"{t('dialog_scan_error')}\n\n{error}")

    def _on_image_processed(self, results, elapsed: float):
        """Callback na verwerking."""
        # Als de scan is geannuleerd, negeer het resultaat
        if self._scan_cancelled:
            self._reset_scan_buttons()
            self._hide_progress()
            return

        self._reset_scan_buttons()
        self._hide_progress()
        self.current_results = results
        self._update_image_canvas()
        self._update_results_panel(results, elapsed)

        self._dev_log(f"[GUI] Scan klaar: {len(results)} resultaten in {elapsed*1000:.0f}ms", "success")

        # Voeg toe aan geschiedenis
        for r in results:
            self.all_results_history.append({
                "plate": r.plate_text,
                "det_conf": r.detection_confidence,
                "ocr_conf": r.ocr_confidence,
                "color": getattr(r, "plate_color", "UNKNOWN"),
                "time": datetime.now().strftime("%H:%M:%S"),
                "source": t("source_image"),
            })

    def _batch_process(self, image_paths: list):
        """Verwerk meerdere afbeeldingen achter elkaar."""
        if not self.pipeline:
            return

        self._show_progress("progress_detecting")

        def process():
            for i, path in enumerate(image_paths):
                img = cv2.imread(path)
                if img is None:
                    continue

                self._schedule(lambda im=img: setattr(self, 'current_image', im))
                self._schedule(self._update_image_canvas)

                start = time.time()
                results = self.pipeline.process_frame_array(img)
                elapsed = time.time() - start

                self._schedule(lambda r=results, e=elapsed: self._on_image_processed(r, e))
                time.sleep(0.1)

            self._schedule(self._hide_progress)

        self.btn_process_img.configure(state="disabled", text=f"0/{len(image_paths)}")
        threading.Thread(target=process, daemon=True).start()

    def _update_results_panel(self, results, elapsed: float = 0):
        """Update het resultaten-paneel met nieuwe detecties."""
        # Update stats
        self.stat_detected.set_value(str(len(results)))
        self.stat_time.set_value(f"{elapsed*1000:.0f}" if elapsed > 0 else "-")

        if results:
            avg_conf = sum(r.detection_confidence for r in results) / len(results)
            self.stat_conf.set_value(f"{avg_conf:.0%}")
        else:
            self.stat_conf.set_value("-")

        # Verwijder oude kaartjes
        for widget in self.results_scroll.winfo_children():
            widget.destroy()

        if not results:
            label = ctk.CTkLabel(
                self.results_scroll,
                text=t("no_results_found"),
                font=ctk.CTkFont(size=12),
                text_color=Colors.TEXT_MUTED, justify="center",
            )
            label.pack(pady=40)
            return

        # Maak kaartjes voor elk resultaat
        for r in results:
            thumb = cv2_to_pil(r.cropped_image) if r.cropped_image is not None else None
            card = PlateCard(
                self.results_scroll,
                plate_text=r.plate_text,
                det_conf=r.detection_confidence,
                ocr_conf=r.ocr_confidence,
                thumbnail=thumb,
                timestamp=datetime.now().strftime("%H:%M:%S"),
                plate_color=getattr(r, "plate_color", "UNKNOWN"),
            )
            card.pack(fill="x", padx=4, pady=4)

    # ──────────────────────────────────────────────────────
    #  Video / Camera Acties
    # ──────────────────────────────────────────────────────

    def _load_video(self):
        """Open een videobestand."""
        path = filedialog.askopenfilename(
            title=t("dialog_select_video"),
            filetypes=[
                (t("filetypes_video"), "*.mp4 *.avi *.mkv *.mov *.wmv"),
                (t("filetypes_all"), "*.*"),
            ],
        )
        if path:
            self._start_video_source(path)

    def _start_camera(self):
        """Start live camera feed. (Slim zoeken naar werkende camera)"""
        self._dev_log("[Camera] Zoeken naar werkende camera...", "info")
        best_cam = 0
        
        # Op Mac kunnen camera 0 of 1 virtueel zijn of Continuity Camera's die falen
        for i in range(3):
            try:
                if sys.platform == "darwin":
                    cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
                else:
                    cap = cv2.VideoCapture(i)
                    
                if cap.isOpened():
                    # Warmup probeer 5 frames i.v.m. Mac startup
                    ret = False
                    for _ in range(5):
                        ret, f = cap.read()
                        if ret and f is not None:
                            break
                        time.sleep(0.1)
                    
                    cap.release()
                    if ret:
                        best_cam = i
                        self._dev_log(f"[Camera] Gevonden op index {i}", "success")
                        break
            except Exception as e:
                self._dev_log(f"[Camera] Fout bij testen index {i}: {e}", "warning")
                
        self._start_video_source(best_cam)

    def _start_video_source(self, source):
        """Start video verwerking van een bron (pad of camera index)."""
        if self.pipeline is None:
            messagebox.showwarning(t("dialog_error_title"), t("dialog_not_ready"))
            return

        if self.video_running:
            self._stop_video()

        self.video_paused = False

        try:
            if isinstance(source, int) and sys.platform == "darwin":
                self.video_cap = cv2.VideoCapture(source, cv2.CAP_AVFOUNDATION)
            else:
                self.video_cap = cv2.VideoCapture(source)
        except Exception as e:
            messagebox.showerror(t("dialog_error_title"), f"{t('dialog_video_error')}\n{str(e)}")
            return

        if not self.video_cap.isOpened():
            messagebox.showerror(t("dialog_error_title"), t("dialog_video_error"))
            return

        self.video_running = True
        self.video_plates_found = set()
        self._video_drop_count = 0  # Houd bij hoeveel frames mislukken
        self.btn_stop_video.configure(state="normal")
        self.btn_load_video.configure(state="disabled")
        self.btn_camera.configure(state="disabled")

        self._dev_log(f"[Video] Bron geopend: {source}", "info")

        # Verwijder oude resultaten
        for w in self.video_results_scroll.winfo_children():
            w.destroy()

        # Start video loop
        self._video_frame_count = 0
        self._video_last_time = time.time()
        self._process_video_frame()

    def _process_video_frame(self):
        """Verwerk één video frame (wordt herhaaldelijk aangeroepen)."""
        if not self.video_running or self.video_cap is None:
            return

        if self.video_paused:
            return

        try:
            ret, frame = self.video_cap.read()
        except Exception as e:
            self._dev_log(f"[Video] Fout tijdens lezen frame: {e}", "error")
            ret = False

        if not ret or frame is None:
            self._video_drop_count += 1
            if self._video_drop_count > 30:  # Te veel foute frames op rij, ga uit van kapotte feed
                self._dev_log("[Video] Te veel frames mislukt. Stoppen...", "error")
                self._stop_video()
            else:
                # Probeer even te wachten en opnieuw (handig op Mac met trage AVFoundation)
                self._after_id = self.after(30, self._process_video_frame)
            return

        self._video_drop_count = 0  # Reset teller bij success
        self._video_frame_count += 1
        skip = int(self.vid_skip_slider.get())

        # Verwerk alleen elke N-de frame
        should_process = (self._video_frame_count % skip == 0)
        display_frame = frame.copy()

        if should_process and self.pipeline:
            results = self.pipeline.process_frame_array(frame)

            if results:
                # Teken bounding boxes
                pil_frame = cv2_to_pil(display_frame)
                pil_frame = draw_detections_on_pil(pil_frame, results)
                display_frame = cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGB2BGR)

                # Update resultaten
                for r in results:
                    if r.plate_text not in self.video_plates_found:
                        self.video_plates_found.add(r.plate_text)

                        thumb = cv2_to_pil(r.cropped_image)
                        card = PlateCard(
                            self.video_results_scroll,
                            plate_text=r.plate_text,
                            det_conf=r.detection_confidence,
                            ocr_conf=r.ocr_confidence,
                            thumbnail=thumb,
                            timestamp=datetime.now().strftime("%H:%M:%S"),
                            plate_color=getattr(r, "plate_color", "UNKNOWN"),
                        )
                        card.pack(fill="x", padx=4, pady=4)

                        # Voeg toe aan geschiedenis
                        self.all_results_history.append({
                            "plate": r.plate_text,
                            "det_conf": r.detection_confidence,
                            "ocr_conf": r.ocr_confidence,
                            "color": getattr(r, "plate_color", "UNKNOWN"),
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "source": t("source_video"),
                        })

        # Toon frame op canvas
        self._show_frame_on_canvas(display_frame)

        # Update FPS
        now = time.time()
        fps = 1.0 / max(now - self._video_last_time, 0.001)
        self._video_last_time = now
        self.vid_stat_fps.set_value(f"{fps:.0f}")
        self.vid_stat_plates.set_value(str(len(self.video_plates_found)))

        # Plan volgend frame
        delay = max(1, int(1000 / config.VIDEO_MAX_FPS))
        self._after_id = self.after(delay, self._process_video_frame)

    def _show_frame_on_canvas(self, frame: np.ndarray):
        """Toon een cv2 frame op het video canvas."""
        canvas_w = self.video_canvas.winfo_width()
        canvas_h = self.video_canvas.winfo_height()

        if canvas_w <= 1 or canvas_h <= 1:
            return

        pil_img = cv2_to_pil(frame)
        display_img = fit_image(pil_img, canvas_w, canvas_h)

        self._video_photo = ImageTk.PhotoImage(display_img)
        self.video_canvas.delete("all")
        self.video_canvas.create_image(
            canvas_w // 2, canvas_h // 2,
            image=self._video_photo, anchor="center",
        )

    def _stop_video(self):
        """Stop video verwerking."""
        self.video_running = False
        self.video_paused = False

        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None

        self.btn_stop_video.configure(state="disabled")
        self.btn_load_video.configure(state="normal")
        self.btn_camera.configure(state="normal")
        self.vid_stat_fps.set_value("-")
        self._dev_log("[Video] Gestopt", "info")

    def _on_frame_skip_change(self, value):
        """Callback voor frame skip slider."""
        val = int(value)
        self.vid_skip_label.configure(text=str(val))
        config.VIDEO_FRAME_SKIP = val

    # ──────────────────────────────────────────────────────
    #  Instellingen Acties
    # ──────────────────────────────────────────────────────

    def _apply_settings(self, *args):
        """Pas gewijzigde instellingen toe."""
        # Detectie
        if hasattr(self, "slider_conf_threshold"):
            config.DETECTION_CONFIDENCE = self.slider_conf_threshold.get()
        if hasattr(self, "slider_iou_threshold"):
            config.DETECTION_IOU = self.slider_iou_threshold.get()

        # Kleurfilter
        if hasattr(self, "color_filter_var"):
            config.COLOR_FILTER_ENABLED = self.color_filter_var.get()
        if hasattr(self, "plate_mode_var"):
            config.PLATE_MODE = self.plate_mode_var.get()
        if hasattr(self, "slider_color_threshold"):
            config.COLOR_THRESHOLD = self.slider_color_threshold.get()

        # Preprocessing
        for step_name, var in self.preprocess_vars.items():
            config.PREPROCESSING[step_name] = var.get()

        # Denoise
        if hasattr(self, "slider_denoise_strength"):
            config.DENOISE_STRENGTH = int(self.slider_denoise_strength.get())

        # OCR
        if hasattr(self, "slider_ocr_conf_min"):
            config.OCR_CONFIDENCE_MIN = self.slider_ocr_conf_min.get()

        # Herinitialiseer preprocessor als pipeline bestaat
        if self.pipeline:
            from preprocessor import PlatePreprocessor
            self.pipeline.preprocessor = PlatePreprocessor()

        self._dev_log("[Settings] Instellingen bijgewerkt", "info")

    def _browse_model(self):
        """Open bestandsdialoog voor modelbestand."""
        path = filedialog.askopenfilename(
            title=t("dialog_select_model"),
            filetypes=[(t("filetypes_model"), "*.pt"), (t("filetypes_all"), "*.*")],
        )
        if path:
            self.model_path_var.set(path)

    def _reload_model(self):
        """Herlaad het model met het nieuwe pad."""
        new_path = self.model_path_var.get()
        if not Path(new_path).exists():
            messagebox.showerror(t("dialog_error_title"),
                                  f"{t('dialog_model_not_found')}\n{new_path}")
            return

        self.model_path = new_path
        self.status_dot.configure(text_color=Colors.WARNING)
        self.status_label.configure(text=t("reloading"))
        self._dev_log(f"[Model] Herladen: {new_path}", "step")

        def reload():
            try:
                from pipeline import ALPRPipeline
                self.pipeline = ALPRPipeline(
                    self.model_path,
                    log_callback=self._dev_log,
                    progress_callback=self._on_progress_callback,
                )
                self._schedule(self._on_pipeline_ready)
            except Exception as e:
                self._schedule(lambda err=str(e): self._on_pipeline_error(err))

        threading.Thread(target=reload, daemon=True).start()

    # ──────────────────────────────────────────────────────
    #  Geschiedenis Acties
    # ──────────────────────────────────────────────────────

    def _refresh_history(self):
        """Ververs de geschiedenis-pagina."""
        for w in self.history_scroll.winfo_children():
            w.destroy()

        if not self.all_results_history:
            ctk.CTkLabel(
                self.history_scroll,
                text=t("history_empty"),
                font=ctk.CTkFont(size=13),
                text_color=Colors.TEXT_MUTED, justify="center",
            ).pack(pady=60)
            return

        # Header
        header = ctk.CTkFrame(self.history_scroll, fg_color=Colors.BG_LIGHT,
                               corner_radius=8)
        header.pack(fill="x", padx=4, pady=(0, 8))
        header.grid_columnconfigure((0, 1, 2, 3), weight=1)

        for i, col_key in enumerate(["col_plate", "col_detection", "col_ocr", "col_time"]):
            ctk.CTkLabel(
                header, text=t(col_key),
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Colors.TEXT_SECONDARY,
            ).grid(row=0, column=i, padx=12, pady=8)

        # Rijen (nieuwste eerst)
        for entry in reversed(self.all_results_history):
            row_frame = ctk.CTkFrame(self.history_scroll, fg_color=Colors.BG_CARD,
                                      corner_radius=8)
            row_frame.pack(fill="x", padx=4, pady=2)
            row_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

            values = [
                (entry["plate"], Colors.SUCCESS, ("Courier", 14, "bold")),
                (f"{entry['det_conf']:.0%}", Colors.TEXT_PRIMARY, (None, 12, None)),
                (f"{entry['ocr_conf']:.0%}", Colors.TEXT_PRIMARY, (None, 12, None)),
                (f"{entry['time']} ({entry['source']})", Colors.TEXT_SECONDARY, (None, 11, None)),
            ]

            for i, (text, color, font_spec) in enumerate(values):
                fam, size, weight = font_spec
                font = ctk.CTkFont(family=fam, size=size, weight=weight or "normal")
                ctk.CTkLabel(
                    row_frame, text=text, font=font, text_color=color,
                ).grid(row=0, column=i, padx=12, pady=8)

    def _export_history_csv(self):
        """Exporteer geschiedenis naar CSV."""
        if not self.all_results_history:
            messagebox.showinfo(t("dialog_no_data_title"), t("no_data"))
            return

        path = filedialog.asksaveasfilename(
            title=t("dialog_export_csv"),
            defaultextension=".csv",
            filetypes=[(t("filetypes_csv"), "*.csv")],
            initialfilename=f"alpr_resultaten_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return

        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["plate", "det_conf", "ocr_conf", "time", "source"])
            writer.writeheader()
            writer.writerows(self.all_results_history)

        messagebox.showinfo(t("dialog_exported_title"),
                             f"{t('exported_msg')}\n{path}")

    def _clear_history(self):
        """Wis alle geschiedenis."""
        if messagebox.askyesno(t("dialog_clear_title"), t("confirm_clear")):
            self.all_results_history.clear()
            self._refresh_history()

    # ──────────────────────────────────────────────────────
    #  Cleanup
    # ──────────────────────────────────────────────────────

    def destroy(self):
        """Ruim op bij sluiten."""
        self.video_running = False
        if self.video_cap:
            self.video_cap.release()
        super().destroy()


# ──────────────────────────────────────────────────────────────
#  Entry Point
# ──────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ALPR GUI")
    parser.add_argument("--model", "-m", default=None,
                        help="Pad naar YOLOv8 model")
    parser.add_argument("--dev", action="store_true",
                        help="Start in dev mode")
    parser.add_argument("--lang", choices=["nl", "en"], default=None,
                        help="Interfacetaal (nl/en)")
    args = parser.parse_args()

    if args.lang:
        set_language(args.lang)

    if args.dev:
        config.DEV_MODE = True

    app = ALPRApp(model_path=args.model)
    app.mainloop()


if __name__ == "__main__":
    main()
