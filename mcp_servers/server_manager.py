import os
import signal
import socket
import subprocess
import sys
import time
from typing import Optional, Tuple

import psutil
from console_gpt.custom_stdout import custom_print

class ServerManager:
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.server_process: Optional[subprocess.Popen] = None
        self.server_script = os.path.join(os.path.dirname(__file__), "mcp_tcp_server.py")

    def is_port_open(self) -> bool:
        """Check if the server port is open."""
        try:
            with socket.create_connection((self.host, self.port), timeout=1):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            return False

    def is_process_running(self) -> bool:
        """Check if the server process is running."""
        return self.find_server_process() is not None

    def is_server_running(self) -> bool:
        """Check if the server is fully running by checking both process and port."""
        return self.is_process_running() and self.is_port_open()

    def find_server_process(self) -> Optional[psutil.Process]:
        """Find the server process if it's running"""
        if self.server_process and self.server_process.poll() is None:
            return self.server_process

        server_name = os.path.basename(self.server_script)
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["cmdline"]:
                    cmdline = " ".join(proc.info["cmdline"])
                    if server_name in cmdline and "python" in cmdline.lower():
                        return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return None

    def start_server(self) -> Tuple[bool, str]:
        """Start the server if it's not already running."""
        if self.is_server_running():
            return True, "Server is already running"

        try:
            custom_print("info", "Starting MCP server...")

            # Start the server as a subprocess
            if os.name == "nt":  # Windows
                self.server_process = subprocess.Popen(
                    [sys.executable, self.server_script],
                    stdout=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:  # Unix-like systems
                self.server_process = subprocess.Popen(
                    [sys.executable, self.server_script],
                    stdout=subprocess.PIPE,
                    start_new_session=True,
                )

            start_time = time.time()
            while time.time() - start_time < 60:
                time.sleep(0.5)
                if self.is_port_open():
                    custom_print("info", "Server is accepting connections.")
                    return True, "Server process started successfully"

            return False, "Server failed to start: Port did not open within timeout"

        except Exception as e:
            if self.server_process:
                try:
                    self.stop_server()
                except Exception:
                    pass
            return False, f"Failed to start server: {str(e)}"

    def stop_server(self) -> Tuple[bool, str]:
        """Stop the server."""
        if not self.is_server_running():
            return True, "Server is not running"

        try:
            custom_print("info", "Stopping MCP server...")
            server_proc = self.find_server_process()

            if server_proc:
                # Try graceful shutdown first
                if os.name == "nt":  # Windows
                    server_proc.send_signal(signal.CTRL_C_EVENT)
                else:  # Unix-like systems
                    server_proc.send_signal(signal.SIGTERM)

                # Wait for the process to terminate (max 5 seconds)
                for _ in range(10):
                    if not self.is_server_running():
                        self.server_process = None
                        custom_print("info", "Server stopped successfully")
                        return True, "Server stopped successfully"
                    time.sleep(0.5)

                # If server still running, force kill
                custom_print("warn", "Server didn't stop gracefully, forcing shutdown...")
                if os.name == "nt":
                    server_proc.kill()
                else:
                    server_proc.send_signal(signal.SIGKILL)

                self.server_process = None
                for _ in range(10):
                    if not self.is_port_open():
                        break
                    time.sleep(0.5)
                else:
                    return False, "Failed to stop server: Port still in use"

                return True, "Server force stopped"
            else:
                return False, "Could not find server process to stop"

        except Exception as e:
            return False, f"Failed to stop server: {str(e)}"

    def release_port(self):
        """Attempts to release the port using OS-specific commands."""
        try:
            if os.name == "posix":  # Linux/Mac
                # Use lsof to find the process ID (PID) using the port and kill it
                result = subprocess.run(
                    ["lsof", "-t", "-i", f":{self.port}"],
                    capture_output=True,
                    text=True,
                )
                pid = result.stdout.strip()
                if pid:
                    custom_print("warn", f"Killing process {pid} using port {self.port}")
                    os.kill(int(pid), signal.SIGKILL)
            elif os.name == "nt":  # Windows
                # Use netstat and taskkill to find and kill the process
                result = subprocess.run(
                    ["netstat", "-ano", "|", "findstr", f":{self.port}"],
                    capture_output=True,
                    text=True,
                    shell=True,  # Needed for piped commands on Windows
                )
                lines = result.stdout.splitlines()
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 5 and parts[1].endswith(f":{self.port}"):
                        pid = parts[4]
                        custom_print("warn", f"Killing process {pid} using port {self.port}")
                        subprocess.run(
                            ["taskkill", "/F", "/PID", pid],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
            time.sleep(1) # Give it some time to cleanup after killing
        except Exception as e:
            custom_print("error", f"Failed to release port: {str(e)}")