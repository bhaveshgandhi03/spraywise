"""Fictional sample packets so judges can try the app without a real packet or an API key.

Dates are generated relative to today so the expiry logic can always be demonstrated.
Brand names are invented; nothing here copies a real product label.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _mmyyyy(d: date) -> str:
    return f"{d.month:02d}/{d.year}"


def build(today: date) -> dict[str, dict[str, Any]]:
    future = _mmyyyy(today + timedelta(days=500))
    past = _mmyyyy(today - timedelta(days=120))
    return {
        "paddy-fungicide": {
            "title": "Paddy fungicide (hexaconazole 5% EC)",
            "default_crop": "paddy",
            "label": {
                "readable": True, "product_name": "Sample Brand A",
                "ingredients": [{"name": "Hexaconazole", "percent": "5%"}], "formulation": "EC",
                "toxicity_color": "blue", "toxicity_words": "Moderately toxic",
                "printed_crops": ["Paddy"], "printed_dose": "1000 ml per hectare",
                "printed_waiting_period": "40 days", "registration_number": "CIR-SAMPLE-0001",
                "batch_number": "A123", "expiry_date": future, "manufacturer": "Sample Agro Pvt Ltd",
                "precautions": [],
            },
        },
        "tomato-monocrotophos": {
            "title": "Monocrotophos 36% SL on tomato",
            "default_crop": "tomato",
            "label": {
                "readable": True, "product_name": "Sample Brand B",
                "ingredients": [{"name": "Monocrotophos", "percent": "36%"}], "formulation": "SL",
                "toxicity_color": "red", "toxicity_words": "Extremely toxic",
                "printed_crops": ["Cotton", "Paddy"], "printed_dose": None,
                "printed_waiting_period": None, "registration_number": "CIR-SAMPLE-0002",
                "batch_number": "B777", "expiry_date": future, "manufacturer": "Sample Agro Pvt Ltd",
                "precautions": [],
            },
        },
        "groundnut-expired": {
            "title": "Chlorpyrifos 20% EC, expired",
            "default_crop": "groundnut",
            "label": {
                "readable": True, "product_name": "Sample Brand C",
                "ingredients": [{"name": "Chlorpyrifos", "percent": "20%"}], "formulation": "EC",
                "toxicity_color": "yellow", "toxicity_words": "Highly toxic",
                "printed_crops": ["Groundnut", "Paddy"], "printed_dose": None,
                "printed_waiting_period": None, "registration_number": "CIR-SAMPLE-0003",
                "batch_number": "C456", "expiry_date": past, "manufacturer": "Sample Agro Pvt Ltd",
                "precautions": [],
            },
        },
        "groundnut-oxyfluorfen": {
            "title": "Oxyfluorfen herbicide on groundnut",
            "default_crop": "groundnut",
            "label": {
                "readable": True, "product_name": "Sample Brand D",
                "ingredients": [{"name": "Oxyfluorfen", "percent": "23.5%"}], "formulation": "EC",
                "toxicity_color": "blue", "toxicity_words": "Moderately toxic",
                "printed_crops": ["Potato", "Groundnut"], "printed_dose": None,
                "printed_waiting_period": None, "registration_number": "CIR-SAMPLE-0004",
                "batch_number": "D890", "expiry_date": future, "manufacturer": "Sample Agro Pvt Ltd",
                "precautions": [],
            },
        },
        "tomato-mixed": {
            "title": "Mixed fungicide (azoxystrobin + difenoconazole)",
            "default_crop": "tomato",
            "label": {
                "readable": True, "product_name": "Sample Brand E",
                "ingredients": [{"name": "Azoxystrobin", "percent": "18.2%"},
                                {"name": "Difenoconazole", "percent": "11.4%"}], "formulation": "SC",
                "toxicity_color": "green", "toxicity_words": "Slightly toxic",
                "printed_crops": ["Tomato", "Paddy"], "printed_dose": None,
                "printed_waiting_period": "5 days", "registration_number": "CIR-SAMPLE-0005",
                "batch_number": "E321", "expiry_date": future, "manufacturer": "Sample Agro Pvt Ltd",
                "precautions": [],
            },
        },
    }
