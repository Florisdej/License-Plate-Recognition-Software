"""
ALPR Systeem - OCR Module
==========================
EasyOCR-integratie voor het uitlezen van kentekentekst uit gecropte afbeeldingen.
Bevat postprocessing specifiek voor Nederlandse/Europese kentekens.
"""

import logging
import re
import numpy as np
from typing import Optional, Tuple
import easyocr
import config

logger = logging.getLogger(__name__)


class PlateOCR:
    """
    OCR-engine voor kentekenherkenning.

    Gebruikt EasyOCR met postprocessing voor het corrigeren van
    veelvoorkomende herkenningsfouten bij kentekens.
    """

    # Veelvoorkomende OCR-verwisselingen bij kentekens
    CHAR_CORRECTIONS = {
        "O": "0",   # Letter O → Cijfer 0 (in cijferposities)
        "I": "1",   # Letter I → Cijfer 1 (in cijferposities)
        "S": "5",   # Letter S → Cijfer 5 (in cijferposities)
        "B": "8",   # Letter B → Cijfer 8 (in cijferposities)
        "G": "6",   # Letter G → Cijfer 6 (in cijferposities)
        "Z": "2",   # Letter Z → Cijfer 2 (in cijferposities)
        "0": "O",   # Cijfer 0 → Letter O (in letterposities)
        "1": "I",   # Cijfer 1 → Letter I (in letterposities)
        "5": "S",   # Cijfer 5 → Letter S (in letterposities)
        "8": "B",   # Cijfer 8 → Letter B (in letterposities)
        "6": "G",   # Cijfer 6 → Letter G (in letterposities)
        "2": "Z",   # Cijfer 2 → Letter Z (in letterposities)
    }

    # Nederlandse kentekenpatronen (sidecode formaten)
    # Elk patroon is een tuple van: (gecompileerde regex, format_beschrijving)
    NL_PLATE_PATTERNS = [
        (re.compile(r"^[A-Z]{2}-?\d{3}-?[A-Z]$"),      "XX-999-X (sidecode 9)"),
        (re.compile(r"^[A-Z]-?\d{3}-?[A-Z]{2}$"),       "X-999-XX (sidecode 8)"),
        (re.compile(r"^\d-?[A-Z]{3}-?\d{2}$"),          "9-XXX-99 (sidecode 7)"),
        (re.compile(r"^\d{2}-?[A-Z]{3}-?\d$"),          "99-XXX-9 (sidecode 6)"),
        (re.compile(r"^[A-Z]{3}-?\d{2}-?[A-Z]$"),       "XXX-99-X"),
        (re.compile(r"^[A-Z]-?\d{2}-?[A-Z]{3}$"),       "X-99-XXX"),
        (re.compile(r"^\d{2}-?[A-Z]{2}-?\d{2}$"),       "99-XX-99"),
        (re.compile(r"^[A-Z]{2}-?\d{2}-?[A-Z]{2}$"),    "XX-99-XX"),
        (re.compile(r"^\d{2}-?\d{2}-?[A-Z]{2}$"),       "99-99-XX"),
        (re.compile(r"^[A-Z]{2}-?\d{2}-?\d{2}$"),       "XX-99-99"),
        (re.compile(r"^\d{2}-?[A-Z]{2}-?[A-Z]{2}$"),    "99-XX-XX"),
        (re.compile(r"^[A-Z]{2}-?[A-Z]{2}-?\d{2}$"),    "XX-XX-99"),
    ]

    def __init__(self):
        logger.info("[OCR] EasyOCR initialiseren (talen: %s)...", config.OCR_LANGUAGES)
        logger.info("[OCR] GPU: %s", config.OCR_GPU)

        try:
            self.reader = easyocr.Reader(
                config.OCR_LANGUAGES,
                gpu=config.OCR_GPU,
                verbose=False,
            )
        except Exception as e:
            raise RuntimeError(
                f"EasyOCR initialisatie mislukt: {e}\n"
                "Controleer OCR_LANGUAGES en OCR_GPU in config.py."
            ) from e

        logger.info("[OCR] EasyOCR gereed")

    def read_plate(self, plate_image: np.ndarray) -> Tuple[str, float]:
        """
        Lees de tekst van een kentekenafbeelding.

        Args:
            plate_image: Voorverwerkte kentekenafbeelding

        Returns:
            Tuple van (kentekentekst, confidence_score)
        """
        if plate_image is None or plate_image.size == 0:
            return "", 0.0

        # Voer OCR uit
        results = self.reader.readtext(
            plate_image,
            detail=1,            # Geeft bbox, tekst, confidence
            paragraph=False,      # Geen paragraaf-groepering
            min_size=10,
            text_threshold=0.5,
            low_text=0.3,
            width_ths=0.7,
        )

        if not results:
            return "", 0.0

        # Stap 1: Analyseer hoogtes en posities
        candidates = []
        max_height = 0

        for (bbox, text, conf) in results:
            if conf < config.OCR_CONFIDENCE_MIN:
                continue

            # Bbox formaat: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
            # Bereken gemiddelde hoogte van het tekstblok
            h = abs(bbox[2][1] - bbox[1][1])
            if h > max_height:
                max_height = h
            
            # Bereken centrum x-positie voor sortering
            center_x = (bbox[0][0] + bbox[1][0]) / 2
            
            candidates.append({
                "text": text,
                "conf": conf,
                "height": h,
                "x": center_x,
                "bbox": bbox
            })

        if not candidates:
            return "", 0.0


        




        # Stap 2: Filter ruis & Sorteer
        final_pieces = []
        
        # Functie om items te sorteren op 'leesvolgorde'
        def sort_reading_order(items):
            if not items: return []
            items.sort(key=lambda i: i["bbox"][0][1]) # Sorteer op Y
            
            lines = []
            current_line = [items[0]]
            
            for item in items[1:]:
                prev = current_line[-1]
                y_diff = abs(item["bbox"][0][1] - prev["bbox"][0][1])
                h_avg = (item["height"] + prev["height"]) / 2
                
                if y_diff < (h_avg * 0.5): 
                    current_line.append(item)
                else:
                    lines.append(current_line)
                    current_line = [item]
            lines.append(current_line)
            
            result = []
            for line in lines:
                line.sort(key=lambda i: i["x"])
                result.extend(line)
            return result

        candidates = sort_reading_order(candidates)
        
        # Bepaal drempel voor "grote" tekst
        thresh_factor = 0.5 if config.VEHICLE_MODE == "scooter" else 0.6
        min_height = max_height * thresh_factor

        for item in candidates:
            text = item["text"].strip().upper()
            h = item["height"]
            
            if config.VERBOSE:
                logger.debug("[OCR] Kandidaat: '%s', Hoogte: %.1f (Max: %.1f, Min: %.1f)",
                             text, h, max_height, min_height)

            # Filter op grootte
            if h < min_height:
                if config.VERBOSE:
                    logger.debug("   -> REJECT: Te klein (< %.1f)", min_height)
                continue

            # Filter typische "ruis" teksten
            if len(text) < 3 and text.isalpha():
                if config.VERBOSE:
                    logger.debug("   -> REJECT: Te kort & alpha")
                continue

            # Blacklist
            if text in ["NL", "EU", "GARAGE", "DEALER", "AUTO", "BMW", "AUDI", "VOLVO"]:
                if config.VERBOSE:
                    logger.debug("   -> REJECT: Blacklist")
                continue

            if config.VERBOSE:
                logger.debug("   -> ACCEPT")
            final_pieces.append(item)

        if not final_pieces:
            return "", 0.0

        # Stap 3: Combineer resultaten
        # Bij NL kentekens zit er soms ruimte tussen delen (bijv. XX-XX-XX).
        # We voegen ze samen zonder spaties, de formatter lost de streepjes op.
        combined_text = "".join([p["text"] for p in final_pieces])
        avg_confusion = sum([p["conf"] for p in final_pieces]) / len(final_pieces)

        # Stap 4: Postprocessing & validatie
        cleaned = self._clean_plate_text(combined_text)

        if config.VERBOSE:
            logger.debug("[OCR] Ruwe tekst: '%s' → Opgeschoond: '%s' (conf: %.2f)",
                         combined_text, cleaned, avg_confusion)

        return cleaned, avg_confusion

    def read_plate_multi(self, variants: list) -> Tuple[str, float]:
        """
        Probeer meerdere preprocessingvarianten en kies het beste resultaat.

        Args:
            variants: Lijst van voorverwerkte afbeeldingen

        Returns:
            Beste (kentekentekst, confidence_score) uit alle varianten
        """
        best_text = ""
        best_conf = 0.0

        for i, variant in enumerate(variants):
            text, conf = self.read_plate(variant)

            # Geef bonus aan resultaten die matchen met NL-kentekenpatronen
            if self._matches_nl_pattern(text):
                conf += 0.15  # Bonus voor geldig patroon

            if conf > best_conf and len(text) >= 4:
                best_text = text
                best_conf = conf

                # Vroeg stoppen: hoog vertrouwen + geldig NL-patroon, verdere varianten overbodig
                if best_conf >= 0.7 and self._matches_nl_pattern(best_text):
                    break

        return best_text, min(best_conf, 1.0)

    def _clean_plate_text(self, raw_text: str) -> str:
        """
        Schoon ruwe OCR-tekst op voor kentekenformaat.

        Stappen:
        1. Verwijder ongeldige tekens
        2. Converteer naar hoofdletters
        3. Verwijder extra spaties
        4. Formatteer als kenteken
        """
        # Naar hoofdletters
        text = raw_text.upper().strip()

        # Behoud alleen geldige kentekentekens
        text = re.sub(r"[^A-Z0-9\-\s]", "", text)

        # Verwijder spaties en streepjes voor analyse
        stripped = re.sub(r"[\s\-]", "", text)

        # Probeer NL-kentekenformattering toe te passen
        formatted = self._format_nl_plate(stripped)

        return formatted if formatted else stripped

    def _format_nl_plate(self, text: str) -> Optional[str]:
        """
        Probeer tekst te formatteren als Nederlands kenteken.

        Nederlandse kentekens bestaan uit 6 tekens in groepen van 2-3,
        gescheiden door streepjes.
        """
        if len(text) < 5 or len(text) > 8:
            return None

        # Verwijder bestaande streepjes
        clean = text.replace("-", "")

        if len(clean) != 6:
            return None

        # Analyseer het patroon (L=letter, D=cijfer)
        pattern = ""
        for char in clean:
            pattern += "D" if char.isdigit() else "L"

        # Bekende Nederlandse kentekenpatronen en hun groepering
        format_map = {
            "LLDDDD": (2, 2, 2),   # XX-99-99
            "DDDDLL": (2, 2, 2),   # 99-99-XX
            "DDLLDD": (2, 2, 2),   # 99-XX-99
            "LLDDLL": (2, 2, 2),   # XX-99-XX
            "LLLLDD": (2, 2, 2),   # XX-XX-99
            "DDLLLL": (2, 2, 2),   # 99-XX-XX
            "DLLLDL": (1, 3, 2),   # 9-XXX-99
            "DLLLDD": (1, 3, 2),   # 9-XXX-99
            "DDLLLD": (2, 3, 1),   # 99-XXX-9
            "DDDLLL": (3, 3, 0),   # alt format
            "LDDDLL": (1, 3, 2),   # X-999-XX
            "LLDDDL": (2, 3, 1),   # XX-999-X
            "LLLDDL": (3, 2, 1),   # XXX-99-X
            "LDDLLL": (1, 2, 3),   # X-99-XXX
        }

        grouping = format_map.get(pattern)
        if grouping and grouping[2] > 0:
            g1, g2, g3 = grouping
            return f"{clean[:g1]}-{clean[g1:g1+g2]}-{clean[g1+g2:]}"

        # Fallback: groepeer als XX-XX-XX
        if len(clean) == 6:
            return f"{clean[:2]}-{clean[2:4]}-{clean[4:]}"

        return clean

    def _matches_nl_pattern(self, text: str) -> bool:
        """Controleer of tekst overeenkomt met een bekend NL-kentekenpatroon."""
        clean = text.replace("-", "").replace(" ", "")
        for pattern, _ in self.NL_PLATE_PATTERNS:
            if pattern.match(clean):
                return True
        return False
