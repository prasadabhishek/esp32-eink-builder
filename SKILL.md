---
name: esp32-eink-builder
description: >-
  Probes connected ESP32 / ESP32-S3 / Cardputer / Seeed SenseCraft e-Paper
  boards over USB serial, prepares 1-bit monochrome e-ink bitmaps using 8x8
  Bayer ordered dithering or Floyd-Steinberg error diffusion, and exports
  flash-ready C header arrays (PROGMEM) and PBM previews. Use when building
  ESP32 e-ink dashboards, converting images for e-paper displays, or debugging
  connected ESP32 serial devices.
---

# ESP32 & E-Ink Builder

## Overview

End-to-end helper for ESP32 / ESP32-S3 e-Paper displays (Seeed SenseCraft HMI, reTerminal E-Series, M5Stack Cardputer, Waveshare e-Paper): probes USB serial ports and converts images into crisp 1-bit dithered bitmaps + C header arrays ready for firmware compilation—using Python 3 stdlib only.

## Quick Start

```bash
# 1. Detect connected ESP32 / USB-JTAG serial ports
uv run scripts/eink_dither.py probe --output /tmp/esp-ports.json

# 2. Convert a BMP (or any macOS image via sips) to 1-bit e-ink PBM + C header array
uv run scripts/eink_dither.py dither \
  --input /path/to/photo.bmp \
  --width 800 --height 480 \
  --method bayer8 \
  --output /tmp/epaper_frame.h
```

## Utility Scripts

`scripts/eink_dither.py` uses Python 3 standard library only (plus macOS `sips` if converting PNG/JPEG to BMP).

### Subcommands
- **`probe --output <path.json>`**: Lists `/dev/cu.usb*` and `/dev/ttyUSB*`/`/dev/ttyACM*` devices and reports whether `esptool` / `pio` / `arduino-cli` are installed.
- **`dither --input <img_path> --width <W> --height <H> --method <bayer8|floyd> --output <file.h>`**:
  - Converts input image to grayscale luminance ($0.299R + 0.587G + 0.114B$), resizes to `W×H`, applies either **8×8 Bayer ordered dithering** (crisp retro print aesthetic, zero worm artifacts) or **Floyd-Steinberg** error diffusion, and writes both a packed 1-bit C byte array (`const unsigned char epaper_bitmap[]`) and a sibling `.pbm` visual preview.

## Workflow

1. **Probe Hardware:** Run `eink_dither.py probe` to confirm the serial port (`/dev/cu.usbmodem*`) and available flashing tools before writing firmware.
2. **Prepare E-Ink Assets:** Run `eink_dither.py dither` with the panel's native resolution (e.g. `800×480` for 7.5" panels, `296×128` for 2.9", `240×135` for Cardputer).
3. **Avoid Full-Screen Flash Fatigue:** On e-paper displays, prefer partial updates for clocks/widgets and schedule full refresh cycles every 10–15 partial updates to prevent ghosting.

## Common Mistakes

- **Wrong bit order or byte alignment:** Most Waveshare/GxEPD2 panels expect MSB-first packed bytes padded to 8-pixel row boundaries (`(width + 7) // 8` bytes per row); `eink_dither.py` enforces this automatically.
- **Using Floyd-Steinberg on flat UI gradients:** Floyd-Steinberg creates "worm" artifacts on solid fills; use `--method bayer8` for UI/dashboards and `--method floyd` for photographs.
- **Flashing while another serial monitor holds the port:** Close any active serial monitor (`screen`, `minicom`, PlatformIO monitor) before running `esptool`.
