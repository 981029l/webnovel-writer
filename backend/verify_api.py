import requests
import json

try:
    print("Testing /api/projects/list...")
    resp = requests.get('http://127.0.0.1:8080/api/projects/list', timeout=5)
    print(f"Status: {resp.status_code}")
    print(f"Content: {resp.text[:500]}") # Print first 500 chars
except Exception as e:
    print(f"Error: {e}")
