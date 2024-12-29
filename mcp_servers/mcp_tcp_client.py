import json
import socket
from typing import Any, Dict, List, Tuple

from console_gpt.custom_stdout import custom_print

from .mcp_errors import MCPError
from .server_manager import ServerManager


class MCPClientError(Exception):
    def __init__(self, error: MCPError):
        self.error = error
        super().__init__(str(error.message))


class MCPClient:
    _server_failed = False  # Class-level flag to track server failure

    def __init__(self, host: str = "localhost", port: int = 8765, auto_start: bool = True):
        self.host = host
        self.port = port
        self.sock = None
        self.server_manager = ServerManager(host, port)
        self.auto_start = auto_start

    def _connect(self) -> bool:
        """Internal method to establish connection."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            return True

        except ConnectionRefusedError as e:
            self.sock = None
            custom_print("error", f"Connection refused: {e}")
            if self.auto_start:
                custom_print("error", "Failed to connect to MCP server even after starting it")
            else:
                custom_print("error", "MCP Server is not running.")
            return False
        except Exception as e:
            self.sock = None
            custom_print("error", f"Error during connection attempt: {e}")
            return False

    def _handle_response(self, response: Dict[str, Any]) -> Any:
        """Handle server response and raise appropriate exceptions."""
        if response["status"] == "error":
            error_data = response["error"]
            error = MCPError.from_dict(error_data)
            raise MCPClientError(error)
        return response.get("result")

    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the server and receive the response."""
        try:
            data = json.dumps(request).encode()
            self.sock.sendall(len(data).to_bytes(4, "big"))
            self.sock.sendall(data)

            length_bytes = self.sock.recv(4)
            if not length_bytes:
                raise ConnectionError("Connection closed by server")

            msg_length = int.from_bytes(length_bytes, "big")

            chunks = []
            bytes_received = 0
            while bytes_received < msg_length:
                chunk = self.sock.recv(min(msg_length - bytes_received, 4096))
                if not chunk:
                    raise ConnectionError("Connection closed by server")
                chunks.append(chunk)
                bytes_received += len(chunk)

            response_data = b"".join(chunks)
            if response_data:
                try:
                    return json.loads(response_data.decode())
                except json.JSONDecodeError as e:
                    custom_print("error", f"Failed to decode JSON response: {e}")
                    return {"status": "error", "error": {"type": "JSON_DECODE_ERROR", "message": str(e)}}
            else:
                return {
                    "status": "error",
                    "error": {"type": "EMPTY_RESPONSE", "message": "Empty response received from server"},
                }
        except (ConnectionError, socket.error, Exception) as e:
            custom_print("error", f"Communication error: {str(e)}")
            self.close()
            return {"status": "error", "error": {"type": "CONNECTION_ERROR", "message": str(e)}}

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the server."""
        request = {"command": "call_tool", "tool_name": tool_name, "arguments": arguments}

        response = self._send_request(request)
        return self._handle_response(response)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from the server."""
        request = {"command": "get_tools"}
        response = self._send_request(request)

        # Check for initialization errors
        if response.get("initialization_errors"):
            for error in response["initialization_errors"]:
                custom_print("error", f"Server '{error['server']}' failed to initialize: {error['error']}")

        return response.get("tools", [])

    def start_server(self) -> Tuple[bool, str]:
        """Start the server if it's not running."""
        return self.server_manager.start_server()

    def stop_server(self) -> Tuple[bool, str]:
        """Stop the server."""
        if MCPClient._server_failed:  # Skip if we know server failed to start
            return True, "Server was not running"

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
        """Context manager entry - ensures server is running and connects."""
        if MCPClient._server_failed:
            return None

        if self.auto_start:
            if not self.server_manager.is_server_running():
                success, message = self.server_manager.start_server()
                if not success:
                    custom_print("error", f"Failed to start MCP server: {message}")
                    MCPClient._server_failed = True
                    self.close()
                    return None

        if not self._connect():
            return None  # Return None if connection fails
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes the connection."""
        self.close()
        # Don't suppress exceptions unless they're connection-related
        return isinstance(exc_val, (ConnectionError, MCPClientError))
