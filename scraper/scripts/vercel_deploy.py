"""Configure the Vercel project and trigger a production deploy via the API.

Reads the Vercel token from ../../secrets/tokens.env and the public Supabase env
from ../../web/.env.local. Idempotent: safe to re-run.

Usage (venv active):
    python scripts/vercel_deploy.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import agent  # noqa: F401 — activates truststore so HTTPS works behind the proxy
import requests

ROOT = Path(__file__).resolve().parent.parent.parent     # research-agent/
API = "https://api.vercel.com"
PROJECT_NAME = "grocerytracker"
ROOT_DIRECTORY = "web"


def read_kv(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return None


def main() -> None:
    token = read_kv(ROOT / "secrets" / "tokens.env", "VERCEL_TOKEN")
    if not token:
        sys.exit("VERCEL_TOKEN not found in secrets/tokens.env")
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    supa_url = read_kv(ROOT / "web" / ".env.local", "NEXT_PUBLIC_SUPABASE_URL")
    supa_anon = read_kv(ROOT / "web" / ".env.local", "NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not (supa_url and supa_anon):
        sys.exit("Supabase env not found in web/.env.local")

    # --- locate project + team ---
    team_id = None
    teams = requests.get(f"{API}/v2/teams", headers=H, timeout=25).json().get("teams", [])
    proj = None
    for tid in [None] + [t["id"] for t in teams]:
        params = {"teamId": tid} if tid else {}
        r = requests.get(f"{API}/v9/projects", headers=H, params=params, timeout=25)
        for p in r.json().get("projects", []):
            if p.get("name") == PROJECT_NAME:
                proj, team_id = p, tid
    if not proj:
        sys.exit(f"Project {PROJECT_NAME!r} not found")
    pid = proj["id"]
    q = {"teamId": team_id} if team_id else {}
    print(f"Project {pid} (team {team_id})")

    # --- 1. set root directory + framework ---
    r = requests.patch(
        f"{API}/v9/projects/{pid}", headers=H, params=q,
        json={"framework": "nextjs", "rootDirectory": ROOT_DIRECTORY}, timeout=25,
    )
    r.raise_for_status()
    print(f"  set rootDirectory={r.json().get('rootDirectory')!r}, framework={r.json().get('framework')!r}")

    # --- 2. upsert public env vars (all targets) ---
    for key, value in [
        ("NEXT_PUBLIC_SUPABASE_URL", supa_url),
        ("NEXT_PUBLIC_SUPABASE_ANON_KEY", supa_anon),
    ]:
        rr = requests.post(
            f"{API}/v10/projects/{pid}/env", headers=H,
            params={**q, "upsert": "true"},
            json={"key": key, "value": value, "type": "encrypted",
                  "target": ["production", "preview", "development"]},
            timeout=25,
        )
        print(f"  env {key}: {'ok' if rr.ok else rr.text[:120]}")

    # --- 3. trigger a production deploy from the linked GitHub repo ---
    link = proj.get("link") or {}
    repo_id = link.get("repoId")
    if not repo_id:
        sys.exit("No GitHub repoId on project link; push a commit to deploy instead.")
    dep = requests.post(
        f"{API}/v13/deployments", headers=H, params={**q, "forceNew": "1"},
        json={
            "name": PROJECT_NAME,
            "project": pid,
            "target": "production",
            "gitSource": {"type": "github", "repoId": repo_id, "ref": "main"},
        },
        timeout=30,
    )
    if not dep.ok:
        sys.exit(f"Deploy request failed: {dep.status_code} {dep.text[:300]}")
    d = dep.json()
    dep_id, dep_url = d["id"], d.get("url")
    print(f"  deploy queued: https://{dep_url}")

    # --- 4. poll until ready ---
    print("  building", end="", flush=True)
    for _ in range(80):  # ~6.5 min max
        time.sleep(5)
        s = requests.get(f"{API}/v13/deployments/{dep_id}", headers=H, params=q, timeout=25).json()
        state = s.get("readyState") or s.get("status")
        print(".", end="", flush=True)
        if state in ("READY", "ERROR", "CANCELED"):
            print(f"\n  deployment {state}")
            if state == "READY":
                aliases = s.get("alias") or []
                print("PRODUCTION URL(S):")
                for a in aliases:
                    print(f"  https://{a}")
                print(f"  https://{dep_url}")
            else:
                print("  Check Vercel build logs for the error.")
            return
    print("\n  still building — check the Vercel dashboard.")


if __name__ == "__main__":
    main()
