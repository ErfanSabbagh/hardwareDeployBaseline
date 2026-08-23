"""Raspberry Pi deploy over SSH. Credentials come from the request or env — never committed."""

from __future__ import annotations

import os
from pathlib import Path

from .models import PiDeployResponse


def deploy_python(source: str, host: str | None, user: str | None, password: str | None, remote_path: str) -> PiDeployResponse:
    host = (host or os.environ.get("PI_SSH_HOST") or "").strip()
    user = (user or os.environ.get("PI_SSH_USER") or "").strip()
    password = password if password is not None else os.environ.get("PI_SSH_PASSWORD")
    key_path = os.environ.get("PI_SSH_KEY", "").strip()

    if not host or not user:
        return PiDeployResponse(
            ok=False,
            logs="SSH host and user are required (form fields or PI_SSH_HOST / PI_SSH_USER).",
            downloadHint="Download app.py and copy it to the Pi instead.",
        )

    remote_path = remote_path.replace("{user}", user)
    try:
        import paramiko
    except ImportError:
        return PiDeployResponse(
            ok=False,
            logs="paramiko is not installed on the backend.",
            downloadHint="pip install paramiko, or download the artefact.",
        )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    logs: list[str] = []
    try:
        connect_kw: dict = {"hostname": host, "username": user, "timeout": 15}
        if key_path and Path(key_path).is_file():
            connect_kw["key_filename"] = key_path
            logs.append(f"Auth: SSH key {key_path}")
        elif password:
            connect_kw["password"] = password
            logs.append("Auth: password (not stored)")
        else:
            connect_kw["look_for_keys"] = True
            connect_kw["allow_agent"] = True
            logs.append("Auth: default keys / agent")

        client.connect(**connect_kw)
        logs.append(f"Connected to {user}@{host}")

        sftp = client.open_sftp()
        remote_dir = str(Path(remote_path).parent)
        _mkdir_p(sftp, remote_dir)
        with sftp.file(remote_path, "w") as remote:
            remote.write(source)
        sftp.chmod(remote_path, 0o755)
        sftp.close()
        logs.append(f"Wrote {remote_path}")

        cmd = (
            f"pkill -f '{remote_path}' >/dev/null 2>&1 || true; "
            f"nohup python3 {remote_path} > {remote_dir}/hw-deploy.log 2>&1 & echo PID:$!"
        )
        _stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        logs.append(out.strip() or "(started)")
        if err.strip():
            logs.append(err.strip())
        return PiDeployResponse(ok=True, logs="\n".join(logs), remotePath=remote_path)
    except Exception as exc:  # noqa: BLE001
        return PiDeployResponse(
            ok=False,
            logs="\n".join(logs + [str(exc)]),
            remotePath=remote_path,
            downloadHint="SSH failed. Download app.py and run: python3 app.py on the Pi.",
        )
    finally:
        client.close()


def _mkdir_p(sftp, remote_dir: str) -> None:
    dirs: list[str] = []
    current = remote_dir.rstrip("/")
    while current and current != "/":
        dirs.append(current)
        parent = str(Path(current).parent)
        if parent == current:
            break
        current = parent
    for directory in reversed(dirs):
        try:
            sftp.mkdir(directory)
        except OSError:
            pass
