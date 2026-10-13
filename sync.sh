#!/usr/bin/env bash
# ==============================================================================
# n8n Workflow Synchronization & Git Automation Script
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

ACTION="${1:-export}"

# Check Docker
if ! docker ps | grep -q "n8n-n8n-1"; then
    echo "❌ کانتینر n8n-n8n-1 در حال اجرا نیست! ابتدا سرویس‌ها را با docker compose up -d اجرا کنید."
    exit 1
fi

case "$ACTION" in
    import)
        python3 scripts/sync_workflows.py import
        ;;
    list)
        python3 scripts/sync_workflows.py list
        ;;
    export)
        python3 scripts/sync_workflows.py export
        echo ""
        echo "💡 وضعیت تغییرات در گیت:"
        git status -s
        ;;
    *)
        # If the argument is a commit message
        COMMIT_MSG="$*"
        python3 scripts/sync_workflows.py export
        
        echo ""
        echo "📦 در حال آماده‌سازی و ثبت در گیت..."
        git add sync.sh workflows/ scripts/ compose.yml searxng-settings.yml .gitignore .env.example README.md 2>/dev/null || git add .
        
        if git diff --cached --quiet; then
            echo "ℹ️ هیچ تغییری در ورک‌فلوها یا کانفیگ‌ها نسبت به آخرین کامیت وجود نداشت."
        else
            git commit -m "$COMMIT_MSG"
            echo "✅ تغییرات با موفقیت در گیت کامیت شدند: \"$COMMIT_MSG\""
            
            # Check if remote exists
            if git remote | grep -q "origin"; then
                echo "🚀 در حال ارسال تغییرات به گیت‌هاب (git push)..."
                git push origin main || git push origin master || echo "⚠️ ارسال به گیت‌هاب انجام نشد. اتصال اینترنت یا دسترسی ریپازیتوری را بررسی کنید."
            else
                echo "💡 نکته: هنوز ریموت گیت‌هاب متصل نشده است. برای ارسال به گیت‌هاب از دستور زیر استفاده کنید:"
                echo "   git remote add origin https://github.com/USERNAME/REPO.git"
                echo "   git push -u origin main"
            fi
        fi
        ;;
esac
