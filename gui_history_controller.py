#!/usr/bin/env python3
"""
ALPR Systeem - History Controller Mixin
==========================================
Bevat alle logica voor de geschiedenis-pagina.
"""

import csv
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from translations import t
from gui_components import Colors, PlateCard


class HistoryControllerMixin:
    """Mixin voor geschiedenis-gerelateerde functionaliteit."""

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
