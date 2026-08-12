#!/usr/bin/env python3
"""
Quick test of the /APITask endpoint that we know works
"""

import requests
import json
import getpass

BASE_URL = "https://rockpointe.tpsdb.com"

username = input("Username: ")
password = getpass.getpass("Password: ")

session = requests.Session()
session.auth = (username, password)
session.headers.update({'Accept': 'application/json'})

# Test endpoints that showed as working
endpoints = [
    "/APITask",
    "/APITask/List",
    "/APITask/GetTasks",
    "/APIOrganization",
    "/APIOrganization/List",
    "/api/",  # Check what's in the base response
]

for endpoint in endpoints:
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'='*60}")
    print(f"GET {endpoint}")
    print('='*60)

    try:
        resp = session.get(url, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            # Try to parse as JSON
            try:
                data = resp.json()
                print(f"Type: {type(data)}")
                if isinstance(data, dict):
                    print(f"Keys: {list(data.keys())[:10]}")
                    # Print first few items if it's a list of tasks
                    for key in ['Tasks', 'tasks', 'value', 'Items', 'items']:
                        if key in data and isinstance(data[key], list):
                            print(f"\nFound {len(data[key])} items in '{key}':")
                            for item in data[key][:3]:
                                print(f"  {json.dumps(item, indent=2)[:300]}")
                            break
                    else:
                        print(json.dumps(data, indent=2)[:500])
                elif isinstance(data, list):
                    print(f"List with {len(data)} items")
                    for item in data[:3]:
                        print(f"  {json.dumps(item, indent=2)[:300]}")
            except:
                print(f"Response (not JSON): {resp.text[:500]}")
        else:
            print(f"Response: {resp.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

print("\n" + "="*60)
print("DONE")
print("="*60)
