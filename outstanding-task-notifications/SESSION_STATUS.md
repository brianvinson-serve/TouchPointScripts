# TouchPoint Dev Project - Session Status
**Last Updated:** January 31, 2026

## GitHub Repository
**URL:** https://github.com/brianvinson-serve/TouchPointScripts
**Profile:** https://github.com/brianvinson-serve

## Current Status: WAITING ON ACCESS + NEED TO PUSH CODE

### Waiting on Marlene:
- Separate dev account with Developer, SpecialContentFull roles, normal web login (NOT APIOnly)
- Email sent with technical justification

### Ready to push to GitHub:
Scripts are ready locally, need to push to repo (requires `gh auth login` first)

---

## What's Been Done (Jan 31, 2026)

### 1. Scripts Adapted & Ready to Deploy
All in `/scripts/rockpointe/`:
- `SM_TaskNote-ToDo.sql` - Identifies users with outstanding tasks
- `SM_OutstandingTasksList.py` - Generates formatted task list HTML
- `SM_OutstandingTaskNotifications.py` - Sends the emails (needs config updates)
- Email template in `/templates/SM_OutstandingTasksReminderEmail.md`

### 2. API Testing Completed
**Finding:** APIOnly role gives OData access but TaskNote isn't exposed via API.

Working entities: People, Organizations, OrganizationMembers, Contributions, Transactions, Pledges

NOT available via API: TaskNote (not in entity list), Meetings (500 error)

**Conclusion:** Must deploy Python scripts via web UI - can't use API for task notifications.

### 3. GitHub Setup Complete
- Profile created: `brianvinson-serve`
- Bio: Church tech volunteer, TouchPoint scripts, Resultant day job
- Repository created: `TouchPointScripts` (public, MIT license, Python gitignore)
- README written and ready: `/github_readme.md`

### 4. Documentation Created
- `docs/WORKFLOW.md` - Full deployment workflow
- `docs/CHROME_AUTOMATION.md` - How to use Claude in Chrome to deploy
- `README.md` - Quick reference
- `api_test/` - Test scripts for API exploration

---

## Next Steps

### Immediate (Next Session):
1. Push code to GitHub:
   ```bash
   brew install gh
   gh auth login
   cd /Users/bvinson/AnthMCP/90_TouchPoint_Dev
   git clone https://github.com/brianvinson-serve/TouchPointScripts.git
   cd TouchPointScripts
   cp ../scripts/rockpointe/*.py .
   cp ../scripts/rockpointe/*.sql .
   cp ../templates/SM_OutstandingTasksReminderEmail.md .
   cp ../github_readme.md README.md
   git add .
   git commit -m "Add Student Ministry task notification scripts"
   git push
   ```

### Once Marlene Grants Access:
1. Log into TouchPoint with new dev account
2. Deploy scripts in order (SQL → Python → Email template)
3. Test with single recipient
4. Schedule weekly sends
5. Notify Max McCalley

---

## Key Contacts at RockPointe

- **Marlene Godinez** - Senior TouchPoint Associate (manages roles)
- **Jessica Siri** - Director of Operations
- **Jay Hough** - Web Developer
- **Max McCalley** - Student Ministry (end user for task notifications)

---

## To Resume This Project

In new Cowork thread, say:
> "Continue TouchPoint dev project - give you access to /Users/bvinson/AnthMCP/90_TouchPoint_Dev and read SESSION_STATUS.md"
