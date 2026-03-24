#!/usr/bin/env python3
"""
ALPR Systeem - Image Controller Mixin
========================================
Bevat alle logica voor de afbeeldingen-pagina.
"""

import cv2
import time
import threading
from pathlib import Path
from datetime import datetime
from PIL import ImageTk

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk

from translations import t
from gui_components import (
    Colors, cv2_to_pil, fit_image, draw_detections_on_pil,
    PlateCard, StatWidget,
)


class ImageControllerMixin:
    """Mixin voor afbeelding-gerelateerde functionaliteit."""

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
