#!/usr/bin/env python3
"""Minimal askpass helper. It reads a mounted secret only when Git asks."""
import os
import sys
from pathlib import Path

prompt = sys.argv[1].lower() if len(sys.argv) > 1 else ""
if "username" in prompt:
    print(os.environ.get("GIT_HTTPS_USERNAME", "x-access-token"))
else:
    secret_path = os.environ.get("GIT_HTTPS_TOKEN_FILE", "")
    try:
        print(Path(secret_path).read_text(encoding="utf-8").strip())
    except OSError:
        # Git will fail authentication; never disclose path or secret here.
        sys.exit(1)
