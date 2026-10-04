#!/usr/bin/env python3
"""node --check for page JavaScript: standalone .js files and inline <script> blocks in .html.

Static pages embedded into a binary (go:embed) never meet a browser in CI, so a syntax
error would ship silently. Fails when nothing was checked: a wrong path is an error too.

  check_js.py <dir> [<dir>...]
"""
import os
import re
import subprocess
import sys
import tempfile

failed = checked = 0
for root, name in sorted((r, n) for r in sys.argv[1:] for n in os.listdir(r)):
    path = os.path.join(root, name)
    if name.endswith(".js"):
        sources = [(path, open(path, encoding="utf-8").read())]
    elif name.endswith(".html"):
        html = open(path, encoding="utf-8").read()
        # inline scripts only: <script src=…> is checked as its own file
        sources = [(f"{path} <script #{i + 1}>", m.group(1))
                   for i, m in enumerate(re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S))]
    else:
        continue
    for label, code in sources:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(code)
        r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        os.unlink(f.name)
        checked += 1
        if r.returncode != 0:
            failed += 1
            print(f"::error title=js::{label}\n{r.stderr}")
print(f"scripts checked: {checked}, with errors: {failed}")
sys.exit(1 if failed or not checked else 0)
