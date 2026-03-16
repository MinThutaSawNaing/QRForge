# QRForge

QRForge is a polished PyQt6 desktop application for generating and scanning QR codes on Windows.

Created by Min Thuta Saw Naing.

## Features

- Generate QR codes instantly from text, links, notes, or Wi-Fi payloads
- Preview and export QR codes as PNG files
- Copy generated QR codes directly to the clipboard
- Scan QR codes with the default camera
- Scan QR codes from uploaded image files
- Production-friendly Windows packaging workflow

## Requirements

- Python 3.10+
- Windows 10 or later recommended
- A webcam for camera-based scanning

## Local Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Build A Windows Executable

Install PyInstaller:

```powershell
pip install pyinstaller
```

Build QRForge as a one-folder desktop app:

```powershell
pyinstaller --noconfirm --clean --windowed --name QRForge --icon logo.ico --add-data "logo.png;." --add-data "logo.ico;." main.py
```

This creates the packaged app in `dist\QRForge`.

## Create A Windows Installer

1. Install Inno Setup 6 on your PC.
2. Build the app with PyInstaller so `dist\QRForge` exists.
3. Open `QRForgeInstaller.iss` in Inno Setup.
4. Build the installer from Inno Setup.

The installer output will be created in the `installer` folder.

## Download For Windows

For non-technical users, the easiest option is the Windows installer:

- Download `installer/QRForge-Setup.exe` from this repository
- Run the installer
- Follow the setup steps on screen
- Launch `QRForge` from the Start menu or desktop shortcut

## Project Files

- `main.py` starts the Qt application
- `qr_maker_app.py` contains the main UI and QR logic
- `requirements.txt` lists Python dependencies
- `QRForgeInstaller.iss` packages the app into a Windows installer

## Notes

- Camera access depends on Windows privacy permissions and whether another app is already using the webcam.
- If camera scanning is unavailable, users can still scan QR codes from uploaded images.
