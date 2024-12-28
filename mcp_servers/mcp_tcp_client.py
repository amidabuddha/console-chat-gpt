import json
import socket
from typing import Any, Dict, List, Tuple

# Update the import to use relative import
from .server_manager import ServerManager


class MCPClient:
    def __init__(self, host: str = "localhost", port: int = 8765, auto_start: bool = True):
        self.host = host
        self.port = port
        self.sock = None
        self.server_manager = ServerManager(host, port)
        self.auto_start = auto_start

    def ensure_server_running(self) -> Tuple[bool, str]:
        """Ensure the server is running before connecting."""
        if not self.server_manager.is_server_running():
            success, message = self.server_manager.start_server()
            if not success:
                raise ConnectionError(f"Failed to start server: {message}")
            return success, message
        return True, "Server is already running"

    def connect(self):
        """Establish connection to the server."""
        if self.auto_start:
            self.ensure_server_running()

        if self.sock is None:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
            except ConnectionRefusedError:
                if self.auto_start:
                    raise ConnectionError("Failed to connect to server even after starting it")
                else:
                    raise ConnectionError("Server is not running. Enable auto_start or start the server manually")

    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        # Ensure connection before sending request
        self.connect()

        try:
            # Serialize and send request
            data = json.dumps(request).encode()
            self.sock.sendall(len(data).to_bytes(4, "big"))
            self.sock.sendall(data)

            # Read response length
            length_bytes = self.sock.recv(4)
            if not length_bytes:
                raise ConnectionError("Connection closed by server")

            msg_length = int.from_bytes(length_bytes, "big")

            # Read response data
            chunks = []
            bytes_received = 0
            while bytes_received < msg_length:
                chunk = self.sock.recv(min(msg_length - bytes_received, 4096))
                if not chunk:
                    raise ConnectionError("Connection closed by server")
                chunks.append(chunk)
                bytes_received += len(chunk)

            response_data = b"".join(chunks)
            return json.loads(response_data.decode())

        except (ConnectionError, socket.error) as e:
            # Close the socket on connection errors
            self.close()
            raise ConnectionError(f"Communication error: {str(e)}")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        request = {"command": "call_tool", "tool_name": tool_name, "arguments": arguments}

        response = self._send_request(request)
        if response["status"] == "error":
            raise Exception(response["message"])
        return response["result"]

    def get_available_tools(self) -> List[Dict[str, Any]]:
        request = {"command": "get_tools"}
        response = self._send_request(request)
        if response["status"] == "error":
            raise Exception(response["message"])
        return response["tools"]

    def start_server(self) -> Tuple[bool, str]:
        """Start the server if it's not running."""
        return self.server_manager.start_server()

    def stop_server(self) -> Tuple[bool, str]:
        """Stop the server."""
        if self.sock:
            self.close()
        return self.server_manager.stop_server()

    def close(self):
        """Close the client connection."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            finally:
                self.sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
