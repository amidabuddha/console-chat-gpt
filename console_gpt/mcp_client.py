# More about Model Context Protocol (MCP) and how to create custom MCP servers at https://modelcontextprotocol.io/introduction

import asyncio
import json
import os
import shutil
import subprocess
from functools import wraps
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client

from console_gpt.config_manager import _join_and_check

BASE_PATH = os.path.dirname(os.path.realpath(f"{__file__}/.."))
MCP_PATH = _join_and_check(
    BASE_PATH,
    "mcp_config.json",
    error_message='"mcp_config.json" is either missing or renamed, please check.',
)


class MCPServer:
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.session = None
        self.client = None
        self.tools = {}


# Global state management class
class GlobalState:
    servers: Dict[str, MCPServer] = {}
    loop: Optional[asyncio.AbstractEventLoop] = None


_state = GlobalState()


class MCPToolError(Exception):
    """Custom exception for MCP tool initialization errors"""

    pass


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create an event loop."""
    if _state.loop is None or _state.loop.is_closed():
        _state.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_state.loop)
    return _state.loop


def tool_to_dict(tool: Tool) -> Dict[str, Any]:
    """
    Convert a Tool object to a dictionary with the specified schema.
    """
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": (
            tool.inputSchema if hasattr(tool, "inputSchema") else {"type": "object", "properties": {}, "required": []}
        ),
    }


def list_tools_to_dict(tool: Tool) -> Dict[str, str]:
    """
    Convert a Tool object to a dictionary with the specified schema.
    """
    return {
        "name": tool.name,
        "description": tool.description,
    }


def get_executable_path(command: str) -> str:
    """Get the full path of an executable, considering the OS."""

    def check_common_paths(cmd: str) -> Optional[str]:
        common_paths = []
        common_paths.extend(
                [
                    f"/usr/local/bin/{cmd}",
                    f"/usr/bin/{cmd}",
                    f"/opt/homebrew/bin/{cmd}",  # Common on macOS with Homebrew
                    os.path.expanduser(f"~/.nvm/current/bin/{cmd}"),  # NVM installation
                    os.path.expanduser(f"~/.npm-global/bin/{cmd}"),  # NPM global installation
                    os.path.expanduser(f"~/.local/bin/{cmd}"),  # User local installation
                ]
            )

        for path in common_paths:
            if os.path.isfile(path):
                return path
        return None

    if os.path.sep in command:
        if os.path.isfile(command):
            return command

    path = shutil.which(command)
    if path:
        return path

    path = check_common_paths(command)
    if path:
        return path

    if command in ["node", "npm", "npx", "uv", "uvx"]:
        try:
            # Try to get the path from npm
            npm_cmd = "npm"

            npm_path = shutil.which(npm_cmd)
            if npm_path:
                try:
                    result = subprocess.run([npm_path, "bin", "-g"], capture_output=True, text=True, check=True)
                    global_bin = result.stdout.strip()
                    potential_path = os.path.join(global_bin, command)
                    if os.path.isfile(potential_path):
                        return potential_path
                except subprocess.CalledProcessError:
                    pass
        except Exception:
            pass

    # If we get here, we couldn't find the command
    available_paths = os.environ.get("PATH", "").split(os.pathsep)
    raise MCPToolError(
        f"Command '{command}' not found. Please ensure it's installed and in your PATH.\n"
        f"Current PATH directories:\n{json.dumps(available_paths, indent=2)}"
    )


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


async def _init_server(server_name: str, server_config: Dict[str, Any]) -> MCPServer:
    """Initialize a single MCP server."""
    server = MCPServer(server_name, server_config)

    # Get the full path of the command
    try:
        command_path = get_executable_path(server_config["command"])
    except MCPToolError as e:
        print(f"Error initializing server {server_name}: {str(e)}")
        raise

    # Prepare environment variables
    env = os.environ.copy()  # Start with current environment
    if "env" in server_config:
        env.update(server_config["env"])  # Add config-specific environment variables

    # Prepare server parameters
    server_params = StdioServerParameters(command=command_path, args=server_config.get("args", []), env=env)

    try:
        server.client = stdio_client(server_params)
        read, write = await server.client.__aenter__()

        try:
            server.session = ClientSession(read, write)
            await server.session.__aenter__()
            await server.session.initialize()

            # Get available tools
            tools_list = await server.session.list_tools()

            # Store valid tools
            for tool in tools_list.tools:
                if isinstance(tool, Tool):
                    server.tools[tool.name] = tool

            return server

        except Exception as e:
            if server.session:
                await server.session.__aexit__(type(e), e, e.__traceback__)
            raise

    except Exception as e:
        if server.client:
            await server.client.__aexit__(type(e), e, e.__traceback__)
        raise MCPToolError(f"Failed to initialize server {server_name}: {str(e)}")


async def _init_all_servers(config: Dict[str, Dict[str, Any]]) -> Dict[str, MCPServer]:
    """Initialize all MCP servers in parallel."""
    servers = {}
    init_tasks = []

    for server_name, server_config in config.items():
        task = _init_server(server_name, server_config)
        init_tasks.append((server_name, task))

    # Wait for all servers to initialize
    for server_name, task in init_tasks:
        try:
            servers[server_name] = await task
        except Exception as e:
            print(f"Failed to initialize server {server_name}: {str(e)}")
            continue

    return servers


def initialize_tools() -> List[Dict[str, Any]]:
    """
    Initialize all MCP tools and return them as a list of dictionaries.
    """
    config = load_config()
    loop = get_event_loop()

    try:
        _state.servers = loop.run_until_complete(_init_all_servers(config))

        # Collect all tools from all servers
        all_tools = []
        for server in _state.servers.values():
            all_tools.extend(tool_to_dict(tool) for tool in server.tools.values())

        print(f"\nTotal tools initialized: {len(all_tools)}")
        return all_tools

    except Exception as e:
        # Cleanup on failure
        if _state.servers:
            for server in _state.servers.values():
                if server.session:
                    try:
                        loop.run_until_complete(server.session.__aexit__(None, None, None))
                    except:
                        pass
                if server.client:
                    try:
                        loop.run_until_complete(server.client.__aexit__(None, None, None))
                    except:
                        pass

        _state.servers = {}
        raise MCPToolError(f"Failed to initialize tools: {str(e)}")


def _ensure_initialized(func):
    """Decorator to ensure session is initialized before calling methods."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _state.servers:
            raise MCPToolError("MCP servers not initialized. Call initialize_tools() first.")
        return func(*args, **kwargs)

    return wrapper


@_ensure_initialized
def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Call a tool by name with the provided arguments.
    This is a synchronous wrapper around the async call_tool method.
    """
    # Find the server that has this tool
    server = None
    for s in _state.servers.values():
        if tool_name in s.tools:
            server = s
            break

    if not server:
        raise MCPToolError(f"Tool '{tool_name}' not found in any server")

    async def _call():
        return await server.session.call_tool(tool_name, arguments=arguments)

    loop = get_event_loop()
    return loop.run_until_complete(_call())


@_ensure_initialized
def get_available_tools() -> Dict[str, Dict[str, Any]]:
    """Return all available tools across all servers."""
    all_tools = []
    for server in _state.servers.values():
        all_tools.extend(list_tools_to_dict(tool) for tool in server.tools.values())
    return all_tools


async def cleanup():
    """Cleanup all MCP sessions and connections."""
    if _state.servers:
        for server in _state.servers.values():
            if server.session:
                try:
                    await server.session.__aexit__(None, None, None)
                except:
                    pass
            if server.client:
                try:
                    await server.client.__aexit__(None, None, None)
                except:
                    pass

    _state.servers = {}


def shutdown():
    """Clean up and close the event loop."""
    if _state.loop and not _state.loop.is_closed():
        try:
            _state.loop.run_until_complete(cleanup())
        except:
            pass
        finally:
            _state.loop.close()
            _state.loop = None
