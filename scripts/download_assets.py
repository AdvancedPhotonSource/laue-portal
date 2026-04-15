#!/usr/bin/env python3
"""
Download external CSS and font assets for air-gapped deployment.

Run this script on a machine with internet access **before** deploying to
an air-gapped system.  It fetches the three external stylesheets that
lau_dash.py normally loads from CDNs, plus their transitive font
dependencies, and places everything under the ``assets/`` directory so
Dash can serve them locally.

Usage:
    python scripts/download_assets.py          # from project root
    python scripts/download_assets.py --force  # re-download even if present
"""

import argparse
import os
import re
import urllib.request

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Project root is one level up from this script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

# The three external stylesheets used by lau_dash.py
FLATLY_CSS_URL = "https://cdn.jsdelivr.net/npm/bootswatch@5.3.6/dist/flatly/bootstrap.min.css"
DBC_CSS_URL = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"
BOOTSTRAP_ICONS_CSS_URL = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css"

# Bootstrap Icons font files (referenced by bootstrap-icons.css)
BOOTSTRAP_ICONS_FONT_BASE = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts"
BOOTSTRAP_ICONS_FONTS = [
    "bootstrap-icons.woff2",
    "bootstrap-icons.woff",
]

# Google Fonts CSS endpoint for Lato (referenced by Flatly theme via @import)
LATO_GOOGLE_FONTS_URL = "https://fonts.googleapis.com/css2?family=Lato:ital,wght@0,400;0,700;1,400&display=swap"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _download(url, dest, *, force=False, user_agent=None):
    """Download *url* to *dest*, skipping if the file already exists."""
    if os.path.exists(dest) and not force:
        print(f"  [skip] {os.path.relpath(dest, PROJECT_ROOT)} (already exists)")
        return
    print(f"  [download] {url}")
    req = urllib.request.Request(url)
    if user_agent:
        req.add_header("User-Agent", user_agent)
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(data)
    print(f"  [saved]    {os.path.relpath(dest, PROJECT_ROOT)} ({len(data):,} bytes)")


def _download_text(url, *, user_agent=None):
    """Download *url* and return the content as a string."""
    req = urllib.request.Request(url)
    if user_agent:
        req.add_header("User-Agent", user_agent)
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def _download_google_fonts(force=False):
    """
    Fetch the Lato woff2 font files from Google Fonts.

    Google Fonts serves different formats depending on User-Agent.  We use a
    modern Chrome UA to get woff2 (smallest, universally supported).

    Google Fonts splits fonts into subsets (e.g. ``latin``, ``latin-ext``).
    We download each subset file with a unique filename and generate local
    ``@font-face`` rules with the proper ``unicode-range`` declarations.

    Returns the ``@font-face`` CSS text to embed in the Flatly stylesheet.
    """
    ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    print("\nFetching Google Fonts CSS for Lato...")
    css = _download_text(LATO_GOOGLE_FONTS_URL, user_agent=ua)

    # Split into (comment, @font-face block) pairs.
    # Google Fonts CSS has   /* subset-name */\n@font-face { ... }
    entries = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{[^}]+\})", css, re.DOTALL)

    font_face_parts = []
    downloaded = 0

    for subset, block in entries:
        style_m = re.search(r"font-style:\s*(\w+)", block)
        weight_m = re.search(r"font-weight:\s*(\d+)", block)
        url_m = re.search(r"src:\s*url\(([^)]+)\)\s*format\(['\"]woff2['\"]\)", block)
        range_m = re.search(r"unicode-range:\s*([^;]+);", block)

        if not (style_m and weight_m and url_m):
            continue

        style = style_m.group(1)  # normal | italic
        weight = weight_m.group(1)  # 400 | 700

        # Build a unique filename per weight/style/subset
        if style == "italic":
            variant = "Italic"
        elif weight == "700":
            variant = "Bold"
        else:
            variant = "Regular"
        safe_subset = subset.replace("-", "")  # e.g. "latinext"
        name = f"Lato-{variant}-{safe_subset}.woff2"

        font_url = url_m.group(1)
        dest = os.path.join(FONTS_DIR, name)
        _download(font_url, dest, force=force)
        downloaded += 1

        # Build a local @font-face rule preserving unicode-range
        unicode_range = range_m.group(1).strip() if range_m else None
        face = (
            f"@font-face {{\n"
            f"  font-family: 'Lato';\n"
            f"  font-style: {style};\n"
            f"  font-weight: {weight};\n"
            f"  font-display: swap;\n"
            f"  src: url('fonts/{name}') format('woff2');\n"
        )
        if unicode_range:
            face += f"  unicode-range: {unicode_range};\n"
        face += "}\n"
        font_face_parts.append(face)

    if downloaded == 0:
        print("  [warn] No woff2 font URLs found in Google Fonts response.")
        print("         You may need to download Lato manually from")
        print("         https://fonts.google.com/specimen/Lato")
        return ""

    return "\n".join(font_face_parts)


def _patch_flatly_css(lato_font_face_css, force=False):
    """
    Download the Flatly Bootstrap CSS and replace the Google Fonts @import
    with local @font-face declarations.

    *lato_font_face_css* is the ``@font-face`` CSS text generated by
    :func:`_download_google_fonts`.
    """
    dest = os.path.join(ASSETS_DIR, "01-bootstrap-flatly.min.css")
    if os.path.exists(dest) and not force:
        print(f"  [skip] {os.path.relpath(dest, PROJECT_ROOT)} (already exists)")
        return

    print("\nDownloading Flatly Bootstrap CSS...")
    css = _download_text(FLATLY_CSS_URL)

    # Replace the @import url(...) for Google Fonts with our local @font-face
    patched, n = re.subn(
        r"@import\s+url\([^)]*fonts\.googleapis\.com[^)]*\)\s*;?",
        lato_font_face_css,
        css,
    )
    if n == 0:
        print("  [warn] No Google Fonts @import found in Flatly CSS to replace.")
        print("         The CSS may have changed upstream. Saving as-is.")

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(patched)
    size = os.path.getsize(dest)
    print(f"  [saved]    {os.path.relpath(dest, PROJECT_ROOT)} ({size:,} bytes, patched)")


def _patch_bootstrap_icons_css(force=False):
    """
    Download Bootstrap Icons CSS and adjust the font path from ``./fonts/``
    to ``fonts/`` (both are relative to ``assets/``).
    """
    dest = os.path.join(ASSETS_DIR, "03-bootstrap-icons.css")
    if os.path.exists(dest) and not force:
        print(f"  [skip] {os.path.relpath(dest, PROJECT_ROOT)} (already exists)")
        return

    print("\nDownloading Bootstrap Icons CSS...")
    css = _download_text(BOOTSTRAP_ICONS_CSS_URL)

    # The original CSS uses  url("./fonts/bootstrap-icons.woff2?hash...")
    # We keep it as  url("fonts/bootstrap-icons.woff2")  (strip hash too)
    patched = re.sub(
        r'url\("\./fonts/(bootstrap-icons\.woff2?)(\?[^"]+)?"\)',
        r'url("fonts/\1")',
        css,
    )

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(patched)
    size = os.path.getsize(dest)
    print(f"  [saved]    {os.path.relpath(dest, PROJECT_ROOT)} ({size:,} bytes, patched)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Download external CSS/font assets for air-gapped deployment.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download all files even if they already exist.",
    )
    args = parser.parse_args()
    force = args.force

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Assets dir:   {ASSETS_DIR}")
    print(f"Fonts dir:    {FONTS_DIR}")

    os.makedirs(FONTS_DIR, exist_ok=True)

    # 1. Bootstrap Icons font files (download first, before CSS patching)
    print("\n--- Bootstrap Icons Fonts ---")
    for font_file in BOOTSTRAP_ICONS_FONTS:
        _download(
            f"{BOOTSTRAP_ICONS_FONT_BASE}/{font_file}",
            os.path.join(FONTS_DIR, font_file),
            force=force,
        )

    # 2. Lato font files from Google Fonts (must run before Flatly CSS patch)
    print("\n--- Lato Font (Google Fonts) ---")
    lato_font_face_css = _download_google_fonts(force=force)

    # 3. Flatly Bootstrap CSS (with Google Fonts @import replaced by local @font-face)
    print("\n--- Flatly Bootstrap CSS ---")
    _patch_flatly_css(lato_font_face_css, force=force)

    # 4. DBC template CSS
    print("\n--- DBC Template CSS ---")
    _download(
        DBC_CSS_URL,
        os.path.join(ASSETS_DIR, "02-dbc.min.css"),
        force=force,
    )

    # 5. Bootstrap Icons CSS (with font path patch)
    print("\n--- Bootstrap Icons CSS ---")
    _patch_bootstrap_icons_css(force=force)

    print("\n" + "=" * 60)
    print("Done!  All assets saved under assets/")
    print()
    print("Next steps:")
    print("  1. Verify lau_dash.py uses  external_stylesheets=[]")
    print("  2. Commit the downloaded assets to version control")
    print("  3. Deploy to air-gapped system")
    print("=" * 60)


if __name__ == "__main__":
    main()
