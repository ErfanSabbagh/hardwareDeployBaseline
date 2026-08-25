"""Raspberry Pi deploy over SSH. Credentials come from the request or env — never committed."""

from __future__ import annotations

import os
from pathlib import Path

from .models import PiDeployResponse, PiLogsResponse


def _ssh_connect(host: str | None, user: str | None, password: str | None):
    host = (host or os.environ.get("PI_SSH_HOST") or "").strip()
    user = (user or os.environ.get("PI_SSH_USER") or "").strip()
    password = password if password is not None else os.environ.get("PI_SSH_PASSWORD")
    key_path = os.environ.get("PI_SSH_KEY", "").strip()
    if not host or not user:
        return None, host, user, "SSH host and user are required (form fields or PI_SSH_HOST / PI_SSH_USER)."
    try:
        import paramiko
    except ImportError:
        return None, host, user, "paramiko is not installed on the backend."

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_kw: dict = {"hostname": host, "username": user, "timeout": 15}
    if key_path and Path(key_path).is_file():
        connect_kw["key_filename"] = key_path
    elif password:
        connect_kw["password"] = password
    else:
        connect_kw["look_for_keys"] = True
        connect_kw["allow_agent"] = True
    client.connect(**connect_kw)
    return client, host, user, None


def deploy_python(source: str, host: str | None, user: str | None, password: str | None, remote_path: str) -> PiDeployResponse:
    client = None
    logs: list[str] = []
    try:
        client, host, user, err = _ssh_connect(host, user, password)
        if err:
            hint = "Download app.py and copy it to the Pi instead."
            if "paramiko" in err:
                hint = "pip install paramiko, or download the artefact."
            return PiDeployResponse(ok=False, logs=err, downloadHint=hint)
        remote_path = remote_path.replace("{user}", user or "")
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
        err_out = stderr.read().decode("utf-8", errors="replace")
        logs.append(out.strip() or "(started)")
        if err_out.strip():
            logs.append(err_out.strip())
        log_path = f"{remote_dir}/hw-deploy.log"
        return PiDeployResponse(
            ok=True,
            logs="\n".join(logs),
            remotePath=remote_path,
            logPath=log_path,
        )
    except Exception as exc:  # noqa: BLE001
        return PiDeployResponse(
            ok=False,
            logs="\n".join(logs + [str(exc)]),
            remotePath=remote_path,
            downloadHint="SSH failed. Download app.py and run: python3 app.py on the Pi.",
        )
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


def read_logs(
    host: str | None,
    user: str | None,
    password: str | None,
    log_path: str,
    since_bytes: int,
) -> PiLogsResponse:
    client = None
    try:
        client, _host, user, err = _ssh_connect(host, user, password)
        if err:
            return PiLogsResponse(ok=False, logs=err, nextOffset=since_bytes)
        log_path = log_path.replace("{user}", user or "")
        sftp = client.open_sftp()
        try:
            size = sftp.stat(log_path).st_size
        except OSError:
            sftp.close()
            return PiLogsResponse(ok=True, text="", nextOffset=0, logs=f"(no log yet at {log_path})")
        if since_bytes > size:
            since_bytes = 0
        with sftp.file(log_path, "r") as remote:
            remote.seek(since_bytes)
            chunk = remote.read().decode("utf-8", errors="replace")
        sftp.close()
        return PiLogsResponse(ok=True, text=chunk, nextOffset=size)
    except Exception as exc:  # noqa: BLE001
        return PiLogsResponse(ok=False, logs=str(exc), nextOffset=since_bytes)
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


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
