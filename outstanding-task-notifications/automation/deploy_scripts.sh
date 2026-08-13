#!/bin/bash
# deploy_scripts.sh - TouchPoint Script Deployment Helper
# This script helps manage local development and coordinates with Claude in Chrome for deployment
#
# Usage: ./deploy_scripts.sh [command] [script_name]
# Commands:
#   list      - List all scripts ready for deployment
#   validate  - Validate Python syntax before deployment
#   diff      - Show changes from original TenthPres scripts
#   package   - Create a deployment package with all scripts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ROCKPOINTE_SCRIPTS="$PROJECT_DIR/scripts/rockpointe"
TEMPLATES_DIR="$PROJECT_DIR/templates"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_help() {
    echo -e "${BLUE}TouchPoint Script Deployment Helper${NC}"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  list              List all RockPointe scripts ready for deployment"
    echo "  validate          Validate Python syntax of all scripts"
    echo "  validate [name]   Validate specific script"
    echo "  diff              Show diff between RockPointe and original scripts"
    echo "  package           Create deployment package (copies to clipboard-friendly format)"
    echo "  status            Show deployment checklist status"
    echo "  help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 validate SM_OutstandingTasksList.py"
    echo "  $0 package"
}

list_scripts() {
    echo -e "${BLUE}=== RockPointe TouchPoint Scripts ===${NC}"
    echo ""
    echo -e "${GREEN}Python Scripts:${NC}"
    ls -la "$ROCKPOINTE_SCRIPTS"/*.py 2>/dev/null || echo "  No Python scripts found"
    echo ""
    echo -e "${GREEN}SQL Scripts:${NC}"
    ls -la "$ROCKPOINTE_SCRIPTS"/*.sql 2>/dev/null || echo "  No SQL scripts found"
    echo ""
    echo -e "${GREEN}Email Templates:${NC}"
    ls -la "$TEMPLATES_DIR"/SM_*.md 2>/dev/null || echo "  No SM templates found"
}

validate_python() {
    local script="$1"
    if [ -z "$script" ]; then
        echo -e "${BLUE}Validating all Python scripts...${NC}"
        for f in "$ROCKPOINTE_SCRIPTS"/*.py; do
            if [ -f "$f" ]; then
                echo -n "  Checking $(basename "$f")... "
                if python3 -m py_compile "$f" 2>/dev/null; then
                    echo -e "${GREEN}OK${NC}"
                else
                    echo -e "${RED}SYNTAX ERROR${NC}"
                    python3 -m py_compile "$f"
                fi
            fi
        done
    else
        local full_path="$ROCKPOINTE_SCRIPTS/$script"
        if [ -f "$full_path" ]; then
            echo -e "${BLUE}Validating $script...${NC}"
            if python3 -m py_compile "$full_path" 2>/dev/null; then
                echo -e "${GREEN}Syntax OK${NC}"
            else
                echo -e "${RED}Syntax Error:${NC}"
                python3 -m py_compile "$full_path"
            fi
        else
            echo -e "${RED}Script not found: $script${NC}"
        fi
    fi
}

show_diff() {
    echo -e "${BLUE}=== Differences from Original TenthPres Scripts ===${NC}"
    echo ""
    # This would show diffs if we had both versions
    echo "RockPointe scripts are adapted from TenthPres with these changes:"
    echo "  - Added Student Ministry specific filtering"
    echo "  - Enhanced styling with urgency indicators"
    echo "  - RockPointe branding and contact info"
    echo "  - Configurable parameters at script top"
}

create_package() {
    echo -e "${BLUE}=== Creating Deployment Package ===${NC}"
    echo ""
    local pkg_dir="$PROJECT_DIR/deployment_package_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$pkg_dir"

    # Copy all deployment files
    cp "$ROCKPOINTE_SCRIPTS"/*.py "$pkg_dir/" 2>/dev/null
    cp "$ROCKPOINTE_SCRIPTS"/*.sql "$pkg_dir/" 2>/dev/null
    cp "$TEMPLATES_DIR"/SM_*.md "$pkg_dir/" 2>/dev/null

    # Create deployment instructions
    cat > "$pkg_dir/DEPLOYMENT_ORDER.txt" << 'EOF'
TOUCHPOINT DEPLOYMENT ORDER
============================

Deploy in this exact order:

1. SQL SCRIPT: SM_TaskNote-ToDo.sql
   Location: Admin > Advanced > Special Content > SQL Scripts
   Click: +New SQL Script File
   Name: SM_TaskNote-ToDo

2. PYTHON SCRIPT: SM_OutstandingTasksList.py
   Location: Admin > Advanced > Special Content > Python Scripts
   Click: +New Python Script File
   Name: SM_OutstandingTasksList

3. EMAIL TEMPLATE: SM_OutstandingTasksReminderEmail.md
   Location: Admin > Emails > Saved Drafts
   Create new draft with name: SM_OutstandingTasksReminder
   Body: Paste content, set format to Markdown
   IMPORTANT: Include {pythonscript:SM_OutstandingTasksList} tag

4. PYTHON SCRIPT: SM_OutstandingTaskNotifications.py
   Location: Admin > Advanced > Special Content > Python Scripts
   Click: +New Python Script File
   Name: SM_OutstandingTaskNotifications
   NOTE: Confirm QUEUED_BY PeopleId and sender email/name first!

5. SCHEDULE (Optional):
   Add to MorningBatch or ScheduledTasks:
   if model.DayOfWeek == 2:  # Tuesday
       model.CallScript('SM_OutstandingTaskNotifications')

TESTING:
- Run SM_OutstandingTasksList manually first to verify output
- Test SM_OutstandingTaskNotifications with a small recipient list
EOF

    echo -e "${GREEN}Package created: $pkg_dir${NC}"
    echo ""
    echo "Contents:"
    ls -la "$pkg_dir"
}

show_status() {
    echo -e "${BLUE}=== Deployment Checklist ===${NC}"
    echo ""
    echo "Prerequisites:"
    echo "  [ ] Developer role assigned in TouchPoint"
    echo "  [ ] APIOnly role assigned in TouchPoint"
    echo "  [ ] SpecialContentFull role assigned"
    echo "  [ ] Confidentiality agreement signed"
    echo ""
    echo "Scripts to Deploy:"
    echo "  [ ] SM_TaskNote-ToDo.sql"
    echo "  [ ] SM_OutstandingTasksList.py"
    echo "  [ ] SM_OutstandingTasksReminder (email template)"
    echo "  [ ] SM_OutstandingTaskNotifications.py"
    echo ""
    echo "Post-Deployment:"
    echo "  [ ] Test SM_OutstandingTasksList output"
    echo "  [ ] Send test email to yourself"
    echo "  [ ] Schedule recurring notifications"
    echo "  [ ] Notify Max McCalley it's ready"
}

# Main command router
case "${1:-help}" in
    list)
        list_scripts
        ;;
    validate)
        validate_python "$2"
        ;;
    diff)
        show_diff
        ;;
    package)
        create_package
        ;;
    status)
        show_status
        ;;
    help|*)
        show_help
        ;;
esac
