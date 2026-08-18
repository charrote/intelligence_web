#!/usr/bin/env python3
"""Daily SQLite backup for the Intelligence Platform.

Runs as a long-lived compose service (reuses the research python image, so no
new image pull is needed). On start it takes an immediate consistency snapshot
of every domain DB (so "the last day's backup" always exists), then repeats
every 24h. Snapshots use SQLite's online `VACUUM INTO` — a consistent copy that
does not require stopping the running services — and are verified with
`PRAGMA integrity_check`. Old backups are pruned to a rolling N-day window.

Restoring a backup is a plain file copy back over the live DB file.
"""
import sqlite3
import os
import time
import glob
import datetime

# domain name -> live DB path (inside this container)
DBS = [
    ("research", "/data/research/intelligence"),
    ("sales", "/data/sales/intelligence_sales"),
]
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/backups")
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "14"))
INTERVAL_HOURS = int(os.environ.get("BACKUP_INTERVAL_HOURS", "24"))


def log(msg):
    print(f"[backup] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def backup_one(name, db):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"{name}_{ts}.sqlite")
    # Read-only URI connection: never takes a write lock, safe while services run.
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        conn.execute("VACUUM INTO ?", (dest,))
    finally:
        conn.close()
    # Verify the snapshot is a valid, intact database.
    check = sqlite3.connect(dest)
    try:
        ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        check.close()
    if not ok:
        raise RuntimeError(f"integrity_check failed for {dest}")
    return dest


def prune(name):
    cutoff = time.time() - RETENTION_DAYS * 86400
    removed = []
    for f in glob.glob(os.path.join(BACKUP_DIR, f"{name}_*.sqlite")):
        if os.path.getmtime(f) < cutoff:
            os.remove(f)
            removed.append(os.path.basename(f))
    return removed


def run_cycle(label):
    log(f"cycle start ({label})")
    for name, db in DBS:
        if not os.path.exists(db):
            log(f"{name}: DB not found at {db}, skipping")
            continue
        try:
            dest = backup_one(name, db)
            pruned = prune(name)
            size = os.path.getsize(dest)
            log(f"{name}: OK -> {dest} ({size / 1024:.0f} KB, integrity ok)")
            if pruned:
                log(f"{name}: pruned {len(pruned)} old backup(s)")
        except Exception as e:
            log(f"{name}: ERROR {e}")
    log(f"cycle end ({label})")


def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    log(f"backup service started | retention={RETENTION_DAYS}d interval={INTERVAL_HOURS}h")
    run_cycle("startup")  # immediate: guarantees the "last day" snapshot exists
    while True:
        time.sleep(INTERVAL_HOURS * 3600)
        run_cycle("scheduled")


if __name__ == "__main__":
    main()