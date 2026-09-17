import os
import re

JS_DIR = os.path.abspath("frontend/js")
html_pattern = re.compile(r'["\']([^"\']+\.html[^"\']*)["\']')

found = []
for root, dirs, files in os.walk(JS_DIR):
    for f in files:
        if f.endswith(".js"):
            fpath = os.path.join(root, f)
            relpath = os.path.relpath(fpath, JS_DIR).replace("\\", "/")
            content = open(fpath, "r", encoding="utf-8", errors="ignore").read()
            for m in html_pattern.finditer(content):
                found.append((relpath, m.group(1)))

print(f"Total HTML references in JS: {len(found)}")
for rel, ref in sorted(set(found)):
    print(f"{rel} -> {ref}")
