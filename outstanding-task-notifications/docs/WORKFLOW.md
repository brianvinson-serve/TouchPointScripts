# TouchPoint Development Workflow for RockPointe Church

## Overview

This document outlines the complete workflow for developing, testing, and deploying custom TouchPoint scripts for RockPointe Church, specifically for the Student Ministry task notification system.

## Project Background

**Request:** Max McCalley needs email notifications for incomplete Student Ministry "Tasks" in TouchPoint.

**Solution:** Adapted scripts from TenthPres church (GitHub: TenthPres/TouchPointScripts) to send automated email reminders to SM staff about outstanding tasks.

## Project Structure

```
touchpoint-dev/
├── scripts/
│   ├── original/           # TenthPres original scripts (reference)
│   │   ├── OutstandingTasksList.py
│   │   ├── OutstandingTaskNotifications.py
│   │   └── TaskNote-ToDo.sql
│   └── rockpointe/         # RockPointe adapted scripts
│       ├── SM_OutstandingTasksList.py
│       ├── SM_OutstandingTaskNotifications.py
│       └── SM_TaskNote-ToDo.sql
├── templates/
│   ├── OutstandingTasksReminderEmail.md      # Original template
│   └── SM_OutstandingTasksReminderEmail.md   # RockPointe template
├── automation/
│   └── deploy_scripts.sh   # Deployment helper script
└── docs/
    ├── WORKFLOW.md         # This file
    └── CHROME_AUTOMATION.md
```

## Key Components

### 1. SM_TaskNote-ToDo.sql
**Purpose:** Identifies users who have outstanding tasks
**Deployment:** Admin > Advanced > Special Content > SQL Scripts

### 2. SM_OutstandingTasksList.py
**Purpose:** Generates HTML list of tasks for each user (used in email)
**Deployment:** Admin > Advanced > Special Content > Python Scripts

### 3. SM_OutstandingTasksReminder (Email Template)
**Purpose:** Email body template with personalization
**Deployment:** Admin > Emails > Saved Drafts

### 4. SM_OutstandingTaskNotifications.py
**Purpose:** Orchestrates sending emails to all users with tasks
**Deployment:** Admin > Advanced > Special Content > Python Scripts

## Development Workflow

### Phase 1: Local Development

1. **Edit scripts locally** in `scripts/rockpointe/`
2. **Validate syntax:**
   ```bash
   ./automation/deploy_scripts.sh validate
   ```
3. **Review changes:**
   ```bash
   ./automation/deploy_scripts.sh diff
   ```

### Phase 2: Deployment via Chrome

Use Claude in Chrome to navigate TouchPoint and deploy scripts:

1. **Login to TouchPoint:**
   - Navigate to your RockPointe TouchPoint instance
   - Ensure you're logged in with Developer/SpecialContentFull roles

2. **Deploy SQL Script:**
   - Go to Admin > Advanced > Special Content
   - Click SQL Scripts tab
   - Click +New SQL Script File
   - Name: `SM_TaskNote-ToDo`
   - Paste SQL content
   - Save

3. **Deploy Python Scripts:**
   - Click Python Scripts tab
   - For each .py file:
     - Click +New Python Script File
     - Enter name (without .py extension)
     - Paste script content
     - Save

4. **Create Email Template:**
   - Go to Admin > Emails > Saved Drafts
   - Create new with name: `SM_OutstandingTasksReminder`
   - Set format to Markdown
   - Paste template content
   - Save

### Phase 3: Testing

1. **Test Task List Script:**
   - Navigate to the Python script
   - Click Run/Test
   - Verify HTML output looks correct

2. **Test Email (Single Recipient):**
   - Modify notification script temporarily:
     ```python
     # Change recipient search to just yourself
     recipientSearch = "PeopleId = YOUR_PEOPLE_ID"
     ```
   - Run the notification script
   - Check your email

3. **Test Full System:**
   - Restore original recipient search
   - Run notification script
   - Verify emails sent to correct recipients

### Phase 4: Scheduling

Add to TouchPoint's MorningBatch or ScheduledTasks script:

```python
# Send every Tuesday morning
if model.DayOfWeek == 2:
    model.CallScript('SM_OutstandingTaskNotifications')
```

Or for specific time control:

```python
# Send Tuesdays at 7pm
if model.ScheduledTime == "1900" and model.DayOfWeek == 2:
    print(model.CallScript('SM_OutstandingTaskNotifications'))
```

## Configuration Notes

### Values to Update Before Deployment

In `SM_OutstandingTaskNotifications.py`:
- `FROM_EMAIL` - Student Ministry email address
- `FROM_NAME` - Sender display name
- `QUEUED_BY` - PeopleId whose record the email is queued under; current local default is Joseph McCalley (`23164`).

In `SM_TaskNote-ToDo.sql`:
- Keep the hardcoded SM staff PeopleId list synchronized with `DB_REFERENCE.md` until the focused involvement-role check confirms a maintained long-term source of truth.
- Do not filter to `MemberTypeId = 220` as though it means leader; RPC lookup evidence says 220 = Member globally and 140 = Leader.

In `SM_OutstandingTasksReminderEmail.md`:
- Update dashboard link with actual SM organization ID
- Customize messaging as needed

## Key TouchPoint Concepts

### TaskNote Status IDs
Confirmed for RPC `TaskNote.StatusId` values:
- 1 = Complete
- 2 = Pending
- 3 = Active / accepted
- 4 = Declined
- 5 = Archived / note history

Do not join `TaskNote.StatusId` to `lookup.TaskStatus`; that lookup uses 10-70 and does not map to TaskNote rows.

### Email Template Tags
- `{first}` - Recipient's first name
- `{last}` - Recipient's last name
- `{cmshost}` - TouchPoint base URL
- `{pythonscript:ScriptName}` - Embed Python script output

### Required Roles
- **Developer** - Access to Special Content Python scripts
- **APIOnly** - API access (if using OData)
- **SpecialContentFull** - Full access to all Special Content tabs

## Troubleshooting

### Script Won't Save
- Check for Python syntax errors
- Verify you have SpecialContentFull role

### Emails Not Sending
- Verify email template name matches exactly
- Check QUEUED_BY PeopleId is valid and allowed to queue this email
- Verify SQL script returns recipients

### No Tasks Showing
- Check TaskNote table has data
- Verify status IDs in SQL match your needs
- Test SQL directly in TouchPoint's SQL tool

## Resources

- [TouchPoint Python Documentation](https://docs.touchpointsoftware.com/CustomProgramming/Python/index.html)
- [TouchPoint Special Content](https://docs.touchpointsoftware.com/Administration/Display_Index.html)
- [TenthPres Scripts Repository](https://github.com/TenthPres/TouchPointScripts)

## Contact

**Project Owner:** Brian Vinson (brian.vinson@gmail.com)
**RockPointe Contacts:**
- Jessica Siri - Director of Operations
- Marlene Godinez - Senior TouchPoint Associate
- Jay Hough - Web Developer
- Max McCalley - Student Ministry (end user)
