from typing import Any, Dict, List, Optional


class MCPError(Exception):
    def __init__(self, error_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"error_type": self.error_type, "message": self.message, "details": self.details}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPError":
        return cls(error_type=data["error_type"], message=data["message"], details=data.get("details", {}))


class ConfigError(MCPError):
    def __init__(self, message: str, config_path: str):
        super().__init__(error_type="CONFIG_ERROR", message=message, details={"config_path": config_path})


class ServerInitError(MCPError):
    def __init__(self, message: str, server_name: str):
        super().__init__(error_type="SERVER_INIT_ERROR", message=message, details={"server_name": server_name})


class ToolExecutionError(MCPError):
    def __init__(self, message: str, tool_name: str, args: Dict[str, Any]):
        super().__init__(
            error_type="TOOL_EXECUTION_ERROR", message=message, details={"tool_name": tool_name, "arguments": args}
        )


class CommandNotFoundError(MCPError):
    def __init__(self, command: str, available_paths: List[str]):
        super().__init__(
            error_type="COMMAND_NOT_FOUND",
            message=f"Command '{command}' not found. Please ensure it's installed and in your PATH.",
            details={
                "command": command,
                "available_paths": available_paths,
                "help": "The command might need to be installed or added to your system's PATH.",
            },
        )
