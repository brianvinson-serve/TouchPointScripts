#!/usr/bin/env python3
"""
TouchPoint OData API Test Harness
For RockPointe Church - Student Ministry Task Notifications

This script tests API connectivity and validates our SQL logic
against the actual TouchPoint database.

Usage:
    python tp_api_test.py

Environment variables (optional):
    TP_USERNAME - Your TouchPoint username
    TP_PASSWORD - Your TouchPoint password
"""

import requests
import json
import os
import getpass
from urllib.parse import urljoin
from datetime import datetime

# Configuration
BASE_URL = "https://rockpointe.tpsdb.com"
API_BASE = f"{BASE_URL}/api/"

class TouchPointAPI:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

    def test_connection(self):
        """Test basic API connectivity"""
        print("\n" + "="*60)
        print("TESTING API CONNECTION")
        print("="*60)

        # Try a few different endpoint patterns
        endpoints_to_try = [
            "/api/",
            "/api/People?$top=1",
            "/api/TaskNote?$top=1",
            "/api/$metadata",
            "/APIPerson/MyInfo"
        ]

        for endpoint in endpoints_to_try:
            url = f"{BASE_URL}{endpoint}"
            print(f"\nTrying: {url}")
            try:
                response = self.session.get(url, timeout=10)
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"  ✓ SUCCESS")
                    if len(response.text) < 500:
                        print(f"  Response: {response.text[:500]}")
                    else:
                        print(f"  Response length: {len(response.text)} chars")
                    return True, endpoint
                elif response.status_code == 401:
                    print(f"  ✗ Unauthorized - check credentials")
                elif response.status_code == 403:
                    print(f"  ✗ Forbidden - may need different permissions")
                else:
                    print(f"  Response: {response.text[:200]}")
            except requests.exceptions.RequestException as e:
                print(f"  ✗ Error: {e}")

        return False, None

    def explore_endpoints(self):
        """Discover available API endpoints"""
        print("\n" + "="*60)
        print("EXPLORING AVAILABLE ENDPOINTS")
        print("="*60)

        # Common TouchPoint OData endpoints based on documentation
        endpoints = [
            "/api/People",
            "/api/TaskNote",
            "/api/Organizations",
            "/api/Meetings",
            "/api/Attendance",
            "/api/CheckInTimes",
            "/api/Contributions",
            "/APIPerson/MyInfo",
            "/APIOrganization",
            "/APITask"
        ]

        available = []
        for endpoint in endpoints:
            url = f"{BASE_URL}{endpoint}?$top=1"
            try:
                response = self.session.get(url, timeout=10)
                status = "✓" if response.status_code == 200 else f"✗ ({response.status_code})"
                print(f"  {status} {endpoint}")
                if response.status_code == 200:
                    available.append(endpoint)
            except:
                print(f"  ✗ {endpoint} (timeout/error)")

        return available

    def query_tasks(self):
        """Query TaskNote table to see outstanding tasks"""
        print("\n" + "="*60)
        print("QUERYING TASKNOTE TABLE")
        print("="*60)

        # Try to get tasks - filter for non-complete status
        # StatusId: 1=Complete, 2=Pending, 3=Active, 4=Declined, 5=Archived, 6=Cancelled

        queries = [
            # All tasks (limited)
            ("/api/TaskNote?$top=10", "First 10 tasks"),
            # Non-complete tasks
            ("/api/TaskNote?$filter=StatusId ne 1 and StatusId ne 5 and StatusId ne 6&$top=20",
             "Outstanding tasks (not complete/archived/cancelled)"),
            # With expansion
            ("/api/TaskNote?$expand=AboutPerson&$top=5",
             "Tasks with person details"),
        ]

        for endpoint, description in queries:
            url = f"{BASE_URL}{endpoint}"
            print(f"\n{description}")
            print(f"  URL: {endpoint}")

            try:
                response = self.session.get(url, timeout=15)
                print(f"  Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict) and 'value' in data:
                        tasks = data['value']
                        print(f"  Found {len(tasks)} tasks")
                        for i, task in enumerate(tasks[:5]):
                            print(f"\n  Task {i+1}:")
                            for key in ['Id', 'Description', 'StatusId', 'OwnerId', 'AssigneeId', 'CreatedDate', 'Instructions']:
                                if key in task:
                                    val = str(task[key])[:60]
                                    print(f"    {key}: {val}")
                    else:
                        print(f"  Response: {json.dumps(data, indent=2)[:500]}")
                else:
                    print(f"  Error: {response.text[:300]}")
            except Exception as e:
                print(f"  Error: {e}")

    def get_my_info(self):
        """Get current user info to verify identity"""
        print("\n" + "="*60)
        print("GETTING CURRENT USER INFO")
        print("="*60)

        endpoints = [
            "/APIPerson/MyInfo",
            "/api/People?$filter=Username eq '{}'".format(self.username),
        ]

        for endpoint in endpoints:
            url = f"{BASE_URL}{endpoint}"
            print(f"\nTrying: {endpoint}")
            try:
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    print(f"  ✓ Success")
                    data = response.json()
                    print(f"  {json.dumps(data, indent=2)[:800]}")
                    return data
                else:
                    print(f"  Status: {response.status_code}")
            except Exception as e:
                print(f"  Error: {e}")

        return None

    def test_sql_logic(self):
        """Test our SQL query logic against real data"""
        print("\n" + "="*60)
        print("VALIDATING SQL LOGIC")
        print("="*60)

        # Our SQL looks for:
        # - StatusId 2 (Pending), 3 (Active), 4 (Declined)
        # - Excluding StatusId 1 (Complete), 5 (Archived), 6 (Cancelled)
        # - Excluding "New Person Data Entry" tasks

        url = f"{BASE_URL}/api/TaskNote?$filter=(StatusId eq 2 or StatusId eq 3 or StatusId eq 4)&$top=50"

        print(f"\nQuerying outstanding tasks...")
        print(f"Filter: StatusId in (2=Pending, 3=Active, 4=Declined)")

        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                tasks = data.get('value', [])

                # Filter out "New Person Data Entry" locally
                filtered = [t for t in tasks if 'New Person Data Entry' not in str(t.get('Instructions', ''))]

                print(f"\n  Total tasks matching status filter: {len(tasks)}")
                print(f"  After excluding 'New Person Data Entry': {len(filtered)}")

                # Group by owner/assignee
                owners = {}
                for task in filtered:
                    owner_id = task.get('OwnerId')
                    assignee_id = task.get('AssigneeId')
                    responsible = assignee_id if assignee_id else owner_id
                    if responsible:
                        owners[responsible] = owners.get(responsible, 0) + 1

                print(f"\n  People with outstanding tasks: {len(owners)}")
                for pid, count in sorted(owners.items(), key=lambda x: -x[1])[:10]:
                    print(f"    PeopleId {pid}: {count} tasks")

                return filtered
            else:
                print(f"  Status: {response.status_code}")
                print(f"  Response: {response.text[:300]}")
        except Exception as e:
            print(f"  Error: {e}")

        return []

    def run_full_test(self):
        """Run complete test suite"""
        print("\n" + "="*60)
        print("TOUCHPOINT API TEST HARNESS")
        print(f"Target: {BASE_URL}")
        print(f"User: {self.username}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        # Test connection
        connected, endpoint = self.test_connection()

        if not connected:
            print("\n⚠️  Could not establish API connection.")
            print("Possible issues:")
            print("  - Invalid credentials")
            print("  - APIOnly role may not have access to these endpoints")
            print("  - Network/firewall blocking")
            return

        # Explore endpoints
        available = self.explore_endpoints()

        # Get user info
        self.get_my_info()

        # Query tasks
        if "/api/TaskNote" in available or any("Task" in e for e in available):
            self.query_tasks()
            self.test_sql_logic()
        else:
            print("\n⚠️  TaskNote endpoint not available with current permissions")

        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)


def main():
    print("TouchPoint API Test Harness")
    print("-" * 40)

    # Get credentials
    username = os.environ.get('TP_USERNAME')
    password = os.environ.get('TP_PASSWORD')

    if not username:
        username = input("TouchPoint Username: ")
    if not password:
        password = getpass.getpass("TouchPoint Password: ")

    if not username or not password:
        print("Error: Username and password required")
        return

    # Run tests
    api = TouchPointAPI(username, password)
    api.run_full_test()


if __name__ == "__main__":
    main()
