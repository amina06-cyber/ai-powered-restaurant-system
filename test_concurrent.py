import threading
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8000"
reservation_time = (datetime.now() + timedelta(days=1)).isoformat()

payload = {
    "customer_name": "Race Test",
    "customer_phone": "03001112222",
    "table_id": 2,
    "reservation_time": reservation_time,
    "party_size": 3
}

results = []

def make_request(label):
    response = requests.post(f"{BASE_URL}/reservations", json=payload)
    results.append((label, response.status_code, response.json()))

t1 = threading.Thread(target=make_request, args=("Request A",))
t2 = threading.Thread(target=make_request, args=("Request B",))

t1.start()
t2.start()

t1.join()
t2.join()

print("\n--- RESULTS ---")
for label, status, body in results:
    print(f"{label} -> HTTP {status}")
    print(json.dumps(body, indent=2))
    print()