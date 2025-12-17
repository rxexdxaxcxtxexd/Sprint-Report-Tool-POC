"""
Docker Helper - Automatically start Docker Desktop if not running.

Ensures Docker Desktop is running before attempting JIRA MCP calls.
"""
import subprocess
import time
import sys
from pathlib import Path


def is_docker_running() -> bool:
    """Check if Docker daemon is running.

    Returns:
        True if Docker is running and responding to commands
    """
    try:
        result = subprocess.run(
            ['docker', 'ps'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def find_docker_desktop_path() -> Path:
    """Find Docker Desktop executable path on Windows.

    Returns:
        Path to Docker Desktop.exe

    Raises:
        FileNotFoundError: If Docker Desktop is not installed
    """
    # Common installation paths
    possible_paths = [
        Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"),
        Path(r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe"),
        Path.home() / "AppData" / "Local" / "Docker" / "Docker Desktop.exe",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Docker Desktop not found. Please install from:\n"
        "https://www.docker.com/products/docker-desktop/"
    )


def start_docker_desktop(wait: bool = True, timeout: int = 60) -> bool:
    """Start Docker Desktop if not already running.

    Args:
        wait: Whether to wait for Docker daemon to be ready
        timeout: Maximum seconds to wait for Docker to start

    Returns:
        True if Docker is running after this call

    Raises:
        FileNotFoundError: If Docker Desktop is not installed
        TimeoutError: If Docker fails to start within timeout
    """
    # Check if already running
    if is_docker_running():
        return True

    print("Docker Desktop is not running. Starting...")

    # Find Docker Desktop executable
    docker_path = find_docker_desktop_path()

    # Start Docker Desktop (Windows)
    try:
        subprocess.Popen(
            [str(docker_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
    except Exception as e:
        print(f"Failed to start Docker Desktop: {e}")
        return False

    if not wait:
        return True

    # Wait for Docker daemon to be ready
    print("Waiting for Docker daemon to start", end='', flush=True)
    start_time = time.time()

    while time.time() - start_time < timeout:
        if is_docker_running():
            print(" OK")
            return True

        print(".", end='', flush=True)
        time.sleep(2)

    print(" TIMEOUT")
    raise TimeoutError(
        f"Docker daemon failed to start within {timeout} seconds.\n"
        "Try starting Docker Desktop manually and wait for it to be ready."
    )


def ensure_docker_running(auto_start: bool = True, timeout: int = 60) -> None:
    """Ensure Docker is running, optionally starting it automatically.

    This is the main function to call before using JIRA MCP.

    Args:
        auto_start: Whether to automatically start Docker if not running
        timeout: Maximum seconds to wait for Docker to start

    Raises:
        RuntimeError: If Docker is not running and auto_start is False
        FileNotFoundError: If Docker Desktop is not installed
        TimeoutError: If Docker fails to start within timeout
    """
    if is_docker_running():
        return  # Already running

    if not auto_start:
        raise RuntimeError(
            "Docker Desktop is not running.\n"
            "Please start Docker Desktop manually or set auto_start=True."
        )

    # Auto-start Docker
    success = start_docker_desktop(wait=True, timeout=timeout)

    if not success:
        raise RuntimeError(
            "Failed to start Docker Desktop.\n"
            "Please start it manually and ensure it's ready."
        )


if __name__ == "__main__":
    """Test Docker helper."""
    print("Docker Helper - Test Mode\n")

    print("1. Checking if Docker is running...")
    if is_docker_running():
        print("   [OK] Docker is running")
    else:
        print("   [X] Docker is not running")

        print("\n2. Finding Docker Desktop...")
        try:
            docker_path = find_docker_desktop_path()
            print(f"   [OK] Found at: {docker_path}")
        except FileNotFoundError as e:
            print(f"   [X] {e}")
            sys.exit(1)

        print("\n3. Starting Docker Desktop...")
        try:
            ensure_docker_running(auto_start=True, timeout=60)
            print("   [OK] Docker is now running")
        except Exception as e:
            print(f"   [X] Failed: {e}")
            sys.exit(1)

    print("\n[OK] All checks passed!")
