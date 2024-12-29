# More about Model Context Protocol (MCP) and how to create custom MCP servers at https://modelcontextprotocol.io/introduction

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_errors import (CommandNotFoundError, ConfigError, MCPError,
                        ServerInitError, ToolExecutionError)

from console_gpt.config_manager import _join_and_check
from console_gpt.custom_stdout import custom_print

BASE_PATH = os.path.dirname(os.path.realpath(f"{__file__}/.."))
MCP_SAMPLE_PATH = _join_and_check(BASE_PATH, "mcp_config.json.sample", target="mcp_config.json")
MCP_PATH = _join_and_check(BASE_PATH, "mcp_config.json", create="mcp_config.json")


class MCPServer:
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self.client = None
        self.tools: Dict[str, Tool] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def cleanup(self):
        """Cleanup server resources"""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception:
                pass
        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception:
                pass


class MCPTCPServer:
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.servers: Dict[str, MCPServer] = {}
        self.initialization_timeout = 30  # 30 seconds timeout for tool initialization
        self.server_processes: Dict[str, subprocess.Popen] = {}

    @staticmethod
    def tool_to_dict(tool: Tool) -> Dict[str, Any]:
        """Convert a Tool object to a dictionary with the specified schema."""
        return {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": (
                tool.inputSchema
                if hasattr(tool, "inputSchema")
                else {"type": "object", "properties": {}, "required": []}
            ),
        }

    @staticmethod
    def get_executable_path(command: str) -> str:
        """Get the full path of an executable, considering the OS."""
        if not command or not isinstance(command, str):
            raise CommandNotFoundError(command, available_paths=os.environ.get("PATH", "").split(os.pathsep))

        def check_common_paths(cmd: str) -> Optional[str]:
            common_paths = [
                f"/usr/local/bin/{cmd}",
                f"/usr/bin/{cmd}",
                f"/opt/homebrew/bin/{cmd}",
                os.path.expanduser(f"~/.nvm/current/bin/{cmd}"),
                os.path.expanduser(f"~/.npm-global/bin/{cmd}"),
                os.path.expanduser(f"~/.local/bin/{cmd}"),
            ]
            return next((path for path in common_paths if os.path.isfile(path)), None)

        try:
            # Check if it's a full path
            if os.path.sep in command and os.path.isfile(command):
                return command

            # Try using shutil.which first
            if path := shutil.which(command):
                return path

            # Try common paths
            if path := check_common_paths(command):
                return path

            # Special handling for Node.js related commands
            if command in ["node", "npm", "npx", "uv", "uvx"]:
                try:
                    npm_path = shutil.which("npm")
                    if npm_path:
                        result = subprocess.run([npm_path, "bin", "-g"], capture_output=True, text=True, check=True)
                        global_bin = result.stdout.strip()
                        potential_path = os.path.join(global_bin, command)
                        if os.path.isfile(potential_path):
                            return potential_path
                except Exception:
                    pass

            # If we get here, command wasn't found
            available_paths = os.environ.get("PATH", "").split(os.pathsep)
            raise CommandNotFoundError(command, available_paths=available_paths)

        except Exception as e:
            if isinstance(e, CommandNotFoundError):
                raise
            available_paths = os.environ.get("PATH", "").split(os.pathsep)
            raise CommandNotFoundError(command, available_paths=available_paths) from e

    @staticmethod
    def load_config() -> Dict[str, Dict[str, Any]]:
        """Load and parse the MCP configuration file."""
        try:
            with open(MCP_PATH, "r") as f:
                config = json.load(f)
                return config.get("mcpServers", {})
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file: {str(e)}", MCP_PATH)
        except FileNotFoundError:
            raise ConfigError(f"Config file not found", MCP_PATH)
        except Exception as e:
            raise ConfigError(f"Error reading config file: {str(e)}", MCP_PATH)

    async def init_server(self, server_name: str, server_config: Dict[str, Any]) -> MCPServer:
        """Initialize a single MCP server."""
        server = MCPServer(server_name, server_config)
        read_stream = None  # Initialize to None
        write_stream = None  # Initialize to None

        try:
            command_path = self.get_executable_path(server_config["command"])

            env = os.environ.copy()
            env["NODE_NO_WARNINGS"] = "1"
            if "env" in server_config:
                env.update(server_config["env"])

            server_params = StdioServerParameters(command=command_path, args=server_config.get("args", []), env=env)

            # Start the server process and store it
            process = subprocess.Popen(
                [command_path] + server_config.get("args", []),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.server_processes[server_name] = process

            server.client = stdio_client(server_params)
            read_stream, write_stream = await server.client.__aenter__()
            server.session = ClientSession(read_stream, write_stream)
            await server.session.__aenter__()
            await server.session.initialize()

            tools_list = await server.session.list_tools()
            server.tools = {tool.name: tool for tool in tools_list.tools if isinstance(tool, Tool)}

            return server

        except CommandNotFoundError as e:
            await server.cleanup()
            custom_print("error", f"Command not found error for server {server_name}: {str(e)}")
            raise

        except Exception as e:
            if read_stream is not None and write_stream is not None:
                await server.cleanup()
            raise ServerInitError(str(e), server_name)

    async def initialize_tools(self) -> Tuple[List[Dict[str, Any]], List[Exception]]:
        """Initialize all MCP tools asynchronously with timeout."""
        config = {}
        all_tools = []
        initialization_errors = []

        try:
            config = self.load_config()
        except ConfigError as e:
            initialization_errors.append(e)
            await self.cleanup()
            return [], initialization_errors
        except Exception as e:
            initialization_errors.append(e)
            await self.cleanup()
            return [], initialization_errors

        async def init_with_timeout(server_name: str, server_config: Dict[str, Any]):
            custom_print("info", f"Initializing server: {server_name}")
            try:
                server = await asyncio.wait_for(
                    self.init_server(server_name, server_config), timeout=self.initialization_timeout
                )
                self.servers[server_name] = server
                custom_print("info", f"Server {server_name} initialized successfully")
                return [self.tool_to_dict(tool) for tool in server.tools.values()]
            except asyncio.TimeoutError:
                error = ServerInitError(
                    f"Server initialization timed out after {self.initialization_timeout} seconds", server_name
                )
                self.servers[server_name] = error  # Store the error
                initialization_errors.append(error)
                custom_print("error", f"TimeoutError initializing server {server_name}")
                return []
            except Exception as e:
                custom_print("error", f"Exception caught in init_with_timeout for {server_name}: {e}")

                # Try to get more details from specific exception types
                if isinstance(e, CommandNotFoundError):
                    error_details = e.to_dict()
                    custom_print("error", f"CommandNotFoundError details: {error_details}")
                elif isinstance(e, ServerInitError):
                    error_details = e.to_dict()
                    custom_print("error", f"ServerInitError details: {error_details}")
                else:
                    error_details = {
                        "error_type": type(e).__name__,
                        "message": str(e),
                    }
                    custom_print("error", f"Other exception details: {error_details}")

                error = ServerInitError(f"Server initialization failed: {e}", server_name)
                error.details = error_details
                self.servers[server_name] = error  # Store the error
                initialization_errors.append(error)
                return []

        tasks = [init_with_timeout(name, config) for name, config in config.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten the results list and filter out empty lists and exceptions
        all_tools = [tool for sublist in results if isinstance(sublist, list) for tool in sublist]

        return all_tools, initialization_errors

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle individual TCP client connections."""
        try:
            while True:
                length_bytes = await reader.read(4)
                if not length_bytes:
                    break

                msg_length = int.from_bytes(length_bytes, "big")
                data = await reader.read(msg_length)
                if not data:
                    break

                request = json.loads(data.decode())
                command = request.get("command")
                response = {"status": "error", "error": MCPError("INVALID_COMMAND", "Invalid command").to_dict()}

                try:
                    if command == "call_tool":
                        tool_name = request["tool_name"]
                        arguments = request["arguments"]

                        # Find server for tool
                        server = next(
                            (s for s in self.servers.values() if isinstance(s, MCPServer) and tool_name in s.tools),
                            None,
                        )

                        # Check if server failed to initialize
                        failed_server = next(
                            (
                                s
                                for s in self.servers.values()
                                if isinstance(s, Exception) and not isinstance(s, MCPServer)
                            ),
                            None,
                        )

                        if failed_server:
                            # Return the initialization error
                            if isinstance(failed_server, CommandNotFoundError):
                                response = {"status": "error", "error": failed_server.to_dict()}
                            else:
                                response = {
                                    "status": "error",
                                    "error": MCPError("SERVER_ERROR", "Server initialization failed").to_dict(),
                                }

                        elif not server:
                            raise ToolExecutionError(f"Tool not found", tool_name, arguments)

                        else:
                            result = await server.session.call_tool(tool_name, arguments)
                            response = {"status": "success", "result": str(result)}

                    elif command == "get_tools":
                        tools = []
                        initialization_errors = []
                        for server_name, server in self.servers.items():
                            if isinstance(server, MCPServer):
                                tools.extend(self.tool_to_dict(tool) for tool in server.tools.values())
                            elif isinstance(server, Exception):
                                initialization_errors.append(
                                    {
                                        "server": server_name,
                                        "error": server.to_dict() if hasattr(server, "to_dict") else str(server),
                                    }
                                )

                        response = {
                            "status": "success",
                            "tools": tools,
                            "initialization_errors": initialization_errors if initialization_errors else None,
                        }

                except Exception as e:
                    if isinstance(e, (ConfigError, ServerInitError, ToolExecutionError, CommandNotFoundError)):
                        response = {"status": "error", "error": e.to_dict()}
                    else:
                        response = {"status": "error", "error": MCPError("UNKNOWN_ERROR", str(e)).to_dict()}

                # Ensure response is sent and connection is drained
                response_data = json.dumps(response).encode()
                writer.write(len(response_data).to_bytes(4, "big"))
                writer.write(response_data)
                await writer.drain()  # Make sure data is sent before continuing

        except Exception as e:
            custom_print("error", f"Error handling client: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def cleanup(self):
        """Cleanup all MCP sessions and connections."""
        cleanup_tasks = [
            asyncio.wait_for(server.cleanup(), timeout=5)
            for server in self.servers.values()
            if isinstance(server, MCPServer)
        ]
        results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                custom_print("error", f"Error during server cleanup: {res}")

        self.servers.clear()

        # Terminate server processes
        for server_name, process in self.server_processes.items():
            if process.poll() is None:  # Check if process is still running
                custom_print("info", f"Terminating server process: {server_name}")
                try:
                    if os.name == "nt":
                        process.send_signal(signal.CTRL_C_EVENT)
                    else:
                        process.send_signal(signal.SIGTERM)

                    process.wait(timeout=5)  # Wait for process to terminate
                except subprocess.TimeoutExpired:
                    custom_print("warning", f"Force killing server process: {server_name}")
                    process.kill()
        self.server_processes.clear()

    async def start(self):
        """Start the TCP server and initialize MCP tools."""
        try:
            # Initialize MCP tools first
            tools, errors = await self.initialize_tools()

            # Check if config load failed and prevent server start
            config_error = next((e for e in errors if isinstance(e, ConfigError)), None)
            if config_error:
                custom_print("error", f"Failed to start server: {config_error}", exit_code=1)

            # Start TCP server even if some tools failed to initialize
            server = await asyncio.start_server(self.handle_client, self.host, self.port)

            # Print information about successful tool initialization
            if tools:
                custom_print("info", f"Total tools initialized: {len(tools)}")
                for tool_info in tools:
                    custom_print("info", f"  - {tool_info['name']}: {tool_info['description']}")

            # Print information about failed tool initializations
            if errors:
                custom_print("error", f"Failed to initialize {len(errors)} servers:")
                for error in errors:
                    if isinstance(error, Exception):
                        custom_print("error", f"  - {error}")

            async with server:
                custom_print("info", f"Server running on {self.host}:{self.port}")
                await server.serve_forever()

        except Exception as e:
            custom_print("error", f"Server error: {e}")
            await self.cleanup()
            raise

    def shutdown_signal_handler(self):
        """Handle shutdown signals."""
        custom_print("info", "\nReceived shutdown signal...")
        asyncio.create_task(self.cleanup())


if __name__ == "__main__":
    server = MCPTCPServer()

    async def main():
        try:
            await server.start()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            await server.cleanup()

    asyncio.run(main())
