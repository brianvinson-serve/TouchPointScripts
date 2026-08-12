# TouchPoint Development - RockPointe Church

Local development environment for TouchPoint scripts and automation.

## Projects

| Directory | Description |
|-----------|-------------|
| `outstanding-task-notifications/` | SM staff outstanding task email notification system |
| `attendance-dashboard/` | Attendance reporting dashboard |

## Quick Start

### Outstanding Task Notifications
```bash
cd outstanding-task-notifications
./automation/deploy_scripts.sh status
./automation/deploy_scripts.sh validate
```

### API Testing
```bash
cd outstanding-task-notifications/api_test
python3 tp_api_test.py
```
