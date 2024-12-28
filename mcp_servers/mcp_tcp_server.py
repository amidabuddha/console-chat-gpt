# More about Model Context Protocol (MCP) and how to create custom MCP servers at https://modelcontextprotocol.io/introduction

import asyncio
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from console_gpt.config_manager import _join_and_check
from console_gpt.custom_stdout import custom_print

BASE_PATH = os.path.dirname(os.path.realpath(f"{__file__}/.."))
MCP_SAMPLE_PATH = _join_and_check(BASE_PATH, "mcp_config.json.sample", target="mcp_config.json")
MCP_PATH = _join_and_check(BASE_PATH, "mcp_config.json", create="mcp_config.json")


class MCPToolError(Exception):
    """Custom exception for MCP tool initialization errors"""

    pass


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

    @staticmethod
    def tool_to_dict(tool: Tool) -> Dict[str, Any]:
        """
        Convert a Tool object to a dictionary with the specified schema.
        """
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

        if os.path.sep in command and os.path.isfile(command):
            return command

        if path := shutil.which(command):
            return path

        if path := check_common_paths(command):
            return path

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

        available_paths = os.environ.get("PATH", "").split(os.pathsep)
        raise MCPToolError(
            f"Command '{command}' not found. Please ensure it's installed and in your PATH.\n"
            f"Current PATH directories:\n{json.dumps(available_paths, indent=2)}"
        )

    @staticmethod
    def load_config() -> Dict[str, Dict[str, Any]]:
        """Load and parse the MCP configuration file."""
        try:
            with open(MCP_PATH, "r") as f:
                config = json.load(f)
                return config.get("mcpServers", {})
        except json.JSONDecodeError as e:
            raise MCPToolError(f"Invalid JSON in config file: {str(e)}")
        except FileNotFoundError:
            raise MCPToolError(f"Config file not found at {MCP_PATH}")
        except Exception as e:
            raise MCPToolError(f"Error reading config file: {str(e)}")

    async def init_server(self, server_name: str, server_config: Dict[str, Any]) -> MCPServer:
        """Initialize a single MCP server."""
        server = MCPServer(server_name, server_config)

        try:
            command_path = self.get_executable_path(server_config["command"])

            # Prepare environment variables
            env = os.environ.copy()
            env["NODE_NO_WARNINGS"] = "1"
            if "env" in server_config:
                env.update(server_config["env"])

            # Prepare server parameters
            server_params = StdioServerParameters(command=command_path, args=server_config.get("args", []), env=env)

            server.client = stdio_client(server_params)
            read, write = await server.client.__aenter__()

            server.session = ClientSession(read, write)
            await server.session.__aenter__()
            await server.session.initialize()

            # Get available tools
            tools_list = await server.session.list_tools()
            server.tools = {tool.name: tool for tool in tools_list.tools if isinstance(tool, Tool)}

            return server

        except Exception as e:
            await server.cleanup()
            raise MCPToolError(f"Failed to initialize server {server_name}: {str(e)}")

    async def initialize_tools(self) -> List[Dict[str, Any]]:
        """Initialize all MCP tools asynchronously."""
        config = self.load_config()

        # Initialize all servers concurrently
        init_tasks = [self.init_server(name, cfg) for name, cfg in config.items()]

        # Wait for all servers to initialize
        results = await asyncio.gather(*init_tasks, return_exceptions=True)

        # Process results and store successful server initializations
        all_tools = []
        for server_name, result in zip(config.keys(), results):
            if isinstance(result, Exception):
                custom_print("error", f"Failed to initialize server {server_name}: {str(result)}")
                continue

            self.servers[server_name] = result
            all_tools.extend(self.tool_to_dict(tool) for tool in result.tools.values())

        custom_print("info", f"Total tools initialized: {len(all_tools)}", start="\n")
        return all_tools

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle individual TCP client connections."""
        try:
            while True:
                # Read the request length first (4 bytes)
                length_bytes = await reader.read(4)
                if not length_bytes:
                    break

                msg_length = int.from_bytes(length_bytes, "big")
                data = await reader.read(msg_length)
                if not data:
                    break

                request = json.loads(data.decode())
                command = request.get("command")
                response = {"status": "error", "message": "Invalid command"}

                if command == "call_tool":
                    try:
                        tool_name = request["tool_name"]
                        arguments = request["arguments"]
                        # Find server with the requested tool
                        server = next((s for s in self.servers.values() if tool_name in s.tools), None)

                        if not server:
                            raise MCPToolError(f"Tool '{tool_name}' not found in any server")

                        result = await server.session.call_tool(tool_name, arguments)
                        response = {"status": "success", "result": str(result)}
                    except Exception as e:
                        response = {"status": "error", "message": str(e)}

                elif command == "get_tools":
                    try:
                        tools = [
                            self.tool_to_dict(tool)
                            for server in self.servers.values()
                            for tool in server.tools.values()
                        ]
                        response = {"status": "success", "tools": tools}
                    except Exception as e:
                        response = {"status": "error", "message": str(e)}

                # Send response
                response_data = json.dumps(response).encode()
                writer.write(len(response_data).to_bytes(4, "big"))
                writer.write(response_data)
                await writer.drain()

        except Exception as e:
            print(f"Error handling client: {e}")
            import traceback

            print(traceback.format_exc())
        finally:
            writer.close()
            await writer.wait_closed()

    async def cleanup(self):
        """Cleanup all MCP sessions and connections."""
        cleanup_tasks = [server.cleanup() for server in self.servers.values()]
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        self.servers.clear()

    async def start(self):
        """Start the TCP server and initialize MCP tools."""
        try:
            # Initialize MCP tools first
            await self.initialize_tools()

            # Start TCP server
            server = await asyncio.start_server(self.handle_client, self.host, self.port)

            async with server:
                print(f"Server running on {self.host}:{self.port}")
                await server.serve_forever()
        except Exception as e:
            print(f"Server error: {e}")
            await self.cleanup()
            raise


if __name__ == "__main__":
    server = MCPTCPServer()

    async def main():
        try:
            await server.start()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            await server.cleanup()

    asyncio.run(main())
