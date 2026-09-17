import os
import re
from bs4 import BeautifulSoup

FRONTEND_DIR = os.path.abspath("frontend")
links = []

for root, dirs, files in os.walk(FRONTEND_DIR):
    for f in files:
        if f.endswith(".html"):
            fpath = os.path.join(root, f)
            relpath = os.path.relpath(fpath, FRONTEND_DIR).replace("\\", "/")
            content = open(fpath, "r", encoding="utf-8", errors="ignore").read()
            soup = BeautifulSoup(content, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href and not href.startswith(("#", "javascript:", "tel:", "mailto:", "http:", "https:")):
                    links.append((relpath, "a@href", href))
            for form in soup.find_all("form", action=True):
                action = form["action"].strip()
                if action and not action.startswith(("#", "javascript:", "http:", "https:")):
                    links.append((relpath, "form@action", action))

print(f"Total internal links found: {len(links)}")
for rel, tag, target in links:
    # Resolve target relative to source file dir
    src_dir = os.path.dirname(os.path.join(FRONTEND_DIR, rel))
    resolved = os.path.normpath(os.path.join(src_dir, target.split("#")[0].split("?")[0]))
    exists = os.path.exists(resolved)
    is_dir = os.path.isdir(resolved)
    rel_resolved = os.path.relpath(resolved, FRONTEND_DIR).replace("\\", "/")
    if not exists or is_dir:
        print(f"BROKEN: {rel} -> {tag}='{target}' (resolved: {rel_resolved}, exists={exists})")
    else:
        # Check if pointing to a shim
        content_target = open(resolved, "r", encoding="utf-8", errors="ignore").read()
        if 'http-equiv="refresh"' in content_target:
            print(f"POINTS TO SHIM: {rel} -> {tag}='{target}' -> {rel_resolved}")
