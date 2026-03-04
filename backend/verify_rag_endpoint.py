import requests
import sys

def test_endpoint():
    try:
        url = "http://localhost:8080/api/rag/index/all"
        print(f"Testing POST {url}...")
        response = requests.post(url)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_endpoint()
