# DouWan Free — Open Source Screen Mirroring

DouWan Free is a completely free, open-source, and localized screen mirroring application for Windows. It provides ultra-low latency mirroring, device control, and an elegant Glassmorphic UI to seamlessly cast your Android device to your PC via USB or Wireless (WiFi).

![DouWan Free Screenshot](assets/screenshot.png)

## Features

- **Plug & Play USB Mirroring**: Connect your Android device via USB and mirror instantly.
- **Wireless Mirroring**: Auto-discover and connect to devices over the same network via ADB TCP/IP.
- **Android 11+ Wireless Pairing**: Pair devices over WiFi without ever needing a USB cable.
- **High Performance**: Powered by `scrcpy` and `adb` for 2K/4K resolution and up to 120 FPS.
- **PC Control**: Use your mouse and keyboard to control your Android device directly from the PC.
- **Audio Forwarding**: Stream device audio to your PC speakers natively.
- **No Login / No Paywall**: 100% free with no tracking, no watermarks, and no login required.

## Prerequisites

Before running the application, ensure you have the following system dependencies installed and added to your Windows PATH:

1. **ADB (Android Debug Bridge)**  
   Can be installed via Winget: `winget install Google.PlatformTools`
2. **scrcpy**  
   Can be installed via Winget: `winget install Genymobile.scrcpy`

Your Android device must have **USB Debugging** enabled in Developer Options.

## Download & Installation

You can download the pre-compiled executable for Windows from the **Releases** tab.

1. Download `DouWan_Free.exe`.
2. Double-click the application to launch.

## Building from Source

If you prefer to run or build the application from the source code:

### Requirements
- Python 3.10+
- Flask
- pywebview

### Setup
```bash
git clone https://github.com/venomrk/duwan-opensource-free-screen-share-pc.git
cd duwan-opensource-free-screen-share-pc

# Install Python dependencies
pip install -r requirements.txt

# Run the application natively
python main.py
```

### Compiling to Executable
To package the app into a standalone `.exe`:
```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --add-data "templates;templates" --add-data "static;static" --name "DouWan_Free" main.py
```
The compiled executable will be located in the `dist/` directory.

## License

This project is open-source. All underlying mirroring technology is powered by the excellent work of [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy).
