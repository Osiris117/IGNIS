#!/usr/bin/env python3
"""IGNIS cross-platform launcher.

Works on Windows, macOS and Linux with Python 3.10+.
Creates an isolated .venv, installs dependencies only when requirements change,
starts FastAPI/Uvicorn and opens the browser after the health endpoint is ready.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
REQ = ROOT / "requirements.txt"
STAMP = VENV / ".ignis_requirements.sha256"
MIN_PYTHON = (3, 10)


def die(message: str, code: int = 1) -> None:
    print(f"\n[IGNIS] ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def requirements_hash() -> str:
    return hashlib.sha256(REQ.read_bytes()).hexdigest()


def ensure_python() -> None:
    if sys.version_info < MIN_PYTHON:
        die(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required. "
            f"Detected {platform.python_version()}."
        )


def ensure_venv(skip_install: bool = False) -> Path:
    py = venv_python()
    if not py.exists():
        print("[IGNIS] Creating isolated environment (.venv)...")
        try:
            venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
        except Exception as exc:
            die(f"Could not create .venv: {exc}")

    if skip_install:
        return py

    current = requirements_hash()
    installed = STAMP.read_text(encoding="utf-8").strip() if STAMP.exists() else ""
    if current != installed:
        print("[IGNIS] Installing/verifying Python dependencies...")
        try:
            subprocess.check_call(
                [str(py), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQ)],
                cwd=ROOT,
            )
            STAMP.write_text(current, encoding="utf-8")
        except subprocess.CalledProcessError as exc:
            die(f"Dependency installation failed (exit {exc.returncode}).")
    else:
        print("[IGNIS] Dependencies already up to date.")
    return py


def port_is_free(host: str, port: int) -> bool:
    bind_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    family = socket.AF_INET6 if ":" in bind_host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((bind_host, port)) != 0
    except OSError:
        return False


def pick_port(host: str, requested: int) -> int:
    for port in range(requested, requested + 30):
        if port_is_free(host, port):
            if port != requested:
                print(f"[IGNIS] Port {requested} is busy; using {port} instead.")
            return port
    die(f"No free port found between {requested} and {requested + 29}.")
    return requested


def open_when_ready(url: str, health_url: str) -> None:
    for _ in range(80):
        try:
            with urllib.request.urlopen(health_url, timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(url, new=2)
                    return
        except Exception:
            time.sleep(0.25)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run IGNIS on Windows, macOS or Linux.")
    parser.add_argument("--host", default=os.getenv("IGNIS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("IGNIS_PORT", "8000")))
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser automatically.")
    parser.add_argument("--no-install", action="store_true", help="Skip dependency installation check.")
    parser.add_argument("--reload", action="store_true", help="Enable Uvicorn reload for development.")
    args = parser.parse_args()

    ensure_python()
    py = ensure_venv(skip_install=args.no_install)
    port = pick_port(args.host, args.port)
    browser_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{browser_host}:{port}"
    health_url = f"{url}/api/health"

    print("\n===============================================")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    print(f"  IGNIS v{version} — Earth Fire Intelligence")
    print("===============================================")
    print(f"  OS      : {platform.system()} {platform.release()}")
    print(f"  Python  : {platform.python_version()}")
    print(f"  Address : {url}")
    print("  Stop    : Ctrl+C")
    print("===============================================\n")

    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(url, health_url), daemon=True).start()

    cmd = [
        str(py), "-m", "uvicorn", "backend.app:app",
        "--host", args.host, "--port", str(port),
    ]
    if args.reload:
        cmd.append("--reload")

    try:
        raise SystemExit(subprocess.call(cmd, cwd=ROOT))
    except KeyboardInterrupt:
        print("\n[IGNIS] Server stopped.")


if __name__ == "__main__":
    main()
