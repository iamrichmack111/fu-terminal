#!/usr/bin/env python3

import os
import subprocess


def run(cmd):
    try:
        return subprocess.run(
            cmd,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).stdout.strip()
    except Exception:
        return ""


def lesson():
    print("""
◆ FU GUIDED LESSON — DELETED FILE RECOVERY
────────────────────────────────────────────────────────────────────────────────────────

MENTAL MODEL

  filename
      │
      ▼
  directory entry
      │
      ▼
    inode
      │
      ▼
  data blocks

Deleting a filename removes a directory reference.

The data may still exist temporarily depending on:
  • remaining hard links
  • open file descriptors
  • filesystem type
  • subsequent disk writes
  • block reuse


STEP 1 — LOOK FOR DELETED FILES STILL OPEN

  lsof +L1

Why:
A process may still hold the inode even though the filename was deleted.

Learn:
  fu learn lsof --deep


STEP 2 — IDENTIFY THE FILESYSTEM

  findmnt /
  lsblk -f

Why:
Recovery techniques depend heavily on the filesystem.

Learn:
  fu learn findmnt
  fu learn lsblk


STEP 3 — MINIMIZE WRITES

If important deleted data is no longer held open, continued writes can
reuse blocks that formerly belonged to the deleted file.

Recovery work should avoid unnecessary modification of the source.


STEP 4 — IMAGE BEFORE EXPERIMENTING

Advanced recovery commonly works from an image or another copy rather
than experimenting directly on the original filesystem.

  fu learn dd --deep

⚠ dd is high risk. FU does not automatically execute recovery writes.


STEP 5 — RECOVERY TOOLS

Depending on filesystem and circumstances:

  testdisk
  photorec
  debugfs          [advanced/ext filesystem work]
  extundelete      [when available/applicable]

Recovery capability varies substantially by filesystem and whether data
blocks have already been reused.


THE IMPORTANT DISTINCTION

Deleted but OPEN:
    often recoverable through the process file descriptor.

Deleted and CLOSED:
    filesystem-level recovery may be necessary.

Blocks already REUSED:
    original data may be partially or completely unrecoverable.


NEXT

  fu learn inode
  fu learn lsof --deep
  fu learn stat --deep
  fu learn recovery
""".strip())


if __name__ == "__main__":
    lesson()
