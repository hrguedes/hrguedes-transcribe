IDLE_COLOR = "#37474f"
RECORDING_COLOR = "#d32f2f"
PAUSED_COLOR = "#f9a825"


def record_button_style(color: str, size: int) -> str:
    return f"""
        QPushButton {{
            background-color: {color};
            color: white;
            border: none;
            border-radius: {size // 2}px;
            font-size: 22px;
            font-weight: 600;
        }}
        QPushButton:hover {{ border: 4px solid rgba(255, 255, 255, 0.35); }}
        QPushButton:disabled {{ background-color: #9e9e9e; }}
    """


APP_STYLE = """
    QListWidget#sessionList { border: none; font-size: 13px; }
    QListWidget#sessionList::item { padding: 8px 6px; }
    QLabel#timer { font-size: 44px; font-weight: 300; font-family: Menlo, Consolas, monospace; }
    QLabel#pageTitle { font-size: 20px; font-weight: 600; }
    QLabel#muted { color: #757575; }
    QLabel#warning { color: #b26a00; }
    QProgressBar#level { border: none; background: #e0e0e0; border-radius: 3px; max-height: 6px; }
    QProgressBar#level::chunk { background: #43a047; border-radius: 3px; }
"""
