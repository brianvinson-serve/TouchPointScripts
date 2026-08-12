#!/usr/bin/env python3
"""List all available OData entities"""

import requests
import json
import getpass

BASE_URL = "https://rockpointe.tpsdb.com"

username = input("Username: ")
password = getpass.getpass("Password: ")

session = requests.Session()
session.auth = (username, password)
session.headers.update({'Accept': 'application/json'})

resp = session.get(f"{BASE_URL}/api/", timeout=15)
data = resp.json()

print("\nAvailable OData Entities:")
print("="*40)
for item in data.get('value', []):
    print(f"  - {item['name']}")

# Try to query each one
print("\n\nTesting each entity...")
print("="*40)
for item in data.get('value', []):
    name = item['name']
    url = f"{BASE_URL}/api/{name}?$top=1"
    try:
        r = session.get(url, timeout=10)
        status = "✓" if r.status_code == 200 else f"✗ {r.status_code}"
        print(f"  {status} /api/{name}")
    except:
        print(f"  ✗ /api/{name} (timeout)")
