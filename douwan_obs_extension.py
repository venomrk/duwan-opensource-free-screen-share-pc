import obspython as obs
import urllib.request
import urllib.parse
import json

# Global variables to store settings
api_url = "http://127.0.0.1:5000"
device_id = ""

def refresh_pressed(props, prop):
    """Called when the refresh button is pressed"""
    update_device_list(props)
    return True

def start_pressed(props, prop):
    """Called when the Start Mirroring button is pressed"""
    global device_id
    if not device_id:
        return True
    
    url = f"{api_url}/api/mirror/start"
    data = json.dumps({
        "device_id": device_id,
        "bitrate": "8M",
        "max_fps": "60",
        "title": f"OBS-Mirror-{device_id}"
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req)
        print(f"DouWan: Mirroring started for {device_id}")
    except Exception as e:
        print(f"DouWan Error: {e}")
    return True

def update_device_list(props):
    """Fetches device list from DouWan API and updates the dropdown"""
    p = obs.obs_properties_get(props, "device_list")
    obs.obs_property_list_clear(p)
    
    try:
        with urllib.request.urlopen(f"{api_url}/api/devices") as response:
            devices = json.loads(response.read().decode())
            for dev in devices:
                label = f"{dev['model']} ({dev['id']})"
                obs.obs_property_list_add_string(p, label, dev['id'])
    except:
        obs.obs_property_list_add_string(p, "DouWan App Not Running", "")

def script_properties():
    """Defines the UI properties in OBS"""
    props = obs.obs_properties_create()
    
    obs.obs_properties_add_button(props, "refresh_btn", "↻ Refresh Devices", refresh_pressed)
    
    p = obs.obs_properties_add_list(props, "device_list", "Select Device", obs.OBS_COMBO_TYPE_DROPDOWN, obs.OBS_COMBO_FORMAT_STRING)
    update_device_list(props)
    
    obs.obs_properties_add_button(props, "start_btn", "▶ Start DouWan Mirror", start_pressed)
    
    return props

def script_update(settings):
    global device_id
    device_id = obs.obs_data_get_string(settings, "device_list")

def script_description():
    return "DouWan Free — OBS Extension\n\n1. Ensure the DouWan Desktop app is running.\n2. Select your device and hit Start.\n3. Add a 'Window Capture' source for the mirroring window."
