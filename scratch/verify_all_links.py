import os
import re
from bs4 import BeautifulSoup

FRONTEND_DIR = os.path.abspath("frontend")

# 1. Test every link in every page
broken_links = []
valid_links_count = 0

for root, dirs, files in os.walk(FRONTEND_DIR):
    for f in files:
        if not f.endswith(".html"):
            continue
        fpath = os.path.join(root, f)
        rel_page = os.path.relpath(fpath, FRONTEND_DIR).replace("\\", "/")
        is_component = "components/" in rel_page
        
        content = open(fpath, "r", encoding="utf-8", errors="ignore").read()
        soup = BeautifulSoup(content, "html.parser")
        
        # Check standard <a> tags
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            # If component has data-site-path, use data-site-path for site-root resolution
            if is_component and a.get("data-site-path"):
                target_path = a["data-site-path"]
                resolved = os.path.normpath(os.path.join(FRONTEND_DIR, target_path.split("#")[0].split("?")[0]))
            elif not href or href.startswith(("#", "javascript:", "tel:", "mailto:", "http:", "https:")):
                continue
            else:
                target_path = href
                resolved = os.path.normpath(os.path.join(root, href.split("#")[0].split("?")[0]))
            
            if not os.path.exists(resolved) or os.path.isdir(resolved):
                broken_links.append((rel_page, f"<a> href={href}", target_path, resolved))
            else:
                valid_links_count += 1

        # Check forms
        for form in soup.find_all("form", action=True):
            action = form["action"].strip()
            if is_component and form.get("data-site-path"):
                target_path = form["data-site-path"]
                resolved = os.path.normpath(os.path.join(FRONTEND_DIR, target_path.split("#")[0].split("?")[0]))
            elif not action or action.startswith(("#", "javascript:", "http:", "https:")):
                continue
            else:
                target_path = action
                resolved = os.path.normpath(os.path.join(root, action.split("#")[0].split("?")[0]))
            
            if not os.path.exists(resolved) or os.path.isdir(resolved):
                broken_links.append((rel_page, f"<form> action={action}", target_path, resolved))
            else:
                valid_links_count += 1

print(f"Total valid links verified: {valid_links_count}")
print(f"Total broken links: {len(broken_links)}")
if broken_links:
    for src, tag, tgt, resolved in broken_links:
        print(f"  BROKEN in {src}: {tag} -> target {tgt} (resolved: {resolved})")
    exit(1)
else:
    print("ALL NAVIGATION LINKS SUCCESSFULLY RESOLVED TO EXISTING FILES!")
