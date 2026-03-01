#!/usr/bin/env python3
"""
ALPR Systeem - Video Controller Mixin
========================================
Bevat alle logica voor de video/camera-pagina.
"""

import sys
import cv2
import time
import numpy as np
from datetime import datetime
from PIL import ImageTk

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk

import config
from translations import t
from gui_components import (
    Colors, cv2_to_pil, fit_image, draw_detections_on_pil,
    PlateCard, StatWidget,
)


class VideoControllerMixin:
    """Mixin voor video/camera-gerelateerde functionaliteit."""

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

        try:
            # Drain camera-buffer: gooi gebufferde frames weg en pak het meest actuele frame.
            # Voorkomt dat verouderde (vage) frames worden verwerkt.
            for _ in range(2):
                self.video_cap.grab()
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
