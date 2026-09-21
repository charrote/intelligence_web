#!/usr/bin/env python3
"""Domain watcher — polls core/domains.json for pending_start / pending_stop
entries, performs docker compose up/down + nginx reload, and marks entries
started / archived accordingly.

Runs as a container (service: domain_watcher) with the repo + docker.sock
mounted, so it can manage sibling containers and the gateway.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

REPO = os.environ.get("REPO_PATH", "/repo")
REGISTRY = os.path.join(REPO, "config", "domains.json")
COMPOSE_DIR = os.path.join(REPO, "compose.d")
NGINX_DYNAMIC = os.path.join(REPO, "nginx", "dynamic")
DOMAINS_DIR = os.path.join(REPO, "domains")
BACKUP_ROOT = os.path.join(REPO, "backups")
POLL_INTERVAL = int(os.environ.get("WATCHER_POLL_INTERVAL", "10"))


def log(msg):
    print(f"[domain-watcher] {msg}", flush=True)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, **kw)
    if r.returncode != 0:
        log(f"cmd failed ({' '.join(cmd)}): {r.stderr.strip() or r.stdout.strip()}")
    return r


def compose_cmd(slug, *args):
    """docker compose scoped to an ISOLATED project `domain_<slug>`.

    Critical: without -p, the project name defaults to the project-directory
    basename (`intelligence_web`) — the same as the MAIN project — and
    `down --remove-orphans` would stop/remove every main-project container
    (gateway, research, sales, ...) as 'orphans'.
    REPO_HOST env lets ${REPO_HOST} volume placeholders in fragment files
    resolve to the real host repo path.
    """
    env = dict(os.environ, REPO_HOST=REPO)
    return subprocess.run(
        ["docker", "compose", "-p", f"domain_{slug}",
         "--project-directory", REPO, *args],
        capture_output=True, text=True, cwd=REPO, env=env)


def load_registry():
    with open(REGISTRY, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(data):
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, REGISTRY)


def start_domain(entry):
    slug, port = entry["slug"], entry["port"]
    frag = os.path.join(COMPOSE_DIR, f"domain-{slug}.yml")
    if not os.path.exists(frag):
        log(f"compose fragment missing for {slug}, skipping")
        return False
    r = compose_cmd(slug, "-f", frag, "up", "-d")
    if r.returncode != 0:
        log(f"compose up failed for {slug}: {r.stderr.strip() or r.stdout.strip()}")
        return False
    # Health check via docker inspect: the domain container lives on the
    # compose network, not on the watcher's localhost.
    cname = f"domain_{slug}-domain_{slug}-1"
    for _ in range(30):
        h = subprocess.run(["docker", "inspect", "--format",
                            "{{.State.Health.Status}}", cname],
                           capture_output=True, text=True)
        if h.returncode == 0 and h.stdout.strip() == "healthy":
            log(f"domain {slug} healthy (container {cname})")
            return True
        if h.returncode == 0 and h.stdout.strip() == "unhealthy":
            log(f"domain {slug} container unhealthy — will retry")
            return False
        time.sleep(2)
    log(f"domain {slug} not healthy within 60s — will retry")
    return False


def stop_container(slug):
    frag = os.path.join(COMPOSE_DIR, f"domain-{slug}.yml")
    if os.path.exists(frag):
        r = compose_cmd(slug, "-f", frag, "down", "--remove-orphans")
        if r.returncode != 0:
            log(f"compose down failed for {slug}: {r.stderr.strip()}")


def reload_nginx():
    run(["docker", "compose", "exec", "-T", "gateway", "nginx", "-t"])
    r = run(["docker", "compose", "exec", "-T", "gateway", "nginx", "-s", "reload"])
    log("gateway nginx reloaded" if r.returncode == 0 else "nginx reload failed")


def archive_data(entry):
    slug = entry["slug"]
    ddir = os.path.join(DOMAINS_DIR, slug)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = os.path.join(BACKUP_ROOT, "domain_archived", f"{slug}_{stamp}")
    os.makedirs(archive_dir, exist_ok=True)
    if os.path.exists(ddir):
        os.rename(ddir, archive_dir)
        entry["archive_path"] = os.path.relpath(archive_dir, REPO)
        log(f"data archived to {archive_dir}")


def delete_meili_index(db_filename):
    import urllib.request
    try:
        req = urllib.request.Request(
            f"http://localhost:7700/indexes/intelligence_{db_filename}",
            method="DELETE",
            headers={"Authorization": "Bearer intel-search-key"},
        )
        urllib.request.urlopen(req, timeout=5)
        log(f"meilisearch index deleted: intelligence_{db_filename}")
    except Exception as e:
        log(f"meilisearch index delete skipped ({e})")


def tick():
    try:
        data = load_registry()
    except Exception as e:
        log(f"registry read failed: {e}")
        return

    changed = False
    for entry in data["domains"]:
        status = entry.get("status")
        if status == "pending_start":
            ok = start_domain(entry)
            if ok:
                entry["status"] = "started"
                changed = True
        elif status == "pending_stop":
            stop_container(entry["slug"])
            entry["enabled"] = False
            entry["status"] = "stopped"
            changed = True
            log(f"domain {entry['slug']} stopped (data kept)")
        elif status == "pending_reconnect":
            stop_container(entry["slug"])
            ok = start_domain(entry)
            if ok:
                entry["status"] = "started"
                changed = True
                log(f"domain {entry['slug']} reconnected (port {entry.get('port')})")
        elif status == "pending_archive":
            stop_container(entry["slug"])
            entry["enabled"] = False
            entry["status"] = "archived"
            entry["archived_at"] = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_data(entry)
            conf = os.path.join(NGINX_DYNAMIC, f"{entry['slug']}.conf")
            if os.path.exists(conf):
                os.remove(conf)
            delete_meili_index(entry.get("db_filename", entry["slug"]))
            changed = True
            log(f"domain {entry['slug']} archived")

    if changed:
        save_registry(data)
        reload_nginx()


def main():
    log(f"watcher started, polling {REGISTRY} every {POLL_INTERVAL}s")
    # Wait for docker CLI readiness
    for _ in range(30):
        if run(["docker", "version"]).returncode == 0:
            break
        time.sleep(2)
    while True:
        tick()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
