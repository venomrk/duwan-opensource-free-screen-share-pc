import mss
import pygetwindow as gw
import pyvirtualcam
import numpy as np
import cv2
import time
import threading
import os

class VirtualCameraManager:
    def __init__(self):
        self.active_vams = {}  # device_id -> {'running': bool, 'thread': Thread}
        self.lock = threading.Lock()

    def start_vcam(self, device_id, window_title):
        with self.lock:
            if device_id in self.active_vams and self.active_vams[device_id]['running']:
                return False, "Virtual camera already running for this device"
            
            self.active_vams[device_id] = {'running': True}
            thread = threading.Thread(target=self._vcam_loop, args=(device_id, window_title), daemon=True)
            self.active_vams[device_id]['thread'] = thread
            thread.start()
            return True, "Virtual camera starting..."

    def stop_vcam(self, device_id):
        with self.lock:
            if device_id in self.active_vams:
                self.active_vams[device_id]['running'] = False
                return True, "Stopping virtual camera..."
            return False, "No virtual camera running for this device"

    def _vcam_loop(self, device_id, window_title):
        print(f"[VCam] Starting loop for {window_title}")
        try:
            with mss.mss() as sct:
                cam = None
                while self.active_vams.get(device_id, {}).get('running'):
                    # 1. Find the window
                    windows = [w for w in gw.getWindowsWithTitle(window_title) if w.visible]
                    if not windows:
                        time.sleep(1)
                        continue
                    
                    win = windows[0]
                    if win.width <= 0 or win.height <= 0:
                        time.sleep(0.5)
                        continue

                    # 2. Setup Camera if not exists or size changed
                    if cam is None or cam.width != win.width or cam.height != win.height:
                        if cam:
                            cam.close()
                        try:
                            # Try to initialize virtual camera
                            # We use 30 FPS for streaming stability
                            cam = pyvirtualcam.Camera(width=win.width, height=win.height, fps=30, fmt=pyvirtualcam.PixelFormat.BGR)
                            print(f"[VCam] Camera initialized: {cam.device} ({win.width}x{win.height})")
                        except Exception as e:
                            print(f"[VCam] Initialization Error: {e}")
                            time.sleep(5)
                            continue

                    # 3. Capture and Send
                    monitor = {"top": win.top, "left": win.left, "width": win.width, "height": win.height}
                    try:
                        screenshot = np.array(sct.grab(monitor))
                        # MSS returns BGRA. Convert to BGR for the camera
                        frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
                        cam.send(frame)
                        cam.sleep_until_next_frame()
                    except Exception as e:
                        print(f"[VCam] Capture Error: {e}")
                        time.sleep(1)
                
                if cam:
                    cam.close()
        except Exception as e:
            print(f"[VCam] Fatal Error: {e}")
        finally:
            print(f"[VCam] Loop ended for {device_id}")

vcam_manager = VirtualCameraManager()
