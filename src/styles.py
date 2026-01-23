
class ModernStyles:
    # Color Palette (Dark Mode)
    COLORS = {
        "bg_main": "#1e1e1e",
        "bg_secondary": "#252526",
        "bg_tertiary": "#333333",
        "accent": "#007AFF",
        "accent_hover": "#0062cc",
        "text_primary": "#ffffff",
        "text_secondary": "#cccccc",
        "border": "#3e3e42",
        "success": "#4CAF50",
        "error": "#F44336",
        "table_header": "#2d2d2d",
        "table_alt_row": "#2a2a2a"
    }

    # Cross-platform font families
    # DejaVu Sans is pre-installed on Raspberry Pi OS and most Linux distributions
    # Liberation Sans is a free alternative to Arial
    # 'sans-serif' is the final fallback for any system
    FONTS = {
        "main": "DejaVu Sans, Liberation Sans, FreeSans, Arial, sans-serif",
        "mono": "DejaVu Sans Mono, Liberation Mono, FreeMono, Courier New, monospace"
    }

    @staticmethod
    def get_main_window_style():
        return f"""
            QMainWindow, QWidget {{
                background-color: {ModernStyles.COLORS['bg_main']};
                color: {ModernStyles.COLORS['text_primary']};
                font-family: "{ModernStyles.FONTS['main']}";
                font-size: 14px;
            }}
        """

    @staticmethod
    def get_button_style(is_primary=False):
        bg_color = ModernStyles.COLORS['accent'] if is_primary else ModernStyles.COLORS['bg_tertiary']
        hover_color = ModernStyles.COLORS['accent_hover'] if is_primary else ModernStyles.COLORS['bg_secondary']
        border = "none" if is_primary else f"1px solid {ModernStyles.COLORS['border']}"
        
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {ModernStyles.COLORS['text_primary']};
                border: {border};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {bg_color};
                padding-top: 9px;
                padding-bottom: 7px;
            }}
            QPushButton:disabled {{
                background-color: {ModernStyles.COLORS['bg_secondary']};
                color: {ModernStyles.COLORS['border']};
                border: 1px solid {ModernStyles.COLORS['border']};
            }}
        """

    @staticmethod
    def get_label_style(is_header=False, is_subtle=False):
        if is_header:
            return f"""
                QLabel {{
                    color: {ModernStyles.COLORS['text_primary']};
                    font-size: 24px;
                    font-weight: bold;
                    padding: 10px 0;
                }}
            """
        elif is_subtle:
            return f"""
                QLabel {{
                    color: {ModernStyles.COLORS['text_secondary']};
                    font-size: 12px;
                }}
            """
        return f"QLabel {{ color: {ModernStyles.COLORS['text_primary']}; }}"

    @staticmethod
    def get_image_container_style():
        return f"""
            QLabel {{
                background-color: {ModernStyles.COLORS['bg_secondary']};
                border: 2px dashed {ModernStyles.COLORS['border']};
                border-radius: 12px;
            }}
        """

    @staticmethod
    def get_table_style():
        return f"""
            QTableWidget {{
                background-color: {ModernStyles.COLORS['bg_secondary']};
                gridline-color: {ModernStyles.COLORS['border']};
                border: 1px solid {ModernStyles.COLORS['border']};
                border-radius: 8px;
                selection-background-color: {ModernStyles.COLORS['accent']};
                selection-color: {ModernStyles.COLORS['text_primary']};
            }}
            QHeaderView::section {{
                background-color: {ModernStyles.COLORS['table_header']};
                color: {ModernStyles.COLORS['text_primary']};
                padding: 6px;
                border: none;
                border-bottom: 1px solid {ModernStyles.COLORS['border']};
                font-weight: bold;
            }}
            QTableCornerButton::section {{
                background-color: {ModernStyles.COLORS['table_header']};
                border: none;
            }}
        """
    
    @staticmethod
    def get_progress_bar_style():
        return f"""
            QProgressBar {{
                border: none;
                background-color: {ModernStyles.COLORS['bg_tertiary']};
                border-radius: 4px;
                text-align: center;
                height: 8px;
            }}
            QProgressBar::chunk {{
                background-color: {ModernStyles.COLORS['accent']};
                border-radius: 4px;
            }}
        """
    
    @staticmethod
    def get_combobox_style():
        return f"""
            QComboBox {{
                background-color: {ModernStyles.COLORS['bg_tertiary']};
                color: {ModernStyles.COLORS['text_primary']};
                border: 1px solid {ModernStyles.COLORS['border']};
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                min-height: 20px;
            }}
            QComboBox:hover {{
                background-color: {ModernStyles.COLORS['bg_secondary']};
                border: 1px solid {ModernStyles.COLORS['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {ModernStyles.COLORS['text_primary']};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {ModernStyles.COLORS['bg_tertiary']};
                color: {ModernStyles.COLORS['text_primary']};
                border: 1px solid {ModernStyles.COLORS['border']};
                border-radius: 6px;
                selection-background-color: {ModernStyles.COLORS['accent']};
                selection-color: {ModernStyles.COLORS['text_primary']};
                padding: 4px;
            }}
            QComboBox:disabled {{
                background-color: {ModernStyles.COLORS['bg_secondary']};
                color: {ModernStyles.COLORS['border']};
            }}
        """
