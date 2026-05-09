"""
DouWan Free — Open-Source Screen Mirroring Engine
Supports USB (wired) and WiFi (wireless) mirroring for Android devices.
No login. No paywall. No telemetry.
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
import subprocess
import os
import re
import threading
import json
import time
import socket
import sys

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

base_path = get_base_path()
app = Flask(__name__, 
            template_folder=os.path.join(base_path, 'templates'),
            static_folder=os.path.join(base_path, 'static'))

# ── Global state ──────────────────────────────────────────────
active_sessions = {}          # device_id -> Popen handle
device_cache = []             # last known device list
scrcpy_path = "scrcpy"        # default: expect in PATH


# ── Helpers ───────────────────────────────────────────────────
def _run(cmd, timeout=8):
    """Run a shell command safely and return stdout."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        return r.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def _get_local_ip():
    """Return the machine's LAN IP for wireless instructions."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _parse_adb_devices():
    """Parse `adb devices -l` into a structured list."""
    raw = _run(["adb", "devices", "-l"])
    devices = []
    for line in raw.splitlines()[1:]:
        if not line.strip():
            continue
        parts = re.split(r"\s+", line.strip())
        if len(parts) < 2:
            continue

        dev_id = parts[0]
        status = parts[1]

        props = {}
        for p in parts[2:]:
            if ":" in p:
                k, v = p.split(":", 1)
                props[k] = v

        conn_type = "wireless" if ":" in dev_id and "." in dev_id.split(":")[0] else "usb"

        devices.append({
            "id": dev_id,
            "status": status,
            "model": props.get("model", "Unknown"),
            "device": props.get("device", ""),
            "transport_id": props.get("transport_id", ""),
            "connection": conn_type,
            "mirroring": dev_id in active_sessions,
        })
    return devices


def _get_device_details(device_id):
    """Fetch richer device info via adb shell."""
    brand = _run(["adb", "-s", device_id, "shell", "getprop", "ro.product.brand"])
    model = _run(["adb", "-s", device_id, "shell", "getprop", "ro.product.model"])
    android = _run(["adb", "-s", device_id, "shell", "getprop", "ro.build.version.release"])
    res = _run(["adb", "-s", device_id, "shell", "wm", "size"])
    battery = _run(["adb", "-s", device_id, "shell", "dumpsys", "battery"])

    batt_level = ""
    for l in battery.splitlines():
        if "level" in l:
            batt_level = l.split(":")[-1].strip()
            break

    return {
        "brand": brand if "ERROR" not in brand else "",
        "model": model if "ERROR" not in model else "Unknown",
        "android": android if "ERROR" not in android else "",
        "resolution": res.replace("Physical size: ", "") if "ERROR" not in res else "",
        "battery": batt_level,
    }


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/devices")
def api_devices():
    """List all ADB-connected devices (USB + wireless)."""
    global device_cache
    devices = _parse_adb_devices()
    device_cache = devices
    return jsonify({"devices": devices, "local_ip": _get_local_ip()})


@app.route("/api/device/<device_id>/details")
def api_device_details(device_id):
    """Get extended info for one device."""
    info = _get_device_details(device_id)
    return jsonify(info)


@app.route("/api/wireless/connect", methods=["POST"])
def api_wireless_connect():
    """Connect to a device over WiFi (ADB TCP/IP)."""
    data = request.json
    ip = data.get("ip", "").strip()
    port = data.get("port", "5555").strip()

    if not ip:
        return jsonify({"success": False, "error": "IP address required"})

    target = f"{ip}:{port}"
    out = _run(["adb", "connect", target])

    success = "connected" in out.lower()
    return jsonify({"success": success, "message": out})


@app.route("/api/wireless/pair", methods=["POST"])
def api_wireless_pair():
    """Pair with a device using Android 11+ wireless pairing."""
    data = request.json
    ip = data.get("ip", "").strip()
    port = data.get("port", "").strip()
    code = data.get("code", "").strip()

    if not all([ip, port, code]):
        return jsonify({"success": False, "error": "IP, port, and pairing code are required"})

    target = f"{ip}:{port}"
    try:
        proc = subprocess.Popen(
            ["adb", "pair", target],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        stdout, stderr = proc.communicate(input=code + "\n", timeout=15)
        out = stdout + stderr
        success = "successfully paired" in out.lower()
        return jsonify({"success": success, "message": out.strip()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/wireless/setup", methods=["POST"])
def api_wireless_setup():
    """Switch a USB-connected device to wireless mode (tcpip 5555)."""
    data = request.json
    device_id = data.get("device_id", "").strip()

    if not device_id:
        return jsonify({"success": False, "error": "Device ID required"})

    out = _run(["adb", "-s", device_id, "tcpip", "5555"])
    success = "restarting" in out.lower() or out == ""

    # Try to get IP of the device
    ip_out = _run(["adb", "-s", device_id, "shell", "ip", "route"])
    device_ip = ""
    for line in ip_out.splitlines():
        m = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", line)
        if m:
            device_ip = m.group(1)
            break

    return jsonify({"success": success, "message": out, "device_ip": device_ip})


@app.route("/api/start", methods=["POST"])
def api_start_mirror():
    """Launch scrcpy for a device."""
    data = request.json
    device_id = data.get("device_id", "").strip()
    max_fps = str(data.get("max_fps", 60))
    max_size = str(data.get("max_size", 0))
    bitrate = str(data.get("bitrate", "8M"))
    audio = data.get("audio", True)
    control = data.get("control", True)
    stay_awake = data.get("stay_awake", True)
    borderless = data.get("borderless", False)
    always_on_top = data.get("always_on_top", False)
    fullscreen = data.get("fullscreen", False)
    record_file = data.get("record", "")
    title = data.get("title", "")

    if not device_id:
        return jsonify({"success": False, "error": "No device ID"})

    if device_id in active_sessions:
        # Kill existing session first
        try:
            active_sessions[device_id].terminate()
        except Exception:
            pass
        del active_sessions[device_id]

    cmd = [scrcpy_path, "-s", device_id, "--max-fps", max_fps]

    if int(max_size) > 0:
        cmd.extend(["-m", max_size])

    if bitrate:
        cmd.extend(["-b", bitrate])

    if not audio:
        cmd.append("--no-audio")

    if not control:
        cmd.append("--no-control")

    if stay_awake:
        cmd.append("--stay-awake")

    if borderless:
        cmd.append("--window-borderless")

    if always_on_top:
        cmd.append("--always-on-top")

    if fullscreen:
        cmd.append("--fullscreen")

    if record_file:
        cmd.extend(["--record", record_file])

    if title:
        cmd.extend(["--window-title", title])

    try:
        proc = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        )
        active_sessions[device_id] = proc
        return jsonify({"success": True, "pid": proc.pid})
    except FileNotFoundError:
        return jsonify({"success": False, "error": "scrcpy not found in PATH. Install scrcpy first."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/stop", methods=["POST"])
def api_stop_mirror():
    """Stop a mirroring session."""
    data = request.json
    device_id = data.get("device_id", "")

    if device_id in active_sessions:
        try:
            active_sessions[device_id].terminate()
            del active_sessions[device_id]
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    return jsonify({"success": False, "error": "No active session for this device"})


@app.route("/api/status")
def api_status():
    """Health check with dependency versions."""
    adb_ver = _run(["adb", "version"]).split("\n")[0] if "ERROR" not in _run(["adb", "version"]) else "Not found"
    scrcpy_ver = _run([scrcpy_path, "--version"]) if "ERROR" not in _run([scrcpy_path, "--version"]) else "Not found"

    return jsonify({
        "status": "ok",
        "adb": adb_ver,
        "scrcpy": scrcpy_ver,
        "active_sessions": len(active_sessions),
        "local_ip": _get_local_ip(),
    })


if __name__ == "__main__":
    print("\n=== DouWan Free - Open Source Screen Mirroring ===")
    print("    http://127.0.0.1:5000")
    print("================================================\n")
    app.run(host="127.0.0.1", port=5000, debug=True)
