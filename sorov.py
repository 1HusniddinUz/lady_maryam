import time
import requests

URL = "https://lady-maryam.onrender.com"  # bu yerga server URL qo'yasiz

while True:
    try:
        response = requests.get(URL)
        print(f"Ping yuborildi: {response.status_code}")
    except Exception as e:
        print(f"Xatolik: {e}")

    # 14 minut = 840 sekund
    time.sleep(840)
