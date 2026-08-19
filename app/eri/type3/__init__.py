"""
ERI Type-3 subpackage — CBDT-compliant JSON generation + portal upload.

Type-3 makes NO ITD API calls. It:
  1. Generates a CBDT-compliant ITR JSON (shared FilingCore).
  2. Validates it locally against the official schema + CBDT rules.
  3. Exports the .json file for manual portal upload, OR
  4. Uploads it to the portal via Playwright automation.

This is the production focus for AY 2026-27 filing season.
"""
