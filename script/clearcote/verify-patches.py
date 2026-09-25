#!/usr/bin/env python3
"""Replay the pinned Chromium/WebRTC patches in temporary, minimal source trees."""
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

ELECTRON = Path(__file__).resolve().parents[2]
SRC = ELECTRON.parent


def run(args, cwd):
    return subprocess.check_output(args, cwd=cwd, stderr=subprocess.STDOUT)


def main():
    manifest = json.loads((ELECTRON / "patches/clearcote/UPSTREAM.json").read_text())
    version = dict(line.split("=", 1) for line in
                   (SRC / "chrome/VERSION").read_text().splitlines())
    actual = ".".join(version[k] for k in ("MAJOR", "MINOR", "BUILD", "PATCH"))
    if actual != manifest["target"]["chromium"]:
        raise SystemExit(f"Expected Chromium {manifest['target']['chromium']}, found {actual}; rebase required")
    for entry in manifest["patches"]:
        patch = ELECTRON / entry["file"]
        data = patch.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise SystemExit(f"Patch checksum differs: {patch}")
        repo = SRC / entry["repo"]
        with tempfile.TemporaryDirectory(prefix="clearcote-replay-") as directory:
            scratch = Path(directory)
            run(["git", "init", "-q"], scratch)
            for filename in re.findall(r"^--- a/([^\n]+)$", data.decode(), re.M):
                dest = scratch / filename
                if not dest.resolve().is_relative_to(scratch.resolve()):
                    raise SystemExit(f"Unsafe patch path: {filename}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(run(["git", "show", f"{entry['baseline']}:{filename}"], repo))
            run(["git", "apply", "--check", str(patch)], scratch)
            run(["git", "apply", str(patch)], scratch)
            for filename in entry["files"]:
                if (scratch / filename).read_bytes() != (repo / filename).read_bytes():
                    raise SystemExit(f"Applied patch differs from working tree: {repo / filename}")
        print(f"PASS {entry['file']}: clean replay and {len(entry['files'])} matching files")


if __name__ == "__main__":
    main()
