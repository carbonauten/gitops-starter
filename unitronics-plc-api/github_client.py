"""
GitHub API client for the Unitronics PLC API bridge.

Uses GITHUB_TOKEN from environment. All methods return (status_code, data)
where data is a dict suitable for JSON response; on error data may contain
"error" and optionally "message".
"""

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

GITHUB_API = "https://api.github.com"
DEFAULT_REF = "main"


def get_token() -> Optional[str]:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT")


def _headers() -> Dict[str, str]:
    token = get_token()
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _request(
    method: str,
    path: str,
    *,
    json: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any]]:
    url = f"{GITHUB_API}{path}"
    try:
        r = requests.request(
            method,
            url,
            headers=_headers(),
            json=json,
            timeout=30,
        )
        try:
            data = r.json() if r.content else {}
        except Exception:
            data = {"error": "invalid_json", "raw": r.text[:500]}
        if not r.ok:
            return r.status_code, data if isinstance(data, dict) else {"error": data}
        return r.status_code, data if isinstance(data, dict) else {"data": data}
    except requests.RequestException as e:
        return 502, {"error": "request_failed", "message": str(e)}


def list_repos() -> Tuple[int, Dict[str, Any]]:
    """List repos for the authenticated user. Requires GITHUB_TOKEN."""
    if not get_token():
        return 503, {"error": "github_not_configured", "message": "GITHUB_TOKEN not set"}
    status, data = _request("GET", "/user/repos?per_page=100")
    if status != 200 or "error" in data:
        return status, data
    repos = [
        {
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "default_branch": r.get("default_branch"),
            "private": r.get("private"),
        }
        for r in (data if isinstance(data, list) else [])
    ]
    return 200, {"repos": repos}


def get_repo(owner: str, repo: str) -> Tuple[int, Dict[str, Any]]:
    """Get a single repo. Works with or without token (public repos)."""
    status, data = _request("GET", f"/repos/{owner}/{repo}")
    if status != 200:
        return status, data
    return 200, {
        "name": data.get("name"),
        "full_name": data.get("full_name"),
        "default_branch": data.get("default_branch"),
        "private": data.get("private"),
    }


def trigger_workflow(
    owner: str,
    repo: str,
    workflow_id: str,
    ref: str = DEFAULT_REF,
    inputs: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, Any]]:
    """
    Trigger a workflow_dispatch run. workflow_id is filename (e.g. ci.yml) or numeric id.
    Requires GITHUB_TOKEN with actions:write.
    """
    if not get_token():
        return 503, {"error": "github_not_configured", "message": "GITHUB_TOKEN not set"}
    body: Dict[str, Any] = {"ref": ref}
    if inputs:
        body["inputs"] = inputs
    status, data = _request(
        "POST",
        f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
        json=body,
    )
    if status == 204:
        return 200, {"status": "dispatched", "workflow_id": workflow_id, "ref": ref}
    return status, data


def get_latest_release(owner: str, repo: str) -> Tuple[int, Dict[str, Any]]:
    """Get latest release tag and name. No token needed for public repos."""
    status, data = _request("GET", f"/repos/{owner}/{repo}/releases/latest")
    if status != 200:
        return status, data
    return 200, {
        "tag_name": data.get("tag_name"),
        "name": data.get("name"),
        "published_at": data.get("published_at"),
    }
