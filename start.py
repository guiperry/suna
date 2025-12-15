#!/usr/bin/env python3

import subprocess
import sys
import platform
import os
import json

IS_WINDOWS = platform.system() == "Windows"
PROGRESS_FILE = ".setup_progress"


# --- ANSI Colors ---
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def load_progress():
    """Loads the last saved step and data from setup."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            try:
                return json.load(f)
            except (json.JSONDecodeError, KeyError):
                return {"step": 0, "data": {}}
    return {"step": 0, "data": {}}


def get_setup_method():
    """Gets the setup method chosen during setup."""
    progress = load_progress()
    return progress.get("data", {}).get("setup_method")


def check_docker_compose_up():
    result = subprocess.run(
        ["docker", "compose", "ps", "-q"],
        capture_output=True,
        text=True,
        shell=IS_WINDOWS,
    )
    return len(result.stdout.strip()) > 0


def start_manual_services():
    """Automatically starts all services for manual setup."""
    import time

    print(f"\n{Colors.BLUE}{Colors.BOLD}🚀 Starting Suna Services{Colors.ENDC}\n")

    # Check if services are already running
    backend_running = subprocess.run(
        ["pgrep", "-f", "python api.py"],
        capture_output=True
    ).returncode == 0

    frontend_running = subprocess.run(
        ["pgrep", "-f", "next dev"],
        capture_output=True
    ).returncode == 0

    if backend_running or frontend_running:
        print(f"{Colors.YELLOW}⚠️  Some services are already running.{Colors.ENDC}")
        print(f"   Backend: {'✓ Running' if backend_running else '✗ Stopped'}")
        print(f"   Frontend: {'✓ Running' if frontend_running else '✗ Stopped'}")
        print(f"\nUse '{Colors.CYAN}./start.py{Colors.ENDC}' again to stop all services.\n")
        return

    # Start infrastructure
    print(f"{Colors.BOLD}1. Starting Infrastructure (Redis, RabbitMQ)...{Colors.ENDC}")
    subprocess.run(
        ["docker", "compose", "up", "redis", "rabbitmq", "-d"],
        shell=IS_WINDOWS,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f"{Colors.GREEN}   ✓ Infrastructure started{Colors.ENDC}\n")
    time.sleep(2)

    # Start backend
    print(f"{Colors.BOLD}2. Starting Backend API...{Colors.ENDC}")
    backend_log = open("/tmp/suna_backend.log", "w")
    subprocess.Popen(
        ["bash", "-c", "cd backend && source .venv/bin/activate && python api.py"],
        stdout=backend_log,
        stderr=backend_log,
        preexec_fn=os.setpgrp if not IS_WINDOWS else None
    )
    print(f"{Colors.GREEN}   ✓ Backend starting (logs: /tmp/suna_backend.log){Colors.ENDC}\n")
    time.sleep(3)

    # Start frontend
    print(f"{Colors.BOLD}3. Starting Frontend...{Colors.ENDC}")
    frontend_log = open("/tmp/suna_frontend.log", "w")
    subprocess.Popen(
        "cd frontend && npm run dev",
        shell=True,
        stdout=frontend_log,
        stderr=frontend_log,
        preexec_fn=os.setpgrp if not IS_WINDOWS else None
    )
    print(f"{Colors.GREEN}   ✓ Frontend starting (logs: /tmp/suna_frontend.log){Colors.ENDC}\n")
    time.sleep(2)

    # Start background worker
    print(f"{Colors.BOLD}4. Starting Background Worker...{Colors.ENDC}")
    worker_log = open("/tmp/suna_worker.log", "w")
    subprocess.Popen(
        ["bash", "-c", "cd backend && source .venv/bin/activate && python -m dramatiq run_agent_background"],
        stdout=worker_log,
        stderr=worker_log,
        preexec_fn=os.setpgrp if not IS_WINDOWS else None
    )
    print(f"{Colors.GREEN}   ✓ Background worker starting (logs: /tmp/suna_worker.log){Colors.ENDC}\n")

    print(f"{Colors.GREEN}{Colors.BOLD}✅ All services started!{Colors.ENDC}\n")
    print(f"{Colors.CYAN}🌐 Access Suna at: http://localhost:3000{Colors.ENDC}\n")
    print(f"{Colors.YELLOW}💡 Tips:{Colors.ENDC}")
    print(f"   • View logs: tail -f /tmp/suna_*.log")
    print(f"   • Stop services: {Colors.CYAN}./start.py{Colors.ENDC}")
    print()

def stop_manual_services():
    """Stops all manually started services."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}🛑 Stopping Suna Services{Colors.ENDC}\n")

    # Stop backend
    print(f"{Colors.BOLD}Stopping Backend...{Colors.ENDC}")
    subprocess.run(["pkill", "-f", "python api.py"], stderr=subprocess.DEVNULL)

    # Stop frontend
    print(f"{Colors.BOLD}Stopping Frontend...{Colors.ENDC}")
    subprocess.run(["pkill", "-f", "next dev"], stderr=subprocess.DEVNULL)

    # Stop background worker
    print(f"{Colors.BOLD}Stopping Background Worker...{Colors.ENDC}")
    subprocess.run(["pkill", "-f", "dramatiq run_agent_background"], stderr=subprocess.DEVNULL)

    # Stop infrastructure
    print(f"{Colors.BOLD}Stopping Infrastructure...{Colors.ENDC}")
    subprocess.run(["docker", "compose", "down"], shell=IS_WINDOWS, stdout=subprocess.DEVNULL)

    print(f"\n{Colors.GREEN}✅ All services stopped.{Colors.ENDC}\n")


def main():
    setup_method = get_setup_method()

    if "--help" in sys.argv:
        print("Usage: ./start.py [OPTION]")
        print("Manage Suna services based on your setup method")
        print("\nOptions:")
        print("  -f\tForce start containers without confirmation")
        print("  --help\tShow this help message")
        return

    # If setup hasn't been run or method is not determined, default to docker
    if not setup_method:
        print(
            f"{Colors.YELLOW}⚠️  Setup method not detected. Run './setup.py' first or using Docker Compose as default.{Colors.ENDC}"
        )
        setup_method = "docker"

    if setup_method == "manual":
        # For manual setup, automatically start/stop all services
        print(f"{Colors.BLUE}{Colors.BOLD}Manual Setup Detected{Colors.ENDC}")

        force = "-f" in sys.argv
        if force:
            print("Force awakened. Skipping confirmation.")

        # Check if any services are running
        backend_running = subprocess.run(
            ["pgrep", "-f", "python api.py"],
            capture_output=True
        ).returncode == 0

        frontend_running = subprocess.run(
            ["pgrep", "-f", "next dev"],
            capture_output=True
        ).returncode == 0

        is_running = backend_running or frontend_running

        if is_running:
            action = "stop"
            msg = "🛑 Stop all Suna services? [y/N] "
        else:
            action = "start"
            msg = "⚡ Start all Suna services? [Y/n] "

        if not force:
            response = input(msg).strip().lower()
            if action == "stop":
                if response != "y":
                    print("Aborting.")
                    return
            else:
                if response == "n":
                    print("Aborting.")
                    return

        if action == "stop":
            stop_manual_services()
        else:
            start_manual_services()

    else:  # docker setup
        print(f"{Colors.BLUE}{Colors.BOLD}Docker Setup Detected{Colors.ENDC}")
        print("Managing all Suna services with Docker Compose...\n")

        force = "-f" in sys.argv
        if force:
            print("Force awakened. Skipping confirmation.")

        is_up = check_docker_compose_up()

        if is_up:
            action = "stop"
            msg = "🛑 Stop all Suna services? [y/N] "
        else:
            action = "start"
            msg = "⚡ Start all Suna services? [Y/n] "

        if not force:
            response = input(msg).strip().lower()
            if action == "stop":
                if response != "y":
                    print("Aborting.")
                    return
            else:
                if response == "n":
                    print("Aborting.")
                    return

        if action == "stop":
            subprocess.run(["docker", "compose", "down"], shell=IS_WINDOWS)
            print(f"\n{Colors.GREEN}✅ All Suna services stopped.{Colors.ENDC}")
        else:
            subprocess.run(["docker", "compose", "up", "-d"], shell=IS_WINDOWS)
            print(f"\n{Colors.GREEN}✅ All Suna services started.{Colors.ENDC}")
            print(f"{Colors.CYAN}🌐 Access Suna at: http://localhost:3000{Colors.ENDC}")


if __name__ == "__main__":
    main()
