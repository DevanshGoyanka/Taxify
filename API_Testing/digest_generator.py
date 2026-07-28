#!/usr/bin/env python
"""
ITD Digest Generator — HMAC-SHA256 Iterative Hashing per SOP Section 5.3

Algorithm:
  1. Read/minify the ITR JSON (remove all interstitial spaces)
  2. Replace "Digest" value with placeholder "-"
  3. HMAC-SHA256 with secret key (UTF-8 encoded), repeated N iterations
  4. Base64-encode the final hash
  5. Inject back into JSON

Usage:
    python digest_generator.py --input ITR-1_EPPPG3078Q.json [--output OUT.json]

Environment variables:
    ERI_DIGEST_SECRET_KEY    — HMAC secret key string (UTF-8 encoded)
    ERI_DIGEST_ITERATIONS    — number of HMAC iterations (default: 1344)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

# ── defaults from environment ────────────────────────────────────────────────
DEFAULT_SECRET_KEY: str = os.getenv("ERI_DIGEST_SECRET_KEY", "")
DEFAULT_ITERATIONS: int = int(os.getenv("ERI_DIGEST_ITERATIONS", "1344"))
DIGEST_PLACEHOLDER: str = "-"
DIGEST_REGEX: str = r'"Digest"\s*:\s*"[^"]*"'


# ── helpers ──────────────────────────────────────────────────────────────────

def _minify_json(json_str: str) -> str:
    """Remove all interstitial whitespace from a JSON string.

    Only whitespace OUTSIDE quoted string values is removed,
    matching the SOP requirement: "Remove all extra spaces in the
    JSON that are not part of variable values."
    """
    result: list[str] = []
    in_string: bool = False
    escape: bool = False

    for ch in json_str:
        if in_string:
            if escape:
                escape = False
                result.append(ch)
            elif ch == '\\':
                escape = True
                result.append(ch)
            elif ch == '"':
                in_string = False
                result.append(ch)
            else:
                result.append(ch)
        else:
            if ch in (' ', '\t', '\n', '\r'):
                continue
            if ch == '"':
                in_string = True
            result.append(ch)

    return ''.join(result)


def _replace_digest_placeholder(json_str: str, placeholder: str = DIGEST_PLACEHOLDER) -> str:
    """Replace the Digest field value with the placeholder in a JSON string."""
    return re.sub(DIGEST_REGEX, f'"Digest":"{placeholder}"', json_str)


# ── core digest generation ──────────────────────────────────────────────────

def generate_digest(
    json_str: str,
    secret_key: str,
    iterations: int = 1,
    placeholder: str = DIGEST_PLACEHOLDER,
) -> str:
    """Generate an iterative HMAC-SHA256 digest for an ITR JSON string.

    Args:
        json_str: The COMPLETE ITR JSON string (indented or minified).
        secret_key: HMAC secret key string (UTF-8 encoded as key bytes).
        iterations: Number of times to repeat the HMAC-SHA256 operation.
        placeholder: Temporary value to replace the Digest field with.

    Returns:
        Base64-encoded digest string to be injected into the JSON.

    Per SOP Section 5.3:
      Step 1: Read JSON
      Step 2: Minify (remove interstitial spaces)
      Step 3: Replace Digest with placeholder "-"
      Step 4: Load secret key and iteration count
      Step 5: HMAC-SHA256 iteratively, then Base64 encode
      Step 6: Return digest
    """
    # Step 2: Minify
    minified = _minify_json(json_str)

    # Step 3: Replace Digest with placeholder
    minified = _replace_digest_placeholder(minified, placeholder)

    # Step 4+5: Iterative HMAC-SHA256 — secret key as UTF-8 bytes
    key_bytes = secret_key.encode("utf-8")
    data = minified.encode("utf-8")

    for _ in range(iterations):
        data = hmac.new(key_bytes, data, hashlib.sha256).digest()

    # Step 6: Base64 encode
    return base64.b64encode(data).decode("utf-8")


def generate_digest_from_dict(
    data: dict,
    secret_key: str,
    iterations: int = 1,
    placeholder: str = DIGEST_PLACEHOLDER,
) -> str:
    """Generate digest from a Python dict (serializes to JSON first).

    This is the entry point used by the ITD JSON builders in app/engine/itd/.
    """
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return generate_digest(raw, secret_key, iterations, placeholder)


# ── file-level operations ───────────────────────────────────────────────────

def inject_digest_into_json(
    input_path: Path,
    output_path: Optional[Path] = None,
    secret_key: str = "",
    iterations: int = 1,
) -> Tuple[str, int]:
    """Read a JSON file, compute & inject digest, save to output.

    Args:
        input_path: Path to the ITR JSON file.
        output_path: Where to write the updated JSON. Defaults to overwriting input.
        secret_key: HMAC secret key string.
        iterations: HMAC iteration count.

    Returns:
        Tuple of (digest_value, file_size_bytes).
    """
    raw: str = input_path.read_text(encoding="utf-8")

    # Compute digest
    digest_val: str = generate_digest(raw, secret_key, iterations)

    # Inject — replace digest in the raw string
    updated: str = re.sub(DIGEST_REGEX, f'"Digest":"{digest_val}"', raw)

    out: Path = output_path or input_path
    out.write_text(updated, encoding="utf-8")

    return digest_val, len(updated.encode("utf-8"))


# ── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ITR JSON Digest Generator (HMAC-SHA256, iterative per SOP 5.3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python digest_generator.py --input ITR-1_EPPPG3078Q.json
  python digest_generator.py --input ITR-1.json --output ITR-1_final.json
  python digest_generator.py --input ITR-1.json --key "4448ffc0cec1a25d" --iterations 1344

Environment:
  ERI_DIGEST_SECRET_KEY    Secret key for HMAC (UTF-8 encoded)
  ERI_DIGEST_ITERATIONS    Number of HMAC iterations
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="Input ITR JSON file path")
    parser.add_argument("--output", "-o", help="Output JSON file path (default: overwrite input)")
    parser.add_argument(
        "--key", "-k",
        default=DEFAULT_SECRET_KEY,
        help="HMAC secret key string (or set ERI_DIGEST_SECRET_KEY env var)",
    )
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Number of HMAC iterations (or set ERI_DIGEST_ITERATIONS env var)",
    )
    args = parser.parse_args()

    if not args.key:
        print("ERROR: No secret key provided. Use --key or set ERI_DIGEST_SECRET_KEY env var.",
              file=sys.stderr)
        sys.exit(1)

    inp: Path = Path(args.input).resolve()
    if not inp.exists():
        print(f"ERROR: Input file not found: {inp}", file=sys.stderr)
        sys.exit(1)

    out: Optional[Path] = Path(args.output).resolve() if args.output else None

    print(f"Input:       {inp}")
    print(f"Output:      {out or inp}{' (overwrite)' if out is None else ''}")
    print(f"Iterations:  {args.iterations}")
    print()

    digest_val, size = inject_digest_into_json(inp, out, args.key, args.iterations)

    print(f"  ✓ Digest computed and injected")
    print(f"  Digest:   {digest_val}")
    print(f"  File size: {size:,} bytes")


if __name__ == "__main__":
    main()
