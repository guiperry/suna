#!/usr/bin/env python3
"""Start/stop helper for Kortix Super Worker (suna).

This script detects whether the project was configured for 'docker' or
'manual' setup (reads .setup_progress) and provides sane start/stop
commands for the common local development services.

The implementation is intentionally small, cross-platform where possible,
and avoids relying on shell-specific behavior.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from typing import Dict, Optional

IS_WINDOWS = platform.system() == "Windows"
PROGRESS_FILE = ".setup_progress"


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def load_progress() -> Dict:
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"step": 0, "data": {}}
    return {"step": 0, "data": {}}


from typing import Optional

def get_setup_method() -> Optional[str]:
    p = load_progress()
    return p.get("data", {}).get("setup_method")


def get_supabase_setup_method() -> Optional[str]:
    p = load_progress()
    return p.get("data", {}).get("supabase_setup_method")


def check_docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, shell=IS_WINDOWS)
        return True
    except Exception:
        print(f"{Colors.RED}❌ Docker does not appear to be available or running.{Colors.ENDC}")
        return False


def docker_compose_is_up() -> bool:
    try:
        res = subprocess.run(["docker", "compose", "ps", "-q"], capture_output=True, text=True, shell=IS_WINDOWS)
        return bool(res.stdout.strip())
    except Exception:
        return False


def start_docker_services() -> None:
    if not check_docker_available():
        return
    try:
        subprocess.run(["docker", "compose", "up", "-d"], check=True, shell=IS_WINDOWS)
        print(f"{Colors.GREEN}✅ Docker Compose services started.{Colors.ENDC}")
        print("Access Suna at: http://localhost:3000")
    except subprocess.CalledProcessError:
        print(f"{Colors.RED}Failed to start Docker Compose services. See 'docker compose ps' and 'docker compose logs'.{Colors.ENDC}")


def stop_docker_services() -> None:
    try:
        subprocess.run(["docker", "compose", "down"], check=True, shell=IS_WINDOWS)
        print(f"{Colors.GREEN}✅ Docker Compose services stopped.{Colors.ENDC}")
    except subprocess.CalledProcessError:
        print(f"{Colors.RED}Failed to stop Docker Compose services.{Colors.ENDC}")


def print_manual_instructions(supabase_local: bool) -> None:
    step = 1
    if supabase_local:
        print(f"{Colors.BOLD}{step}. Start Local Supabase (in backend directory):{Colors.ENDC}")
        print(f"  {Colors.CYAN}cd backend && npx supabase start{Colors.ENDC}\n")
        step += 1

    print(f"{Colors.BOLD}{step}. Start Infrastructure (in project root):{Colors.ENDC}")
    print(f"  {Colors.CYAN}docker compose up redis rabbitmq -d{Colors.ENDC}\n")
    step += 1

    print(f"{Colors.BOLD}{step}. Start Frontend (in a new terminal):{Colors.ENDC}")
    print(f"  {Colors.CYAN}cd frontend && npm run dev{Colors.ENDC}\n")
    step += 1

    print(f"{Colors.BOLD}{step}. Start Backend (in a new terminal):{Colors.ENDC}")
    print(f"  {Colors.CYAN}cd backend && uv run api.py{Colors.ENDC}\n")
    step += 1

    print(f"{Colors.BOLD}{step}. Start Background Worker (in a new terminal):{Colors.ENDC}")
    print(f"  {Colors.CYAN}cd backend && uv run dramatiq run_agent_background{Colors.ENDC}\n")

    if supabase_local:
        print(f"{Colors.BOLD}To stop Local Supabase:{Colors.ENDC}")
        print(f"  {Colors.CYAN}cd backend && npx supabase stop{Colors.ENDC}\n")


def start_manual_services(supabase_local: bool) -> None:
    """Start backend, frontend, worker and infra in background (Unix-like systems).

    On Windows this function will only print helpful instructions (automation is
    more reliable on POSIX systems where `pgrep`/`pkill` and process groups are
    available).
    """
    import time
    import tempfile

    if IS_WINDOWS:
        print(f"{Colors.YELLOW}⚠️  Automatic start of backend/frontend/worker is not supported on Windows yet.{Colors.ENDC}")
        print_manual_instructions(supabase_local)
        print("\nStart the services manually or use WSL for a Unix-like experience.")
        return

    tmp = tempfile.gettempdir()
    backend_log = os.path.join(tmp, "suna_backend.log")
    frontend_log = os.path.join(tmp, "suna_frontend.log")
    worker_log = os.path.join(tmp, "suna_worker.log")

    def is_running(pattern: str) -> bool:
        return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0

    backend_running = is_running("python api.py")
    frontend_running = is_running("next dev")
    worker_running = is_running("dramatiq run_agent_background")

    if backend_running or frontend_running or worker_running:
        print(f"{Colors.YELLOW}⚠️  Some services appear to already be running. Aborting automatic start.{Colors.ENDC}")
        return

    # If we have saved progress, ensure backend/.env reflects it before starting services.
    try:
        prog_path = PROGRESS_FILE
        env_path = os.path.join("backend", ".env")
        if os.path.exists(prog_path):
            prog_mtime = os.path.getmtime(prog_path)
            env_mtime = os.path.getmtime(env_path) if os.path.exists(env_path) else 0
            # If progress is newer, or if .env is missing important keys, re-generate
            should_regen = prog_mtime > env_mtime

            # Also regenerate if SUPABASE_JWT_SECRET is missing/empty in backend/.env
            try:
                if os.path.exists(env_path):
                    with open(env_path, "r") as ef:
                        content = ef.read()
                    # crude check for empty SUPABASE_JWT_SECRET
                    if "SUPABASE_JWT_SECRET=" in content:
                        parts = [ln for ln in content.splitlines() if ln.strip().startswith("SUPABASE_JWT_SECRET=")]
                        if parts:
                            val = parts[0].split("=", 1)[1].strip()
                            if not val:
                                should_regen = True
                    else:
                        should_regen = True
            except Exception:
                # Ignore parse errors and keep existing decision
                pass

            if should_regen:
                # Re-generate .env from saved setup progress (non-interactive)
                try:
                    from setup import SetupWizard
                    sw = SetupWizard()
                    sw.configure_env_files()
                    print(f"{Colors.GREEN}   ✓ Refreshed backend/.env from {prog_path}{Colors.ENDC}\n")
                except Exception as e:
                    print(f"{Colors.YELLOW}⚠️ Failed to refresh backend/.env from {prog_path}: {e}{Colors.ENDC}")
    except Exception:
        # Best-effort only; continue starting services even if refresh fails
        pass

    # Start infrastructure (Redis + RabbitMQ)
    print(f"{Colors.BOLD}1. Starting Infrastructure (Redis, RabbitMQ)...{Colors.ENDC}")
    subprocess.run(
        ["docker", "compose", "up", "redis", "rabbitmq", "-d"],
        shell=IS_WINDOWS,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f"{Colors.GREEN}   ✓ Infrastructure started{Colors.ENDC}\n")
    time.sleep(2)

    # Backend
    print(f"{Colors.BOLD}2. Starting Backend API...{Colors.ENDC}")

    def find_backend_python() -> Optional[str]:
        # Prefer backend/.venv, then project .venv, then fall back to current interpreter
        candidates = [os.path.join("backend", ".venv"), ".venv"]
        for vp in candidates:
            if os.path.isdir(vp):
                p = os.path.join(vp, "Scripts", "python.exe") if IS_WINDOWS else os.path.join(vp, "bin", "python")
                if os.path.exists(p):
                    return p
        return None

    if os.path.isdir("backend"):
        venv_dir = os.path.join("backend", ".venv")
        venv_python = find_backend_python()
        python_exec = venv_python or sys.executable

        backend_log_f = open(backend_log, "w")

        # Prefer the virtualenv python executable directly when available to avoid shell activation issues
        venv_python_exec = os.path.join(venv_dir, "bin", "python") if not IS_WINDOWS else os.path.join(venv_dir, "Scripts", "python.exe")
        if os.path.isdir(venv_dir) and os.path.exists(venv_python_exec):
            python_exec = venv_python_exec

        # Quick checks to warn about missing runtime packages (FastAPI)
        try:
            fastapi_check = subprocess.run([python_exec, "-c", "import fastapi"], capture_output=True)
            if fastapi_check.returncode != 0:
                print(f"{Colors.YELLOW}⚠️  The selected Python ({python_exec}) does not seem to have FastAPI installed. The backend may fail to start.{Colors.ENDC}")
                print(f"{Colors.CYAN}You can install backend dependencies by running:\n  cd backend && {python_exec} -m pip install -e .\nor re-run the setup wizard and let it install dependencies for you.{Colors.ENDC}")
        except Exception:
            pass

        # Ensure absolute path so it resolves regardless of cwd
        if not os.path.isabs(python_exec):
            python_exec = os.path.abspath(python_exec)
        subprocess.Popen([python_exec, "api.py"], cwd="backend", stdout=backend_log_f, stderr=backend_log_f, preexec_fn=(os.setpgrp if not IS_WINDOWS else None))
        print(f"{Colors.GREEN}   ✓ Backend starting with: {python_exec} (logs: {backend_log}){Colors.ENDC}\n")
    else:
        print(f"{Colors.RED}Backend directory not found; skipping backend start.{Colors.ENDC}")

    time.sleep(3)

    # Frontend
    print(f"{Colors.BOLD}3. Starting Frontend...{Colors.ENDC}")
    frontend_log_f = open(frontend_log, "w")
    subprocess.Popen("cd frontend && npm run dev", shell=True, stdout=frontend_log_f, stderr=frontend_log_f, preexec_fn=(os.setpgrp if not IS_WINDOWS else None))
    print(f"{Colors.GREEN}   ✓ Frontend starting (logs: {frontend_log}){Colors.ENDC}\n")

    time.sleep(2)

    # Worker
    print(f"{Colors.BOLD}4. Starting Background Worker...{Colors.ENDC}")
    worker_log_f = open(worker_log, "w")
    # Prefer explicit virtualenv python if available
    venv_python_exec = os.path.join("backend", ".venv", "bin", "python")
    if os.path.isdir(os.path.join("backend", ".venv")) and os.path.exists(venv_python_exec):
        python_exec = venv_python_exec

    # Quick check for dramatiq
    try:
        dramatiq_check = subprocess.run([python_exec, "-c", "import dramatiq"], capture_output=True)
        if dramatiq_check.returncode != 0:
            print(f"{Colors.YELLOW}⚠️  The selected Python ({python_exec}) does not seem to have Dramatiq installed. The worker may fail to start.{Colors.ENDC}")
            print(f"{Colors.CYAN}You can install backend dependencies by running:\n  cd backend && {python_exec} -m pip install -e .\nor re-run the setup wizard and let it install dependencies for you.{Colors.ENDC}")
    except Exception:
        pass

    # Ensure absolute path so it resolves regardless of cwd
    if not os.path.isabs(python_exec):
        python_exec = os.path.abspath(python_exec)

    subprocess.Popen([python_exec, "-m", "dramatiq", "run_agent_background"], cwd="backend", stdout=worker_log_f, stderr=worker_log_f, preexec_fn=(os.setpgrp if not IS_WINDOWS else None))
    print(f"{Colors.GREEN}   ✓ Background worker starting with: {python_exec} (logs: {worker_log}){Colors.ENDC}\n")

    if supabase_local:
        print(f"{Colors.BOLD}To stop Local Supabase:{Colors.ENDC}")
        print(f"  {Colors.CYAN}cd backend && npx supabase stop{Colors.ENDC}\n")

    print(f"\n{Colors.GREEN}{Colors.BOLD}✅ All services started!{Colors.ENDC}")
    print(f"{Colors.CYAN}🌐 Access Suna at: http://localhost:3000{Colors.ENDC}\n")
    print(f"{Colors.YELLOW}💡 Tip:{Colors.ENDC} View logs: tail -f {backend_log} {frontend_log} {worker_log}")

    # Automatically tail the logs in the foreground for convenience on POSIX systems.
    # This will block until the user quits (Ctrl+C). If `tail` is unavailable, we fall back to showing the tip.
    try:
        if not IS_WINDOWS:
            # Use the system 'tail' command to follow logs
            subprocess.run(["tail", "-f", backend_log, frontend_log, worker_log])
    except KeyboardInterrupt:
        # User interrupted tailing; return to shell
        print("\nStopped tailing logs.")
    except FileNotFoundError:
        # tail not found; already printed the tip above
        pass
    # Automatically tail logs in the foreground if 'tail' is available. This mirrors the suggested command
    # and gives immediate feedback to the user (press Ctrl-C to stop).
    try:
        import shutil
        tail_cmd = shutil.which("tail")
        if tail_cmd:
            print(f"{Colors.BOLD}Tailing logs (press Ctrl-C to stop):{Colors.ENDC}")
            subprocess.run([tail_cmd, "-f", backend_log, frontend_log, worker_log])
        else:
            print(f"{Colors.YELLOW}Note:{Colors.ENDC} 'tail' not found; run the printed tail command to view logs.")
    except KeyboardInterrupt:
        print("\nStopped tailing logs.")
    except Exception:
        print(f"{Colors.RED}Failed to tail logs automatically.{Colors.ENDC}")


def stop_manual_services() -> None:
    """Stops all manually started services (Unix-like)."""
    if IS_WINDOWS:
        print("On Windows, please stop services manually (Task Manager / npx supabase stop / docker compose down).")
        return

    print(f"{Colors.BOLD}Stopping Manual Services...{Colors.ENDC}")
    subprocess.run(["pkill", "-f", "python api.py"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "next dev"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "dramatiq run_agent_background"], stderr=subprocess.DEVNULL)
    subprocess.run(["docker", "compose", "down"], shell=IS_WINDOWS, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"{Colors.GREEN}✅ All manual services stopped (best-effort).{Colors.ENDC}")


def main() -> None:
    setup_method = get_setup_method()
    supabase_method = get_supabase_setup_method()

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: ./start.py [--help] [-f]")
        print("Start or stop local services. Uses the setup method selected in setup.py (docker or manual).")
        return

    force = "-f" in sys.argv

    # If setup hasn't been run or method is not determined, stop and instruct the user
    if not setup_method:
        print(f"{Colors.YELLOW}⚠️  Setup method not detected. Run './setup.py' first or configure Docker Compose as desired.{Colors.ENDC}")
        sys.exit(1)

    # Docker path
    if setup_method == "docker":
        print(f"{Colors.BLUE}{Colors.BOLD}Docker Setup Detected{Colors.ENDC}")
        running = docker_compose_is_up()
        if running:
            if force or input("🛑 Stop all Suna services? [y/N] ").strip().lower() == "y":
                stop_docker_services()
            else:
                print("Aborting.")
        else:
            if force or input("⚡ Start all Suna services? [Y/n] ").strip().lower() != "n":
                start_docker_services()
            else:
                print("Aborting.")

    else:
        # Manual setup — show instructions and offer convenience helpers
        print(f"{Colors.BLUE}{Colors.BOLD}Manual Setup Detected{Colors.ENDC}")

        # On Windows: show instructions and allow starting redis only (automation is limited)
        if IS_WINDOWS:
            print_manual_instructions(supabase_local=(supabase_method == "local"))
            if force or input("Start infrastructure now (docker redis only)? [Y/n] ").strip().lower() != "n":
                try:
                    subprocess.run(["docker", "compose", "up", "redis", "-d"], check=True, shell=True)
                    print(f"{Colors.GREEN}✅ Redis started.{Colors.ENDC}")
                except Exception:
                    print(f"{Colors.RED}Failed to start Redis via docker compose. Make sure Docker is running.{Colors.ENDC}")
            print("\nOnce other services are started (frontend/backend/worker), access Suna at: http://localhost:3000")
            return

        # POSIX path — continue with automatic start/stop handling
        # If any service is running, offer to stop
        backend_running = subprocess.run(["pgrep", "-f", "python api.py"], capture_output=True).returncode == 0
        frontend_running = subprocess.run(["pgrep", "-f", "next dev"], capture_output=True).returncode == 0
        worker_running = subprocess.run(["pgrep", "-f", "dramatiq run_agent_background"], capture_output=True).returncode == 0
        infra_up = subprocess.run(["docker", "compose", "ps", "-q", "redis"], capture_output=True, text=True, shell=IS_WINDOWS).stdout.strip() != ""

        any_running = backend_running or frontend_running or worker_running or infra_up

        if any_running:
            if not force and input("🛑 Stop all manual Suna services? [y/N] ").strip().lower() != "y":
                print("Aborting.")
                return

            stop_manual_services()
            return

        # Not running — start automatically without prompting. If the user prefers not to start services,
        # they can run './start.py -f' to force behavior or use the manual instructions below.
        print(f"{Colors.GREEN}⚡ No manual services detected — starting all manual Suna services now...{Colors.ENDC}")
        start_manual_services(supabase_local=(supabase_method == "local"))
        return


if __name__ == "__main__":
    main()