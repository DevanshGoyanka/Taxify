"""
ais_extractor: PDF parsing for ITD documents (26AS, AIS, TIS).

Top-level convenience functions:
  - extract_26as(pdf_path) -> dict
  - extract_ais(pdf_path)  -> AISDocument
  - extract_tis(pdf_path)  -> TISDocument

JSON serialization helpers:
  - extract_26as_json(pdf_path) -> str
  - extract_ais_json(pdf_path)  -> str  (via extractor.ais_to_frontend_json)
  - extract_tis_json(pdf_path)  -> str  (via tis_extractor.tis_to_frontend_json)
"""

from ais_extractor.as26_extractor import extract_26as, extract_26as_json
from ais_extractor.extractor import AISExtractor, AISDocument, extract_ais, extract_ais_json, ais_to_frontend_json
from ais_extractor.tis_extractor import TISExtractor, TISDocument, extract_tis, tis_to_frontend_json

__all__ = [
    "extract_26as",
    "extract_26as_json",
    "extract_ais",
    "extract_ais_json",
    "ais_to_frontend_json",
    "extract_tis",
    "tis_to_frontend_json",
    "AISExtractor",
    "AISDocument",
    "TISExtractor",
    "TISDocument",
]
