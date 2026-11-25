#!/usr/bin/env python3
"""ESP32 USB serial prober and 1-bit e-ink image dithering + C header generator (stdlib only)."""

import argparse
import glob
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BAYER_8X8 = [
    [0, 48, 12, 60, 3, 51, 15, 63],
    [32, 16, 44, 28, 35, 19, 47, 31],
    [8, 56, 4, 52, 11, 59, 7, 55],
    [40, 24, 36, 20, 43, 27, 39, 23],
    [2, 50, 14, 62, 1, 49, 13, 61],
    [34, 18, 46, 30, 33, 17, 45, 29],
    [10, 58, 6, 54, 9, 57, 5, 53],
    [42, 26, 38, 22, 41, 25, 37, 21],
]


def cmd_probe(output: Path) -> None:
    ports = sorted(
        set(
            glob.glob("/dev/cu.usb*")
            + glob.glob("/dev/cu.SLAB*")
            + glob.glob("/dev/cu.wch*")
            + glob.glob("/dev/ttyUSB*")
            + glob.glob("/dev/ttyACM*")
        )
    )
    tools = {t: shutil.which(t) for t in ["esptool.py", "esptool", "pio", "arduino-cli", "idf.py"]}
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "serial_ports": ports,
        "installed_tools": tools,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    print(f"Success! Probed {len(ports)} serial port(s) -> {output}")


def load_bmp_gray(bmp_path: Path, target_w: int, target_h: int) -> list[list[float]]:
    data = bmp_path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError(f"Not a valid BMP file: {bmp_path}")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    src_w, raw_h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    top_down = raw_h < 0
    src_h = abs(raw_h)
    src_w = abs(src_w)
    bytes_per_px = bpp // 8
    row_stride = ((src_w * bytes_per_px + 3) // 4) * 4

    grid = [[255.0] * target_w for _ in range(target_h)]
    for y in range(target_h):
        sy = min(src_h - 1, int(y * src_h / target_h))
        row_idx = sy if top_down else (src_h - 1 - sy)
        row_start = pixel_offset + row_idx * row_stride
        for x in range(target_w):
            sx = min(src_w - 1, int(x * src_w / target_w))
            off = row_start + sx * bytes_per_px
            if off + 3 <= len(data):
                b, g, r = data[off], data[off + 1], data[off + 2]
                grid[y][x] = 0.299 * r + 0.587 * g + 0.114 * b
    return grid


def dither_bayer8(grid: list[list[float]]) -> list[list[int]]:
    h, w = len(grid), len(grid[0])
    out = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            thresh = ((BAYER_8X8[y & 7][x & 7] + 0.5) / 64.0) * 255.0
            out[y][x] = 1 if grid[y][x] >= thresh else 0  # 1=white, 0=black
    return out


def dither_floyd(grid: list[list[float]]) -> list[list[int]]:
    h, w = len(grid), len(grid[0])
    buf = [row[:] for row in grid]
    out = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            old = buf[y][x]
            new = 255.0 if old >= 128.0 else 0.0
            out[y][x] = 1 if new > 0 else 0
            err = old - new
            if x + 1 < w:
                buf[y][x + 1] += err * 7.0 / 16.0
            if y + 1 < h:
                if x > 0:
                    buf[y + 1][x - 1] += err * 3.0 / 16.0
                buf[y + 1][x] += err * 5.0 / 16.0
                if x + 1 < w:
                    buf[y + 1][x + 1] += err * 1.0 / 16.0
    return out


def cmd_dither(inp: Path, width: int, height: int, method: str, output: Path) -> None:
    if not inp.exists():
        print(f"Error: input image not found: {inp}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as td:
        if inp.suffix.lower() == ".bmp":
            bmp = inp
        else:
            bmp = Path(td) / "conv.bmp"
            proc = subprocess.run(
                ["sips", "-s", "format", "bmp", str(inp), "--out", str(bmp)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if proc.returncode != 0 or not bmp.exists():
                print("Error: non-BMP conversion requires macOS sips or a BMP input.", file=sys.stderr)
                sys.exit(1)
        grid = load_bmp_gray(bmp, width, height)

    bits = dither_bayer8(grid) if method == "bayer8" else dither_floyd(grid)
    row_bytes = (width + 7) // 8
    packed = bytearray()
    for y in range(height):
        for bx in range(row_bytes):
            byte = 0
            for bit in range(8):
                x = bx * 8 + bit
                val = bits[y][x] if x < width else 1
                if val:
                    byte |= 1 << (7 - bit)
            packed.append(byte)

    output.parent.mkdir(parents=True, exist_ok=True)
    # Write C header
    hex_rows = []
    for i in range(0, len(packed), 16):
        hex_rows.append("  " + ", ".join(f"0x{b:02X}" for b in packed[i : i + 16]))
    c_src = (
        f"// Generated by esp32-eink-builder ({width}x{height}, {method}, 1=white 0=black)\n"
        f"#pragma once\n"
        f"#include <stdint.h>\n"
        f"static const uint16_t EPAPER_WIDTH = {width};\n"
        f"static const uint16_t EPAPER_HEIGHT = {height};\n"
        f"static const uint8_t epaper_bitmap[{len(packed)}] = {{\n"
        + ",\n".join(hex_rows)
        + "\n};\n"
    )
    output.write_text(c_src)

    # Write PBM preview (P4 binary: 1=black, 0=white)
    pbm_path = output.with_suffix(".pbm")
    pbm_bytes = bytearray(f"P4\n{width} {height}\n".encode("ascii"))
    for b in packed:
        pbm_bytes.append((~b) & 0xFF)
    pbm_path.write_bytes(pbm_bytes)
    print(f"Success! Wrote {width}x{height} ({method}, {len(packed)} bytes) -> {output} and preview {pbm_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="ESP32 Serial Prober & E-Ink Dithering CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_p = sub.add_parser("probe", help="Detect connected USB serial boards and flashing tools")
    p_p.add_argument("--output", required=True, type=Path)

    p_d = sub.add_parser("dither", help="Dither an image to 1-bit e-ink C header + PBM preview")
    p_d.add_argument("--input", required=True, type=Path)
    p_d.add_argument("--width", required=True, type=int)
    p_d.add_argument("--height", required=True, type=int)
    p_d.add_argument("--method", choices=["bayer8", "floyd"], default="bayer8")
    p_d.add_argument("--output", required=True, type=Path)

    args = parser.parse_args()
    if args.command == "probe":
        cmd_probe(args.output)
    elif args.command == "dither":
        cmd_dither(args.input, args.width, args.height, args.method, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
