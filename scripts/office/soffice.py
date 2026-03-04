#!/usr/bin/env python3
"""
LibreOffice headless wrapper for PPTX to PDF conversion.

Usage:
    python scripts/office/soffice.py --headless --convert-to pdf <input.pptx>

This is a thin wrapper that invokes LibreOffice in headless mode
for file format conversion, handling output directory placement.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="LibreOffice headless converter")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--convert-to", dest="format", help="Target format (e.g., pdf)")
    parser.add_argument("input_file", help="Input file to convert")
    parser.add_argument("--outdir", default=None, help="Output directory (defaults to input file directory)")
    args = parser.parse_args()

    input_path = Path(args.input_file).resolve()
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    outdir = args.outdir or str(input_path.parent)

    cmd = ["libreoffice"]
    if args.headless:
        cmd.append("--headless")
    if args.format:
        cmd.extend(["--convert-to", args.format])
    cmd.extend(["--outdir", outdir, str(input_path)])

    print(f"Converting: {input_path.name} -> {args.format or 'default'}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)

    output_name = input_path.stem + "." + (args.format or "pdf")
    output_path = Path(outdir) / output_name
    if output_path.exists():
        print(f"  Output: {output_path}")
    else:
        print(f"  Conversion completed (check output directory: {outdir})")


if __name__ == "__main__":
    main()
