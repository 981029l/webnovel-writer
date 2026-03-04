import requests
import json

url = "http://127.0.0.1:8080/api/ai/write"
data = {"chapter": 326, "word_count": 500}
headers = {"Content-Type": "application/json"}

print("Triggering /api/ai/write API for chapter 326...")
try:
    response = requests.post(url, json=data, headers=headers)
    print("Status:", response.status_code)
    try:
        res_data = response.json()
        print("Success:", res_data.get("success"))
        print("\n--- Extracted State ---")
        print(json.dumps(res_data.get("state_extracted"), indent=2, ensure_ascii=False))
        print("\n--- Summary ---")
        print(res_data.get("summary"))
    except:
        print(response.text)
except Exception as e:
    print("Request failed:", e)
