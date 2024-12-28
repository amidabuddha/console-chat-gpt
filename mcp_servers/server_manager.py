import subprocess
import os
import signal
import time
import socket
import sys
import psutil
from typing import Optional, Tuple

class ServerManager:
    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.host = host
        self.port = port
        self.server_process: Optional[subprocess.Popen] = None
        self.server_script = os.path.join(os.path.dirname(__file__), 'mcp_tcp_server.py')

    def is_server_running(self) -> bool:
        """Check if the server is running by attempting to connect to it."""
        try:
            with socket.create_connection((self.host, self.port), timeout=1):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False

    def find_server_process(self) -> Optional[psutil.Process]:
        """Find the server process if it's running"""
        server_name = os.path.basename(self.server_script)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if server_name in cmdline and 'python' in cmdline.lower():
                        return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return None

    def start_server(self) -> Tuple[bool, str]:
        """Start the server if it's not already running."""
        if self.is_server_running():
            return True, "Server is already running"

        try:
            # Start the server as a subprocess
            if os.name == 'nt':  # Windows
                self.server_process = subprocess.Popen(
                    [sys.executable, self.server_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:  # Unix-like systems
                self.server_process = subprocess.Popen(
                    [sys.executable, self.server_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )

            # Wait for the server to start (max 5 seconds)
            for _ in range(10):
                if self.is_server_running():
                    return True, "Server started successfully"
                time.sleep(0.5)

            # If server didn't start, try to clean up
            self.stop_server()
            return False, "Server failed to start within timeout"
            
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
            server_proc = self.find_server_process()
            if server_proc:
                # Try graceful shutdown first
                if os.name == 'nt':  # Windows
                    server_proc.send_signal(signal.CTRL_C_EVENT)
                else:  # Unix-like systems
                    server_proc.send_signal(signal.SIGTERM)
                
                # Wait for the process to terminate (max 5 seconds)
                for _ in range(10):
                    if not self.is_server_running():
                        self.server_process = None
                        return True, "Server stopped successfully"
                    time.sleep(0.5)

                # If server still running, force kill
                if os.name == 'nt':  # Windows
                    server_proc.kill()
                else:  # Unix-like systems
                    server_proc.send_signal(signal.SIGKILL)
                
                self.server_process = None
                return True, "Server force stopped"
            
            else:
                # Try to find and kill the process by port
                if os.name == 'posix':  # Linux/Mac
                    subprocess.run(['pkill', '-f', f'python.*{self.server_script}'])
                else:  # Windows
                    subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 
                                  f'WINDOWTITLE eq python*{os.path.basename(self.server_script)}*'],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return True, "Server stopped using system commands"

        except Exception as e:
            return False, f"Failed to stop server: {str(e)}"