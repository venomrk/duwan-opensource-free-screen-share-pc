import webview
import threading
import sys
import os

# Import the Flask app
from app import app

def start_server():
    # Start the Flask app in a background thread
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Start the Flask server
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Create and start the PyWebview window
    # Wait a tiny bit to ensure Flask is up
    import time
    time.sleep(1)

    window = webview.create_window(
        'DouWan Free - Open Source Mirroring',
        'http://127.0.0.1:5000',
        width=1280, 
        height=800, 
        min_size=(900, 600),
        background_color='#f8f9fc'
    )
    
    # Start the webview application loop
    webview.start(private_mode=False)
