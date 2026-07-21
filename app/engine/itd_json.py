"""
ITD JSON Output Builder (backwards-compatible re-export).

The actual builders now live in app.engine.itd (per-form modules).
Import from this module continues to work for existing callers.
"""

from app.engine.itd.itr1 import build_itr1_json  # noqa: F401
from app.engine.itd.itr2 import build_itr2_json  # noqa: F401
from app.engine.itd.itr4 import build_itr4_json  # noqa: F401

__all__ = ["build_itr1_json", "build_itr2_json", "build_itr4_json"]
