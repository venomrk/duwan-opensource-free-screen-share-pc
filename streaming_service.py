import subprocess
import threading
import os
import signal

class MultistreamService:
    def __init__(self):
        self.process = None
        self.running = False
        self.lock = threading.Lock()

    def start_stream(self, scrcpy_proc, platforms):
        """
        scrcpy_proc: The Popen object of scrcpy (must be started with --record=- --record-format=matroska)
        platforms: List of dictionaries [{'url': '...', 'key': '...'}]
        """
        with self.lock:
            if self.running:
                return False, "Stream already running"

            # Construct the 'tee' output for FFmpeg
            outputs = []
            for p in platforms:
                full_url = f"{p['url'].rstrip('/')}/{p['key']}"
                outputs.append(f"[f=flv]{full_url}")
            
            tee_string = "|".join(outputs)
            
            # FFmpeg command
            # -i pipe:0 -> read from scrcpy stdout
            # -c:v copy -c:a copy -> no re-encoding (ultra lightweight)
            # -f tee -> output to multiple places
            ffmpeg_cmd = [
                "ffmpeg", "-i", "pipe:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", 
                "-f", "tee", "-map", "0", tee_string
            ]

            try:
                self.process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdin=scrcpy_proc.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )
                self.running = True
                # Start a thread to monitor the process
                threading.Thread(target=self._monitor, daemon=True).start()
                return True, "Streaming started!"
            except Exception as e:
                return False, f"FFmpeg Error: {e}"

    def stop_stream(self):
        with self.lock:
            if self.process:
                self.process.terminate()
                self.process = None
            self.running = False
            return True, "Streaming stopped."

    def _monitor(self):
        if self.process:
            stdout, stderr = self.process.communicate()
            print(f"[Streaming] FFmpeg exited. Stderr: {stderr.decode()[:500]}")
            self.running = False

streaming_service = MultistreamService()
