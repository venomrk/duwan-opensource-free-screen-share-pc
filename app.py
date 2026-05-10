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
from vcam_manager import vcam_manager
from streaming_service import streaming_service
active_sessions = {}          # device_id -> dict
device_cache = []             # Cached device list
streaming_process = None      # Global streaming process
SETTINGS_FILE = os.path.join(base_path, "stream_settings.json")

# scrcpy binary — uses PATH by default, override if needed
scrcpy_path = "scrcpy"


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
            active_sessions[device_id]["process"].terminate()
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

    if title:
        cmd.extend(["--window-title", title])

    if record_file == "STREAM":
        cmd.extend(["--record", "-", "--record-format", "matroska"])
        stdout_dest = subprocess.PIPE
    else:
        stdout_dest = None
        if record_file:
            cmd.extend(["--record", record_file])

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=stdout_dest,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" and record_file != "STREAM" else 0
        )
        
        # Store window title if we set it, otherwise fallback to scrcpy's default logic
        final_title = title if title else (f"scrcpy {device_id}")
        
        active_sessions[device_id] = {
            "process": proc,
            "window_title": final_title
        }
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
            # Also stop VCam if running
            vcam_manager.stop_vcam(device_id)
            
            active_sessions[device_id]["process"].terminate()
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


@app.route("/api/vcam/start", methods=["POST"])
def api_vcam_start():
    data = request.json
    device_id = data.get("device_id", "")
    
    if device_id not in active_sessions:
        return jsonify({"success": False, "error": "Device is not mirroring. Start mirroring first."})
    
    window_title = active_sessions[device_id]["window_title"]
    success, msg = vcam_manager.start_vcam(device_id, window_title)
    return jsonify({"success": success, "message": msg})


@app.route("/api/vcam/stop", methods=["POST"])
def api_vcam_stop():
    data = request.json
    device_id = data.get("device_id", "")
    success, msg = vcam_manager.stop_vcam(device_id)
    return jsonify({"success": success, "message": msg})


# --- Streaming Endpoints ---

@app.route("/api/stream/settings", methods=["GET", "POST"])
def api_stream_settings():
    if request.method == "POST":
        settings = request.json
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
        return jsonify({"success": True})
    
    if not os.path.exists(SETTINGS_FILE):
        return jsonify({"platforms": []})
    
    with open(SETTINGS_FILE, "r") as f:
        return jsonify(json.load(f))


@app.route("/api/stream/start", methods=["POST"])
def api_stream_start():
    data = request.json
    device_id = data.get("device_id", "")
    
    if device_id not in active_sessions:
        return jsonify({"success": False, "error": "Start mirroring in 'Stream Mode' first."})
    
    if not os.path.exists(SETTINGS_FILE):
        return jsonify({"success": False, "error": "No stream settings found."})
        
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)
    
    enabled_platforms = [p for p in settings.get("platforms", []) if p.get("enabled") and p.get("key")]
    
    if not enabled_platforms:
        return jsonify({"success": False, "error": "No platforms enabled with stream keys."})
    
    scrcpy_proc = active_sessions[device_id]["process"]
    success, msg = streaming_service.start_stream(scrcpy_proc, enabled_platforms)
    return jsonify({"success": success, "message": msg})


@app.route("/api/stream/stop", methods=["POST"])
def api_stream_stop():
    success, msg = streaming_service.stop_stream()
    return jsonify({"success": success, "message": msg})


if __name__ == "__main__":
    print("\n=== DouWan Free - Open Source Screen Mirroring ===")
    print("    http://127.0.0.1:5000")
    print("================================================\n")
    app.run(host="127.0.0.1", port=5000, debug=True)
