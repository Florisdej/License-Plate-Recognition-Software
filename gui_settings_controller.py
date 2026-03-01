#!/usr/bin/env python3
"""
ALPR Systeem - Settings Controller Mixin
===========================================
Bevat alle logica voor de instellingen-pagina, taalwisseling en dev mode.
"""

import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

import config
from translations import t, set_language, get_language, LANGUAGES
from gui_components import Colors


class SettingsControllerMixin:
    """Mixin voor instellingen, taalwisseling en dev mode."""

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
