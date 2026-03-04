
import requests
import json
import sys

def test_init_stream():
    url = "http://localhost:8080/api/ai/init-stream"
    payload = {
        "title": "测试项目",
        "genre": "玄幻",
        "protagonist_name": "龙傲天",
        "golden_finger_name": "系统",
        "golden_finger_type": "系统面板",
        "additional_info": "无",
        "mode": "standard"
    }
    
    print(f"Connecting to {url}...")
    try:
        with requests.post(url, json=payload, stream=True) as response:
            print(f"Status Code: {response.status_code}")
            if response.status_code != 200:
                print("Error Response:", response.text)
                return

            print("Reading stream...")
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    print(f"Received: {decoded_line}")
                    if decoded_line.startswith("data: "):
                        try:
                            data = json.loads(decoded_line[6:])
                            print(f"Parsed JSON type: {data.get('type')}")
                        except json.JSONDecodeError as e:
                            print(f"JSON Decode Error: {e}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_init_stream()
