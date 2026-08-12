# Chrome Automation Guide for TouchPoint Deployment

## Overview

This guide explains how to use Claude in Chrome to automate deploying TouchPoint scripts. This is the fastest way to get scripts from your local development environment into TouchPoint.

## Prerequisites

1. **Claude in Chrome Extension** installed and active
2. **TouchPoint Access** with Developer/SpecialContentFull roles
3. **Scripts ready** in `scripts/rockpointe/` directory

## Deployment Commands for Claude

### Step 1: Login and Navigate

Ask Claude:
```
Navigate to [your-church].tpsdb.com and help me log in.
Then go to Admin > Advanced > Special Content.
```

### Step 2: Deploy SQL Script

Ask Claude:
```
I need to create a new SQL script in TouchPoint.
1. Click on the SQL Scripts tab
2. Click +New SQL Script File
3. Name it: SM_TaskNote-ToDo
4. I'll paste the content for you to enter

Here's the SQL content:
[paste your SQL script content]
```

### Step 3: Deploy Python Scripts

Ask Claude:
```
Now let's deploy the Python scripts.
1. Click on the Python Scripts tab
2. Click +New Python Script File
3. Name it: SM_OutstandingTasksList
4. Enter this code:

[paste your Python script content]
```

Repeat for each Python script.

### Step 4: Create Email Template

Ask Claude:
```
Navigate to Admin > Emails > Saved Drafts.
Create a new saved draft with:
- Name: SM_OutstandingTasksReminder
- Format: Markdown
- Body: [paste template content]
```

## Automated Workflow Script

You can create a workflow in Claude that combines all these steps:

```
Help me deploy my TouchPoint Student Ministry scripts.

I have these files to deploy:
1. SQL Script: SM_TaskNote-ToDo.sql
2. Python Script: SM_OutstandingTasksList.py
3. Python Script: SM_OutstandingTaskNotifications.py
4. Email Template: SM_OutstandingTasksReminderEmail.md

Please:
1. Navigate to TouchPoint Special Content
2. Deploy each script in order
3. Verify each deployment was successful
4. Create the email template
5. Give me a summary of what was deployed
```

## Testing via Chrome

### Test Task List Output

Ask Claude:
```
Navigate to the SM_OutstandingTasksList Python script in Special Content.
Run/test the script and show me the output.
```

### Send Test Email

Ask Claude:
```
Navigate to the SM_OutstandingTaskNotifications Python script.
Before running, let's modify it to only send to me for testing.
Then run it and check if I received the email.
```

## Updating Scripts

When you make changes locally:

```
I've updated SM_OutstandingTasksList.py locally.
Please:
1. Navigate to this script in TouchPoint Special Content
2. Replace the existing content with my updated version
3. Save the changes

Here's the new content:
[paste updated script]
```

## Bulk Operations

For deploying multiple scripts at once:

```
I need to update several TouchPoint scripts. Please help me:

1. Navigate to Special Content > Python Scripts
2. For each script I provide, either update it if it exists or create it new
3. Confirm each script saves successfully

Scripts to deploy:
- SM_OutstandingTasksList.py: [content]
- SM_OutstandingTaskNotifications.py: [content]
```

## Rollback Procedure

If something goes wrong:

```
The SM_OutstandingTasksList.py script is causing issues.
Please:
1. Navigate to the script in Special Content
2. Replace it with this previous working version:
[paste previous version]
```

## Verification Checklist

After deployment, ask Claude to verify:

```
Please verify my TouchPoint deployment:

1. Check Special Content > SQL Scripts for SM_TaskNote-ToDo
2. Check Special Content > Python Scripts for:
   - SM_OutstandingTasksList
   - SM_OutstandingTaskNotifications
3. Check Emails > Saved Drafts for SM_OutstandingTasksReminder
4. Report what you find for each
```

## Tips for Smooth Automation

1. **Copy script content to clipboard** before starting Claude session
2. **Have TouchPoint open** in a dedicated Chrome window
3. **Use specific navigation commands** like "Admin > Advanced > Special Content"
4. **Verify after each step** before moving to next
5. **Keep original scripts backed up** locally

## Common Issues

### "Script name already exists"
- Ask Claude to find and update the existing script instead

### "Permission denied"
- Verify your TouchPoint roles include Developer and SpecialContentFull

### "Python syntax error"
- Run `./automation/deploy_scripts.sh validate` locally first

### "Email template not found"
- Ensure the template name matches exactly (case-sensitive)
- Check it's in Saved Drafts, not a different email section
