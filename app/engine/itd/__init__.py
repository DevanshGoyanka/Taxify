"""
ITD JSON Output Builders — per-form CBDT-compliant ITD JSON generation.

Usage:
    from app.engine.itd import build_itr1_json, build_itr2_json, build_itr3_json, build_itr4_json
"""

from app.engine.itd.itr1 import build_itr1_json
from app.engine.itd.itr2 import build_itr2_json
from app.engine.itd.itr3 import build_itr3_json
from app.engine.itd.itr4 import build_itr4_json

__all__ = ["build_itr1_json", "build_itr2_json", "build_itr3_json", "build_itr4_json"]
