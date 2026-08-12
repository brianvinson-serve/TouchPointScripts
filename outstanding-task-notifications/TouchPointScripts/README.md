# TouchPointScripts

Python scripts, SQL queries, and automation tools for [TouchPoint ChMS](https://www.touchpointsoftware.com/). Helping churches leverage their data for ministry.

## 🙏 About This Project

This is a collection of scripts I'm developing as a volunteer to help churches get more out of their TouchPoint church management system. Scripts are shared freely for other churches to use and adapt.

**Inspired by:** [TenthPres/TouchPointScripts](https://github.com/TenthPres/TouchPointScripts) - huge thanks to their team for sharing their work!

## 📁 Current Scripts

### Student Ministry Task Notifications
Automated email reminders for ministry staff about incomplete tasks.

| File | Type | Description |
|------|------|-------------|
| `SM_TaskNote-ToDo.sql` | SQL | Identifies users with outstanding tasks |
| `SM_OutstandingTasksList.py` | Python | Generates formatted HTML task list |
| `SM_OutstandingTaskNotifications.py` | Python | Sends reminder emails |
| `SM_OutstandingTasksReminderEmail.md` | Template | Email body content |

## 🚀 Deployment

### Prerequisites
- TouchPoint account with **Developer** and **SpecialContentFull** roles
- Access to Admin > Advanced > Special Content

### Installation Order
1. **SQL Script:** Admin > Special Content > SQL Scripts > +New
   - Name: `SM_TaskNote-ToDo`

2. **Python Script:** Admin > Special Content > Python Scripts > +New
   - Name: `SM_OutstandingTasksList`

3. **Email Template:** Admin > Emails > Saved Drafts
   - Name: `SM_OutstandingTasksReminder`
   - Include `{pythonscript:SM_OutstandingTasksList}` in body

4. **Python Script:** Admin > Special Content > Python Scripts > +New
   - Name: `SM_OutstandingTaskNotifications`

### Configuration Required
Edit `SM_OutstandingTaskNotifications.py` before deploying:
```python
FROM_EMAIL = "your-ministry@yourchurch.org"
FROM_NAME = "Your Church Ministry"
QUEUED_BY_ID = 0  # Get from TouchPoint admin
```

### Scheduling
Add to your `MorningBatch` or `ScheduledTasks` script:
```python
# Send every Tuesday morning
if model.DayOfWeek == 2:
    model.CallScript('SM_OutstandingTaskNotifications')
```

## 📚 Resources

- [TouchPoint Python Documentation](https://docs.touchpointsoftware.com/CustomProgramming/Python/index.html)
- [TouchPoint Special Content](https://docs.touchpointsoftware.com/Administration/Display_Index.html)
- [TenthPres Scripts](https://github.com/TenthPres/TouchPointScripts) - More examples!

## 🤝 Contributing

Found a bug? Have an improvement? PRs welcome! This is a volunteer project aimed at helping churches.

## 📄 License

MIT License - Use freely, modify as needed, share with other churches!

---

*Built with ❤️ for the local church*
