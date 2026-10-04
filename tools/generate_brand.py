#!/usr/bin/env python3
"""Render the maintained SVG with ImageMagick (development dependency only)."""
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
brand = ROOT / "custom_components/solarman_azzurro/brand"
brand.mkdir(exist_ok=True)
for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
    subprocess.run(["convert", "-background", "none", "-density", "192",
                    str(ROOT / "docs/icon.svg"), "-resize", f"{size}x{size}",
                    "PNG32:" + str(brand / name)], check=True)
