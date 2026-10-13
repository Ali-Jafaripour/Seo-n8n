#!/usr/bin/env python3
"""
n8n Workflow Synchronizer & Git Helper
Allows 2-way sync between running n8n Docker container and local Git repository.
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path

CONTAINER_NAME = "n8n-n8n-1"
BASE_DIR = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = BASE_DIR / "workflows"


def sanitize_filename(name: str) -> str:
    """Sanitize workflow name to create safe, readable file names."""
    if not name:
        name = "unnamed_workflow"
    # Replace dangerous filesystem characters with underscore
    clean = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    # Normalize consecutive spaces
    clean = re.sub(r"\s+", " ", clean)
    return clean


def get_docker_workflows():
    """Fetch all workflows directly from the running n8n Docker container."""
    cmd = ["docker", "exec", CONTAINER_NAME, "n8n", "export:workflow", "--all"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ خطا در ارتباط با کانتینر داکر ({CONTAINER_NAME}):", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ خطا در پارس خروجی JSON از n8n: {e}", file=sys.stderr)
        sys.exit(1)


def export_workflows():
    """Export workflows from n8n into readable JSON files in the workflows/ directory."""
    print("🔄 در حال استخراج ورک‌فلوها از داکر...")
    workflows = get_docker_workflows()
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)

    # Track exported filenames to remove deleted workflows
    exported_files = set()
    summary_list = []

    for wf in workflows:
        wf_id = wf.get("id", "unknown")
        wf_name = wf.get("name", "Unnamed")
        is_active = wf.get("active", False)
        nodes_count = len(wf.get("nodes", []))

        filename = f"{sanitize_filename(wf_name)}.json"
        filepath = WORKFLOWS_DIR / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
            f.write("\n")

        exported_files.add(filename)
        summary_list.append({
            "name": wf_name,
            "id": wf_id,
            "file": filename,
            "active": is_active,
            "nodes": nodes_count
        })
        print(f"  ✓ {wf_name} (ID: {wf_id}) -> workflows/{filename}")

    # Remove files in workflows/ that are no longer present in n8n
    for existing in WORKFLOWS_DIR.glob("*.json"):
        if existing.name not in exported_files:
            print(f"  🗑️ حذف فایل قدیمی (حذف‌شده از n8n): {existing.name}")
            existing.unlink()

    # Generate a workflows/README.md catalog
    catalog_path = WORKFLOWS_DIR / "README.md"
    with open(catalog_path, "w", encoding="utf-8") as f:
        f.write("# 📋 فهرست ورک‌فلوها (Workflows Catalog)\n\n")
        f.write(f"آخرین به‌روزرسانی: به صورت خودکار توسط `sync.sh`\n\n")
        f.write("| نام ورک‌فلو | شناسه (ID) | وضعیت فعال | تعداد نودها | نام فایل |\n")
        f.write("| :--- | :--- | :---: | :---: | :--- |\n")
        for item in summary_list:
            status = "🟢 فعال" if item["active"] else "⚪ غیرفعال"
            f.write(f"| **{item['name']}** | `{item['id']}` | {status} | {item['nodes']} | [`{item['file']}`](./{item['file']}) |\n")

    print(f"\n✅ {len(workflows)} ورک‌فلو با موفقیت در پوشه workflows/ ذخیره شدند.")


def import_workflows():
    """Import JSON files from workflows/ into n8n Docker container."""
    print("🔄 در حال ایمپورت ورک‌فلوها به داکر n8n...")
    json_files = list(WORKFLOWS_DIR.glob("*.json"))
    if not json_files:
        print("⚠️ هیچ فایل جیسونی در پوشه workflows/ یافت نشد.")
        return

    # Prepare container directory
    subprocess.run(["docker", "exec", CONTAINER_NAME, "rm", "-rf", "/tmp/n8n_import"], check=True)
    subprocess.run(["docker", "exec", CONTAINER_NAME, "mkdir", "-p", "/tmp/n8n_import"], check=True)

    # Copy files into container
    subprocess.run(["docker", "cp", f"{str(WORKFLOWS_DIR)}/.", f"{CONTAINER_NAME}:/tmp/n8n_import/"], check=True)

    # Run n8n import
    cmd = [
        "docker", "exec", CONTAINER_NAME,
        "n8n", "import:workflow",
        "--separate",
        "--input=/tmp/n8n_import/"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout.strip())
        print("✅ تمام ورک‌فلوها با موفقیت به n8n منتقل شدند.")
    else:
        print("❌ خطا در هنگام ایمپورت:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)

    # Cleanup container tmp
    subprocess.run(["docker", "exec", CONTAINER_NAME, "rm", "-rf", "/tmp/n8n_import"], check=False)


def list_workflows():
    """List workflows currently running in n8n."""
    workflows = get_docker_workflows()
    print(f"\n📊 تعداد کل ورک‌فلوها در n8n: {len(workflows)}\n")
    print(f"{'نام ورک‌فلو':<45} | {'شناسه':<18} | {'وضعیت':<8} | {'تعداد نود'}")
    print("-" * 85)
    for wf in workflows:
        status = "فعال" if wf.get("active") else "غیرفعال"
        name = wf.get("name", "Unnamed")[:42]
        print(f"{name:<45} | {wf.get('id', ''):<18} | {status:<8} | {len(wf.get('nodes', []))}")
    print()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "export"
    if action == "export":
        export_workflows()
    elif action == "import":
        import_workflows()
    elif action == "list":
        list_workflows()
    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 sync_workflows.py [export|import|list]")
        sys.exit(1)
