#!/usr/bin/env python3
"""
ALPR Systeem - GUI Componenten
================================
Gedeelde kleuren, hulpfuncties en widgets voor de GUI.
"""

import cv2
import numpy as np
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

import customtkinter as ctk


# ──────────────────────────────────────────────────────────────
#  Thema & Kleuren
# ──────────────────────────────────────────────────────────────

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
