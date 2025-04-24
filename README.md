# Roboclone

Roboclone is a lightweight Python GUI that wraps **Robocopy** (Windows) to perform quick, automated, and verifiable backups.

![Roboclone screenshot](docs/screenshot.png)

## Features
- Browse–select source and target folders
- Dry‑run mode (`/L`) to preview changes
- Exclusion list for files / directories
- Free‑space pre‑check to avoid failed copies
- Progress bar based on Robocopy log
- Tray notification on completion
- Post‑action: **none / close app / reboot / shutdown** with 5‑second cancel window
- Portable ‑ no installer required (just Python 3.9+)

## Requirements
```bash
pip install pillow plyer
