from __future__ import annotations

from typing import Dict


SLOT_MAP: Dict[str, Dict[str, Dict[str, str]]] = {
    "cover_centered_01": {
        "title": {"x": "10%", "y": "30%", "w": "80%", "h": "12%"},
        "subtitle": {"x": "10%", "y": "44%", "w": "80%", "h": "8%"},
        "footer": {"x": "10%", "y": "86%", "w": "80%", "h": "5%"},
    },
    "split_left_image_right_text": {
        "imageSlot": {"x": "5%", "y": "10%", "w": "40%", "h": "78%"},
        "title": {"x": "50%", "y": "12%", "w": "45%", "h": "12%"},
        "subtitle": {"x": "50%", "y": "26%", "w": "45%", "h": "8%"},
        "bullets": {"x": "50%", "y": "36%", "w": "45%", "h": "44%"},
        "footer": {"x": "50%", "y": "84%", "w": "45%", "h": "6%"},
    },
    "three_column_points": {
        "title": {"x": "5%", "y": "8%", "w": "90%", "h": "10%"},
        "card1": {"x": "5%", "y": "24%", "w": "28%", "h": "56%"},
        "card2": {"x": "36%", "y": "24%", "w": "28%", "h": "56%"},
        "card3": {"x": "67%", "y": "24%", "w": "28%", "h": "56%"},
        "footer": {"x": "5%", "y": "84%", "w": "90%", "h": "8%"},
    },
}
