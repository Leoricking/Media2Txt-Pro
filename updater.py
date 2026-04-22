import requests, subprocess, sys

VERSION = "1.0.0"
UPDATE_URL = "https://example.com/version.json"  # 你之後自己放

def check_update():
    try:
        data = requests.get(UPDATE_URL, timeout=3).json()
        if data["version"] != VERSION:
            return data["url"]
    except:
        pass
    return None

def apply_update(url):
    r = requests.get(url)
    with open("update.exe", "wb") as f:
        f.write(r.content)
    subprocess.Popen("update.exe")
    sys.exit()