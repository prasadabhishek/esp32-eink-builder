# ESP32 & E-Ink Builder

Agent skill and Python 3 stdlib CLI for probing connected ESP32 / Cardputer / e-Paper boards and converting images to 1-bit **8×8 Bayer** or **Floyd-Steinberg** dithered C header arrays + PBM previews.

## Install as an Agent Skill

```bash
npx skills add prasadabhishek/esp32-eink-builder
```

## Standalone CLI Usage

```bash
# Detect connected USB serial boards and flashing CLIs
uv run scripts/eink_dither.py probe --output /tmp/esp-ports.json

# Generate 1-bit e-ink C header + PBM preview
uv run scripts/eink_dither.py dither \
  --input ./image.bmp \
  --width 800 --height 480 \
  --method bayer8 \
  --output /tmp/frame.h
```

## License

MIT

---
Built by [Abhishek Prasad](https://abhishekprasad.fyi)
