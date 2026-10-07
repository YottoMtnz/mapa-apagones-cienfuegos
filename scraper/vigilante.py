#!/usr/bin/env python3
"""
Vigilante opcional del workflow: si GitHub pausa el cron programado, lo reactiva con
un workflow_dispatch. Ejecútalo desde cualquier cron EXTERNO (cada 10 min).

Variables de entorno:
  GITHUB_TOKEN  token con permiso Actions: write sobre el repo (fine-grained)
  GITHUB_REPO   p.ej. "YottoMtnz/mapa-apagones-cienfuegos"
  MAX_SILENCIO_MIN  (def. 12)  minutos sin ningún run antes de disparar
Sin dependencias fuera de la librería estándar.
"""
import json, os, sys, urllib.request
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPO", "YottoMtnz/mapa-apagones-cienfuegos")
WORKFLOW = "mapa.yml"
MAX_SILENCIO_MIN = float(os.environ.get("MAX_SILENCIO_MIN", "12"))
GITHUB_HOSTS = ["api.github.com"]
CRED_NAME = "custom.github"


def _auth_headers(req):
    """GITHUB_TOKEN en env, o la credencial conectada custom.github (surrogate)."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
        return
    sys.exit('Falta GITHUB_TOKEN')


def api(path, method="GET", data=None):
    req = urllib.request.Request(f"https://api.github.com{path}", data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "MapaCienfuegos-vigilante/3.0")
    _auth_headers(req)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r) if r.status != 204 else None


def main():
    runs = api(f"/repos/{REPO}/actions/workflows/{WORKFLOW}/runs?per_page=1")
    if not runs.get("workflow_runs"):
        disparar = True
    else:
        dt = datetime.fromisoformat(runs["workflow_runs"][0]["created_at"].replace("Z", "+00:00"))
        mins = (datetime.now(timezone.utc) - dt).total_seconds() / 60
        print(f"Último run hace {mins:.1f} min")
        disparar = mins > MAX_SILENCIO_MIN and runs['workflow_runs'][0].get('status') not in ('in_progress','queued','waiting')
    if disparar:
        api(f"/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches", "POST",
            json.dumps({"ref": "main"}).encode())
        print("Workflow reactivado")
    else:
        print("OK")


if __name__ == "__main__":
    main()
