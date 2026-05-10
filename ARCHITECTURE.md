# DouWan Free Architecture

## Core Engine
- **scrcpy**: High-performance screen mirroring via ADB.
- **Flask**: Backend API for device discovery and session management.
- **PyWebview**: Desktop wrapper for the management dashboard.

## OBS / Streamlabs Extension
- **douwan_obs_extension.py**: A native Python script for OBS Studio and Streamlabs Desktop.
- **Workflow**:
    1. The script connects to the local DouWan API (Port 5000).
    2. Streamers select their phone directly in the OBS 'Scripts' panel.
    3. Clicking 'Start' launches a borderless mirroring window.
    4. OBS captures this window automatically or uses the Virtual Camera feed.

## Multistreaming Engine
- **FFmpeg**: Uses the `tee` muxer to push a single mirrored feed to multiple RTMP ingest points (YouTube, Twitch, TikTok, etc.).
- **Virtual Camera**: loopback video device support via `pyvirtualcam`.
