import os
import sys
import socket
import threading
import webbrowser

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GG.settings")

# Make sure Python can find the project when run as a frozen .exe
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

import django
django.setup()

from waitress import serve
from GG.wsgi import application


def get_lan_ip():
    """Find this computer's LAN address automatically."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    ip = get_lan_ip()
    url = f"http://{ip}:8000"

    print("=" * 55)
    print(" GREEN GARDEN SERVER IS RUNNING")
    print("=" * 55)
    print(f" Other computers connect using: {url}")
    print(" Keep this window open while staff are using GG.")
    print(" Close this window to stop the system.")
    print("=" * 55)

    # Auto-open the homepage on THIS computer too
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    try:
        serve(application, host="0.0.0.0", port=8000, threads=8)
    except KeyboardInterrupt:
        print("\nServer stopped.")