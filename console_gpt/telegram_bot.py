import base64
import threading
import html
import io
import re
import select
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from pypdf import PdfReader
from unichat import MODELS_LIST, UnifiedChatApi
from unichat.api_helper import openai

from console_gpt.config_manager import fetch_variable, fetch_variable_resolved
from console_gpt.custom_stdout import custom_print
from console_gpt.ollama_helper import (is_ollama_running, list_ollama_models,
                                       start_ollama)
from mcp_servers.server_manager import ServerManager

REQUEST_TIMEOUT_SECONDS = 120
ANTHROPIC_WEB_SEARCH_MAX_USES = 5
ANTHROPIC_WEB_FETCH_MAX_USES = 5
ANTHROPIC_WEB_FETCH_MAX_CONTENT_TOKENS = 50000

ANTHROPIC_WEB_SEARCH_TOOL_TYPE = "web_search_20260209"
ANTHROPIC_WEB_FETCH_TOOL_TYPE = "web_fetch_20260209"
OPENAI_WEB_SEARCH_TOOL_TYPE = "web_search"


def _telegram_api(token: str, method: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        response = requests.post(url, json=payload or {}, timeout=40)
        response.raise_for_status()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        hint = ""
        if status in (401, 404):
            hint = " Check chat.telegram.bot_token in config.toml."
        raise RuntimeError(f"Telegram API HTTP {status} on method '{method}'.{hint}") from e
    except requests.RequestException as e:
        # Catch DNS/connectivity/transient request failures and return a clear runtime message.
        error_text = str(e)
        hint = ""
        if "Failed to resolve" in error_text or "Name or service not known" in error_text:
            hint = " Check your network or DNS settings and verify api.telegram.org is reachable."
        raise RuntimeError(f"Telegram API request failed on method '{method}': {error_text}.{hint}") from e

    try:
        data = response.json()
    except ValueError as e:
        raise RuntimeError(f"Telegram API returned a non-JSON response on method '{method}'.") from e
    if not data.get("ok"):
        description = data.get("description", "unknown error")
        error_code = data.get("error_code", "unknown")
        raise RuntimeError(f"Telegram API error {error_code} on method '{method}': {description}")
    return data


def _is_valid_telegram_token(token: str) -> bool:
    # BotFather tokens are in the format: <digits>:<alnum_or_underscore_or_dash>
    return bool(re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token or ""))


def _stop_mcp_server_if_running() -> None:
    """Best-effort MCP cleanup when Telegram runtime stops."""
    _, message = ServerManager().stop_server()
    if message in ("Server stopped successfully", "Server force stopped"):
        custom_print("info", "MCP server stopped.")


def _consume_terminal_control_command() -> Optional[str]:
    """Read local terminal control command for Telegram runtime."""
    if not sys.stdin or not sys.stdin.isatty():
        return None
    try:
        readable, _, _ = select.select([sys.stdin], [], [], 0)
        if not readable:
            return None
        command = sys.stdin.readline().strip().lower()
        if command in ("exit", "quit", "bye"):
            return "stop"
        if command in ("reset", "restart"):
            return "reset"
        return None
    except Exception:
        return None


def _telegram_get_file_bytes(token: str, file_id: str) -> bytes:
    file_meta = _telegram_api(token, "getFile", {"file_id": file_id}).get("result", {})
    file_path = file_meta.get("file_path")
    if not file_path:
        raise RuntimeError("Missing file_path in Telegram getFile response")

    file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    file_response = requests.get(file_url, timeout=60)
    file_response.raise_for_status()
    return file_response.content


def _chunk_text(text: str, chunk_size: int = 3900) -> List[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            split = text.rfind("\n", start, end)
            if split > start:
                end = split + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def _telegram_markdown_to_html(text: str) -> str:
    """Convert a subset of markdown-like model output to Telegram-safe HTML."""
    if not text:
        return ""

    fenced_blocks: List[str] = []

    def _capture_fenced_block(match: re.Match[str]) -> str:
        block = match.group(1) or ""
        escaped = html.escape(block.strip("\n"))
        fenced_blocks.append(f"<pre><code>{escaped}</code></pre>")
        return f"@@TG_CODEBLOCK_{len(fenced_blocks) - 1}@@"

    without_fenced = re.sub(r"```(?:[^\n`]+)?\n([\s\S]*?)```", _capture_fenced_block, text)
    escaped_text = html.escape(without_fenced)

    lines: List[str] = []
    for line in escaped_text.split("\n"):
        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.+)$", line)
        if heading_match:
            lines.append(f"<b>{heading_match.group(1).strip()}</b>")
        else:
            lines.append(line)
    transformed = "\n".join(lines)

    transformed = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        transformed,
    )
    transformed = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", transformed)
    transformed = re.sub(r"__(.+?)__", r"<b>\1</b>", transformed)
    transformed = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", transformed)

    for idx, block in enumerate(fenced_blocks):
        transformed = transformed.replace(f"@@TG_CODEBLOCK_{idx}@@", block)

    return transformed


def _send_message(token: str, chat_id: int, text: str) -> None:
    for part in _chunk_text(text.strip() or "(empty response)"):
        payload = {
            "chat_id": chat_id,
            "text": _telegram_markdown_to_html(part),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            _telegram_api(token, "sendMessage", payload)
        except RuntimeError as e:
            # Fallback to plain text if Telegram rejects entities for a specific chunk.
            error_text = str(e).lower()
            if "parse entities" in error_text or "can't parse entities" in error_text:
                _telegram_api(token, "sendMessage", {"chat_id": chat_id, "text": part})
            else:
                raise


def _is_allowed_chat(chat_id: int, allowed_chat_ids: List[int]) -> bool:
    return not allowed_chat_ids or chat_id in allowed_chat_ids


def _extract_pdf_text(file_bytes: bytes) -> str:
    text_parts: List[str] = []
    reader = PdfReader(io.BytesIO(file_bytes))
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts).strip()


def _extract_document_content(file_name: str, file_bytes: bytes) -> Optional[str]:
    suffix = Path(file_name or "").suffix.lower()
    if suffix == ".txt":
        return file_bytes.decode("utf-8", errors="replace").strip()
    if suffix == ".pdf":
        return _extract_pdf_text(file_bytes)
    return None


def _build_default_session() -> Dict[str, Any]:
    models = fetch_variable("models")
    default_model = fetch_variable("defaults", "model")
    model_key = default_model if default_model in models else next(iter(models.keys()))
    model_data = dict(models[model_key])
    model_data.update({"model_title": model_key})

    role_key = fetch_variable("defaults", "system_role")
    role_data = fetch_variable_resolved("roles")
    system_role = role_data.get(role_key, "Deliver precise and informative virtual assistance.")

    temperature = fetch_variable("defaults", "temperature")
    return {
        "model": model_data,
        "role_key": role_key,
        "temperature": temperature,
        "reasoning_effort_override": None,
        "mode": "message",
        "web_search_enabled": False,
        "anthropic_web_fetch_enabled": False,
        "cached": False,
        "conversation": [{"role": "system", "content": system_role}],
    }


def _build_default_session_for_model(model_key_override: Optional[str] = None) -> Dict[str, Any]:
    models = fetch_variable("models")
    default_model = fetch_variable("defaults", "model")
    selected_model = model_key_override if model_key_override in models else default_model
    model_key = selected_model if selected_model in models else next(iter(models.keys()))
    model_data = dict(models[model_key])
    model_data.update({"model_title": model_key})

    role_key = fetch_variable("defaults", "system_role")
    role_data = fetch_variable_resolved("roles")
    system_role = role_data.get(role_key, "Deliver precise and informative virtual assistance.")

    temperature = fetch_variable("defaults", "temperature")
    return {
        "model": model_data,
        "role_key": role_key,
        "temperature": temperature,
        "reasoning_effort_override": None,
        "mode": "message",
        "web_search_enabled": False,
        "anthropic_web_fetch_enabled": False,
        "cached": False,
        "conversation": [{"role": "system", "content": system_role}],
    }


def _parse_chat_id(raw_chat_id: Any) -> Optional[int]:
    if isinstance(raw_chat_id, int):
        return raw_chat_id
    if isinstance(raw_chat_id, str):
        value = raw_chat_id.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _normalize_chat_id_values(raw_values: Any) -> List[int]:
    if raw_values is None:
        return []

    if isinstance(raw_values, (int, str)):
        parsed = _parse_chat_id(raw_values)
        return [parsed] if parsed is not None else []

    if not isinstance(raw_values, list):
        return []

    parsed_values: List[int] = []
    for item in raw_values:
        parsed = _parse_chat_id(item)
        if parsed is not None:
            parsed_values.append(parsed)
    return parsed_values


def _build_telegram_model_chat_overrides() -> Dict[int, str]:
    """Build map of Telegram chat_id -> locked model key from [chat.models.*] config."""
    configured_models = fetch_variable("models") or {}
    overrides: Dict[int, str] = {}

    for model_key, model_data in configured_models.items():
        if not isinstance(model_data, dict):
            continue

        raw_single_chat_id = model_data.get("telegram_chat_id")
        raw_chat_ids = model_data.get("telegram_chat_ids")
        model_chat_ids = _normalize_chat_id_values(raw_chat_ids)

        single_chat_id = _parse_chat_id(raw_single_chat_id)
        if single_chat_id is not None:
            model_chat_ids.append(single_chat_id)

        if not model_chat_ids:
            continue

        for mapped_chat_id in model_chat_ids:
            if mapped_chat_id in overrides and overrides[mapped_chat_id] != model_key:
                custom_print(
                    "warn",
                    (
                        "Duplicate Telegram model room mapping for chat_id="
                        f"{mapped_chat_id}: keeping '{overrides[mapped_chat_id]}' and ignoring '{model_key}'."
                    ),
                )
                continue
            overrides[mapped_chat_id] = model_key

    return overrides


def _default_system_role_content() -> str:
    role_key = fetch_variable("defaults", "system_role")
    role_data = fetch_variable_resolved("roles")
    return role_data.get(role_key, "Deliver precise and informative virtual assistance.")


def _session_system_role_content(session: Dict[str, Any]) -> str:
    role_data = fetch_variable_resolved("roles")
    role_key = str(session.get("role_key") or fetch_variable("defaults", "system_role"))
    return role_data.get(role_key, _default_system_role_content())


def _set_session_role(session: Dict[str, Any], role_key: str, preserve_history: bool) -> None:
    session["role_key"] = role_key
    system_content = _session_system_role_content(session)

    if preserve_history:
        conversation = session.setdefault("conversation", [])
        if conversation and isinstance(conversation[0], dict) and conversation[0].get("role") == "system":
            conversation[0]["content"] = system_content
        else:
            conversation.insert(0, {"role": "system", "content": system_content})
        # Ensure subsequent requests use the updated role/system context.
        _clear_session_runtime_client(session)
        return

    session["conversation"] = [{"role": "system", "content": system_content}]
    _clear_session_runtime_client(session)


def _clear_session_runtime_client(session: Dict[str, Any]) -> None:
    session.pop("_runtime_client", None)
    session.pop("_runtime_client_key", None)


def _reset_session_conversation(session: Dict[str, Any]) -> None:
    _set_session_role(session, str(session.get("role_key") or fetch_variable("defaults", "system_role")), False)


def _should_enable_prompt_cache(session: Dict[str, Any]) -> bool:
    model_title = str(session.get("model", {}).get("model_title", "")).lower()
    mode = str(session.get("mode", "message")).lower()
    return model_title.startswith("anthropic") and mode != "message"


def _session_cached_prompt_payload(session: Dict[str, Any]) -> Any:
    """
    Return the stable prompt context that should be reused via Anthropic caching.
    """
    conversation = session.get("conversation", []) or []
    if conversation and isinstance(conversation[0], dict) and conversation[0].get("role") == "system":
        return conversation[0].get("content", "")
    return _session_system_role_content(session)


def _sync_session_prompt_cache(session: Dict[str, Any]) -> None:
    session["cached"] = _session_cached_prompt_payload(session) if _should_enable_prompt_cache(session) else False


def _is_web_search_enabled(session: Dict[str, Any]) -> bool:
    return bool(session.get("web_search_enabled", False))


def _set_web_search_enabled(session: Dict[str, Any], enabled: bool) -> None:
    session["web_search_enabled"] = enabled


def _get_or_create_session(
    sessions: Dict[int, Dict[str, Any]],
    chat_id: int,
    model_chat_overrides: Optional[Dict[int, str]] = None,
    debug_context: bool = False,
    init_stage: str = "session_init",
    sessions_lock: Optional[Any] = None,
) -> Dict[str, Any]:
    def _create_if_missing() -> Dict[str, Any]:
        existing = sessions.get(chat_id)
        if existing is not None:
            return existing

        model_override = (model_chat_overrides or {}).get(chat_id)
        session = _build_default_session_for_model(model_override)
        _sync_session_prompt_cache(session)
        if model_override:
            session["model_locked"] = True
            session["model_locked_key"] = model_override
        sessions[chat_id] = session
        if debug_context:
            _debug_session_settings_snapshot(session, chat_id, init_stage)
        return session

    if sessions_lock is None:
        return _create_if_missing()

    with sessions_lock:
        return _create_if_missing()


def _effective_reasoning_effort(session: Dict[str, Any]) -> Any:
    override = session.get("reasoning_effort_override", None)
    if override is not None:
        return override
    return session.get("model", {}).get("reasoning_effort", False)


def _format_reasoning_effort(value: Any) -> str:
    if value is False or value is None:
        return "off"
    if isinstance(value, str) and value.lower() in ("off", "none"):
        return "off"
    return str(value)


def _parse_reasoning_effort_selector(raw_value: str) -> Tuple[bool, Optional[Any], str]:
    value = raw_value.strip().lower()
    if value in ("default", "config", "inherit"):
        return True, None, "default"
    if value in ("off", "false", "0", "none"):
        return True, "off", "off"
    if value in ("minimal", "low", "medium", "high", "xhigh", "max"):
        return True, value, value
    return False, None, ""


def _is_ollama_model(model_data: Dict[str, Any]) -> bool:
    model_title = str(model_data.get("model_title", "")).lower()
    api_key = str(model_data.get("api_key", "")).lower()
    base_url = str(model_data.get("base_url", "")).lower()

    if model_title == "ollama" or model_title.startswith("ollama/"):
        return True
    if api_key == "ollama":
        return True
    return "localhost:11434" in base_url or "127.0.0.1:11434" in base_url


def _unload_ollama_model(model_data: Optional[Dict[str, Any]]) -> None:
    """Best-effort unload of Ollama model weights from RAM while keeping service alive."""
    if not model_data or not _is_ollama_model(model_data):
        return

    model_name = str(model_data.get("model_name", "")).strip()
    if not model_name:
        return

    try:
        result = subprocess.run(["ollama", "stop", model_name], capture_output=True, text=True)
        if result.returncode == 0:
            custom_print("info", f"Unloaded Ollama model from RAM: {model_name}")
    except Exception:
        # Non-fatal cleanup path.
        pass


def _unload_ollama_models_in_sessions(sessions: Dict[int, Dict[str, Any]]) -> None:
    seen_models = set()
    for session in sessions.values():
        model_data = session.get("model", {})
        if not _is_ollama_model(model_data):
            continue
        model_name = str(model_data.get("model_name", "")).strip()
        if not model_name or model_name in seen_models:
            continue
        seen_models.add(model_name)
        _unload_ollama_model(model_data)


def _build_model_catalog() -> Dict[str, Dict[str, Any]]:
    configured_models = fetch_variable("models")
    catalog: Dict[str, Dict[str, Any]] = {}

    for model_key, model_data in configured_models.items():
        catalog[model_key] = dict(model_data)
        catalog[model_key]["model_title"] = model_key

    ollama_models = list_ollama_models()

    for ollama_model in ollama_models:
        model_key = f"ollama/{ollama_model}"
        catalog[model_key] = {
            "api_key": "ollama",
            "base_url": "http://localhost:11434/v1",
            "model_input_pricing_per_1k": 0,
            "model_max_tokens": 0,
            "model_name": ollama_model,
            "model_output_pricing_per_1k": 0,
            "reasoning_effort": False,
            "verbosity": False,
            "model_title": model_key,
        }

    return catalog


def _indexed_model_keys(models: Dict[str, Any]) -> List[str]:
    return sorted(models.keys())


def _render_models_list(models: Dict[str, Any], active_model: str) -> str:
    lines = ["Available models (active marked with *):"]
    indexed_keys = _indexed_model_keys(models)
    for idx, model_key in enumerate(indexed_keys, start=1):
        marker = "*" if model_key == active_model else " "
        lines.append(f"{idx}. [{marker}] {model_key}")
    lines.append("Use: /model set <index> or /model set <name>")
    return "\n".join(lines)


def _build_roles_catalog() -> Dict[str, str]:
    return dict(fetch_variable_resolved("roles"))


def _indexed_role_keys(roles: Dict[str, str]) -> List[str]:
    return sorted(roles.keys())


def _render_roles_list(roles: Dict[str, str], active_role: str) -> str:
    lines = ["Available roles (active marked with *):"]
    indexed_keys = _indexed_role_keys(roles)
    for idx, role_key in enumerate(indexed_keys, start=1):
        marker = "*" if role_key == active_role else " "
        lines.append(f"{idx}. [{marker}] {role_key}")
    lines.append("Use: /role set <index> or /role set <name>")
    return "\n".join(lines)


def _extract_responses_text(response: Any) -> Tuple[str, List[Dict[str, Any]]]:
    assistant_chunks: List[str] = []
    parsed_output: List[Dict[str, Any]] = []

    for output in getattr(response, "output", []) or []:
        output_type = getattr(output, "type", "")
        if output_type == "message":
            text_content = ""
            for content_part in getattr(output, "content", []) or []:
                part_text = getattr(content_part, "text", None)
                if part_text:
                    text_content += part_text
            if text_content:
                assistant_chunks.append(text_content)
                parsed_output.append({"role": "assistant", "content": text_content})

    return "\n\n".join(assistant_chunks).strip(), parsed_output


def _extract_completion_text(response: Any) -> Tuple[str, Dict[str, Any]]:
    message = response.choices[0].message
    content = getattr(message, "content", "")

    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in ("text", "output_text"):
                    chunks.append(item.get("text", ""))
            elif hasattr(item, "text"):
                chunks.append(getattr(item, "text", ""))
        text_content = "".join(chunks).strip()
    else:
        text_content = str(content or "").strip()

    return text_content, {"role": "assistant", "content": text_content}


def _debug_conversation_snapshot(session: Dict[str, Any], chat_id: int, stage: str) -> None:
    conversation = session.get("conversation", []) or []
    roles_tail: List[str] = []
    for item in conversation[-8:]:
        if isinstance(item, dict):
            roles_tail.append(str(item.get("role", "?")))
        else:
            roles_tail.append(type(item).__name__)
    mode = str(session.get("mode", "chat")).lower()
    custom_print(
        "info",
        f"[TG DEBUG] stage={stage} chat_id={chat_id} mode={mode} conv_len={len(conversation)} roles_tail={roles_tail}",
    )


def _debug_session_settings_snapshot(session: Dict[str, Any], chat_id: int, stage: str) -> None:
    model = session.get("model", {}) or {}
    mode = str(session.get("mode", "message")).lower()
    role_key = str(session.get("role_key") or fetch_variable("defaults", "system_role"))
    reasoning_override = session.get("reasoning_effort_override", None)
    reasoning_effective = _effective_reasoning_effort(session)
    cache_enabled = _should_enable_prompt_cache(session)
    cached_payload = session.get("cached", False)
    cached_payload_type = type(cached_payload).__name__ if cached_payload is not False else "bool"
    web_search_enabled = _is_web_search_enabled(session)
    web_fetch_enabled = bool(session.get("anthropic_web_fetch_enabled", False))
    custom_print(
        "info",
        (
            f"[TG DEBUG] stage={stage} chat_id={chat_id} "
            f"model={model.get('model_title', 'unknown')} mode={mode} role={role_key} "
            f"reasoning_effective={_format_reasoning_effort(reasoning_effective)} "
            f"reasoning_override={_format_reasoning_effort(reasoning_override)} "
            f"cache_enabled={cache_enabled} cached_payload_type={cached_payload_type} "
            f"web_search={web_search_enabled} web_fetch={web_fetch_enabled}"
        ),
    )


def _debug_startup_default_settings_snapshot() -> None:
    session = _build_default_session()
    _sync_session_prompt_cache(session)
    model = session.get("model", {}) or {}
    mode = str(session.get("mode", "message")).lower()
    role_key = str(session.get("role_key") or fetch_variable("defaults", "system_role"))
    reasoning_override = session.get("reasoning_effort_override", None)
    reasoning_effective = _effective_reasoning_effort(session)
    cache_enabled = _should_enable_prompt_cache(session)
    cached_payload = session.get("cached", False)
    cached_payload_type = type(cached_payload).__name__ if cached_payload is not False else "bool"
    web_search_enabled = _is_web_search_enabled(session)
    web_fetch_enabled = bool(session.get("anthropic_web_fetch_enabled", False))
    custom_print(
        "info",
        (
            "[TG DEBUG] stage=startup_defaults "
            f"model={model.get('model_title', 'unknown')} mode={mode} role={role_key} "
            f"reasoning_effective={_format_reasoning_effort(reasoning_effective)} "
            f"reasoning_override={_format_reasoning_effort(reasoning_override)} "
            f"cache_enabled={cache_enabled} cached_payload_type={cached_payload_type} "
            f"web_search={web_search_enabled} web_fetch={web_fetch_enabled}"
        ),
    )


def _uses_responses_api(model_name: Optional[str]) -> bool:
    return model_name in MODELS_LIST["openai_models"] or model_name in MODELS_LIST["xai_models"]


def _is_anthropic_server_tool(tool: Dict[str, Any]) -> bool:
    tool_type = tool.get("type")
    if not isinstance(tool_type, str):
        return False
    return (
        tool_type.startswith("web_search_")
        or tool_type.startswith("web_fetch_")
        or tool_type.startswith("code_execution_")
    )


def _patch_unichat_tool_normalizer_for_server_tools(client: Any) -> None:
    api_helper = getattr(client, "_api_helper", None)
    if api_helper is None or getattr(api_helper, "_server_tools_passthrough_patch", False):
        return

    original_normalize_tools = api_helper.normalize_tools

    def _patched_normalize_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(tools, list):
            return original_normalize_tools(tools)

        if not any(isinstance(tool, dict) and _is_anthropic_server_tool(tool) for tool in tools):
            return original_normalize_tools(tools)

        normalized_tools: List[Dict[str, Any]] = []
        for tool in tools:
            if isinstance(tool, dict) and _is_anthropic_server_tool(tool):
                normalized_tools.append(dict(tool))
            else:
                normalized_tools.extend(original_normalize_tools([tool]))
        return normalized_tools

    api_helper.normalize_tools = _patched_normalize_tools
    setattr(api_helper, "_server_tools_passthrough_patch", True)


def _execute_model_action(with_timeout_action, fallback_action):
    """Execute model request with timeout support and compatibility fallback."""
    try:
        return with_timeout_action()
    except TypeError:
        # Some API client wrappers may not support request-level timeout kwargs.
        return fallback_action()
    except KeyboardInterrupt:
        return "interrupted"
    except Exception as e:
        error_text = str(e).lower()
        if "timed out" in error_text or "timeout" in error_text:
            custom_print("warn", f"Model request timed out after {REQUEST_TIMEOUT_SECONDS}s.")
            return "request_timeout"
        custom_print("error", f"Model request failed: {e}")
        return "error_appeared"


def _build_user_facing_model_error_message(error_text: str) -> str:
    text = (error_text or "").lower()

    quota_or_billing_markers = (
        "insufficient_quota",
        "exceeded your current quota",
        "credit balance is too low",
        "billing",
        "quota",
    )
    if any(marker in text for marker in quota_or_billing_markers):
        return (
            "The model request failed due to provider quota or billing limits. "
            "Please check your provider account and try again."
        )

    if "429" in text or "rate limit" in text or "too many requests" in text:
        return "The model request hit a rate limit. Please wait a moment and try again."

    if "401" in text or "unauthorized" in text or "invalid api key" in text:
        return "The model request failed due to authentication. Please verify the configured API key."

    if "400" in text or "invalid_request_error" in text or "bad request" in text:
        return "The model request was rejected as invalid for this provider/model configuration."

    if "timed out" in text or "timeout" in text:
        return f"Model request timed out after {REQUEST_TIMEOUT_SECONDS}s. Try a smaller prompt or another model."

    return "The model request failed. Please try again."


def _request_model_reply(session: Dict[str, Any], debug_context: bool = False, chat_id: int = 0) -> str:
    _sync_session_prompt_cache(session)

    model_data = session["model"]
    model_name = model_data.get("model_name")
    model_title = str(model_data.get("model_title", "")).lower()
    api_key = model_data.get("api_key")
    base_url = model_data.get("base_url")
    reasoning_effort = _effective_reasoning_effort(session)
    verbosity = model_data.get("verbosity")
    temperature = session["temperature"]
    conversation = session["conversation"]
    cache_enabled = _should_enable_prompt_cache(session)
    cached = session.get("cached", False)

    client_params = {"api_key": api_key}
    if base_url:
        client_params["base_url"] = base_url

    ollama_model = _is_ollama_model(model_data)
    if ollama_model and not is_ollama_running():
        custom_print("info", "Ollama is not running. Starting it now...")
        start_ollama()
        if not is_ollama_running():
            return "Ollama is unavailable. Start Ollama and try again."

    use_responses = _uses_responses_api(model_name) and not ollama_model
    if use_responses:
        client_key = ("responses", api_key or "", base_url or "", model_name or "")
        if session.get("_runtime_client_key") != client_key or session.get("_runtime_client") is None:
            session["_runtime_client"] = openai.OpenAI(**client_params)
            session["_runtime_client_key"] = client_key
        client = session["_runtime_client"]
        params = {
            "model": model_name,
            "input": conversation[1:] if conversation[0]["role"] == "system" else conversation,
            "stream": False,
        }
        if conversation[0]["role"] == "system":
            params["instructions"] = "Formatting re-enabled\n" + conversation[0]["content"]
        if _is_web_search_enabled(session):
            params["tools"] = [{"type": OPENAI_WEB_SEARCH_TOOL_TYPE}]

        model_lower = str(model_name or "").lower()
        responses_reasoning_effort: Optional[str] = None
        normalized_effort = str(reasoning_effort).strip().lower() if reasoning_effort not in (None, False) else ""
        if model_lower.startswith(("gpt-5.4", "gpt-5.5")):
            if normalized_effort in ("", "off", "none"):
                responses_reasoning_effort = "none"
            elif normalized_effort == "max":
                responses_reasoning_effort = "xhigh"
            elif normalized_effort in ("minimal", "low", "medium", "high", "xhigh"):
                responses_reasoning_effort = normalized_effort

        if responses_reasoning_effort is not None:
            params.setdefault("reasoning", {})["effort"] = responses_reasoning_effort
            params["reasoning"]["summary"] = "detailed"

        # For GPT-5.4/GPT-5.5, temperature is valid only when reasoning effort is none.
        if (not model_lower.startswith(("gpt-5.4", "gpt-5.5"))) or responses_reasoning_effort == "none":
            params["temperature"] = temperature
        if isinstance(verbosity, str) and verbosity.lower() in ("low", "medium", "high"):
            params.setdefault("text", {})["verbosity"] = verbosity.lower()

        if debug_context:
            input_len = len(params.get("input", []) or [])
            custom_print(
                "info",
                f"[TG DEBUG] stage=request_dispatch chat_id={chat_id} api=responses model={model_name} input_len={input_len}",
            )

        response = _execute_model_action(
            lambda: client.responses.create(**params, timeout=REQUEST_TIMEOUT_SECONDS),
            lambda: client.responses.create(**params),
        )
        if response == "request_timeout":
            return f"Model request timed out after {REQUEST_TIMEOUT_SECONDS}s. Try a smaller prompt or another model."
        if response in ("interrupted", "error_appeared"):
            return "The model request failed. Please try again."

        assistant_text, parsed = _extract_responses_text(response)
        if parsed:
            conversation.extend(parsed)
        return assistant_text or "(No text content returned by model.)"

    client_type = "openai_chat" if ollama_model else "unified_chat"
    client_key = (client_type, api_key or "", base_url or "", model_name or "")
    if session.get("_runtime_client_key") != client_key or session.get("_runtime_client") is None:
        session["_runtime_client"] = openai.OpenAI(**client_params) if ollama_model else UnifiedChatApi(**client_params)
        session["_runtime_client_key"] = client_key
    client = session["_runtime_client"]
    if model_title.startswith("anthropic") and not ollama_model:
        _patch_unichat_tool_normalizer_for_server_tools(client)

    params = {
        "model": model_name,
        "messages": conversation,
        "temperature": temperature,
        "stream": False,
    }
    if model_title.startswith("anthropic"):
        anthropic_tools: List[Dict[str, Any]] = []
        web_search_enabled = _is_web_search_enabled(session)
        web_fetch_enabled = bool(session.get("anthropic_web_fetch_enabled", False))

        if web_search_enabled:
            anthropic_tools.append(
                {
                    "type": ANTHROPIC_WEB_SEARCH_TOOL_TYPE,
                    "name": "web_search",
                    "max_uses": ANTHROPIC_WEB_SEARCH_MAX_USES,
                }
            )

        if web_fetch_enabled:
            anthropic_tools.append(
                {
                    "type": ANTHROPIC_WEB_FETCH_TOOL_TYPE,
                    "name": "web_fetch",
                    "max_uses": ANTHROPIC_WEB_FETCH_MAX_USES,
                    "max_content_tokens": ANTHROPIC_WEB_FETCH_MAX_CONTENT_TOKENS,
                    "citations": {"enabled": True},
                }
            )

        if anthropic_tools:
            params["tools"] = anthropic_tools
    if model_title.startswith("anthropic") and cache_enabled and cached is not False and cached not in (None, ""):
        params["cached"] = cached

    anthropic_reasoning_effort: Optional[str] = None
    if reasoning_effort not in (None, False):
        normalized_effort = str(reasoning_effort).strip().lower()
        if normalized_effort in ("off", "none"):
            anthropic_reasoning_effort = "none"
        elif normalized_effort == "xhigh" and model_title != "anthropic-opus-latest":
            anthropic_reasoning_effort = "max"
        elif normalized_effort == "minimal":
            anthropic_reasoning_effort = "low"
        elif normalized_effort in ("low", "medium", "high", "xhigh", "max"):
            anthropic_reasoning_effort = normalized_effort
    if anthropic_reasoning_effort:
        params["reasoning_effort"] = anthropic_reasoning_effort

    if debug_context:
        custom_print(
            "info",
            (
                f"[TG DEBUG] stage=request_dispatch chat_id={chat_id} api=chat_completions "
                f"model={model_name} cache_enabled={cache_enabled} "
                f"cached_payload_type={type(cached).__name__ if cached is not False else 'bool'} "
                f"messages_len={len(conversation)}"
            ),
        )

    response = _execute_model_action(
        lambda: client.chat.completions.create(**params, timeout=REQUEST_TIMEOUT_SECONDS),
        lambda: client.chat.completions.create(**params),
    )
    if response == "request_timeout":
        return f"Model request timed out after {REQUEST_TIMEOUT_SECONDS}s. Try a smaller prompt or another model."
    if response in ("interrupted", "error_appeared"):
        return "The model request failed. Please try again."

    assistant_text, assistant_msg = _extract_completion_text(response)
    conversation.append(assistant_msg)
    return assistant_text or "(No text content returned by model.)"


def _build_user_content_from_message(
    token: str, message: Dict[str, Any], model_title: str, use_responses: bool
) -> Optional[Any]:
    text = (message.get("text") or "").strip()
    caption = (message.get("caption") or "").strip()

    if message.get("photo"):
        largest_photo = message["photo"][-1]
        image_bytes = _telegram_get_file_bytes(token, largest_photo["file_id"])
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        if model_title.startswith("anthropic"):
            content: List[Dict[str, Any]] = [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded_image},
                }
            ]
            if caption:
                content.append({"type": "text", "text": caption})
            return content

        content = []
        if use_responses:
            if caption:
                content.append({"type": "input_text", "text": caption})
            content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{encoded_image}"})
        else:
            if caption:
                content.append({"type": "text", "text": caption})
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}})
        return content

    if message.get("document"):
        doc = message["document"]
        file_name = doc.get("file_name") or ""
        file_bytes = _telegram_get_file_bytes(token, doc["file_id"])
        extracted = _extract_document_content(file_name, file_bytes)
        if extracted is None:
            return (
                f"Unsupported document type: {file_name}. Please send .txt or .pdf files only."
                if file_name
                else "Unsupported document type. Please send .txt or .pdf files only."
            )

        prefix = "This is the content of a file:\n"
        if caption:
            return f"{caption}:\n{prefix}{extracted}"
        return f"{prefix}{extracted}"

    if text:
        return text

    if caption:
        return caption

    return None


def _handle_command(
    text: str,
    chat_id: int,
    token: str,
    sessions: Dict[int, Dict[str, Any]],
    admin_chat_ids: List[int],
    model_chat_overrides: Optional[Dict[int, str]] = None,
    debug_context: bool = False,
    sessions_lock: Optional[Any] = None,
) -> Tuple[bool, bool]:
    command = text.split()[0].lower()
    model_locked_key = (model_chat_overrides or {}).get(chat_id)
    is_model_locked_chat = model_locked_key is not None

    if command == "/start":
        command_list = (
            "/help, /new, /mode, /role, /reasoning, /websearch, /webfetch, /shutdown"
            if is_model_locked_chat
            else "/help, /new, /mode, /model, /role, /reasoning, /websearch, /webfetch, /shutdown"
        )
        lock_note = f"\nThis room is pinned to model: {model_locked_key}." if is_model_locked_chat else ""
        _send_message(
            token,
            chat_id,
            "Telegram mode is active. Send text, images, or .txt/.pdf files to chat with your configured model.\n"
            f"Commands: {command_list}{lock_note}",
        )
        return True, False

    if command == "/help":
        model_lines = (
            ""
            if is_model_locked_chat
            else (
                "/model - list available models (config + Ollama, if available)\n"
                "/model set <name|index> - switch active model for this chat\n"
            )
        )
        alias_line = (
            "Aliases: /roles -> /role" if is_model_locked_chat else "Aliases: /models -> /model, /roles -> /role"
        )
        lock_note = (
            f"\n\nThis room is pinned to model: {model_locked_key}. Model switching is disabled."
            if is_model_locked_chat
            else ""
        )
        _send_message(
            token,
            chat_id,
            "Commands:\n"
            "/new - reset current conversation\n"
            "/mode - show current mode (chat or message)\n"
            "/mode chat - keep multi-turn context\n"
            "/mode message - one question/one answer per message\n"
            f"{model_lines}"
            "/role - list available roles\n"
            "/role set <name|index> - switch active role for this chat (keeps conversation)\n"
            "/reasoning - show effective reasoning effort for this chat\n"
            "/reasoning <default|off|minimal|low|medium|high|xhigh|max> - set session reasoning effort override\n"
            "/websearch - show web search status (Anthropic + OpenAI Responses)\n"
            "/websearch [on|off] - toggle web search tool (Anthropic + OpenAI Responses)\n"
            "/webfetch - show Anthropic web fetch status\n"
            "/webfetch [on|off] - toggle Anthropic web fetch tool\n"
            "/shutdown - stop bot runtime (admin chat IDs only)\n"
            "/help - show this message\n\n"
            f"{alias_line}\n\n"
            "You can also send:\n"
            "- plain text\n"
            "- photos (with optional caption)\n"
            f"- .txt or .pdf documents (with optional caption){lock_note}",
        )
        return True, False

    if command in ("/websearch", "/webfetch"):
        session = _get_or_create_session(
            sessions,
            chat_id,
            model_chat_overrides=model_chat_overrides,
            debug_context=debug_context,
            init_stage="session_init",
            sessions_lock=sessions_lock,
        )
        is_search_command = command == "/websearch"
        setting_key = "web_search_enabled" if is_search_command else "anthropic_web_fetch_enabled"
        tool_label = "web search" if is_search_command else "web fetch"
        parts = text.split(maxsplit=1)

        if len(parts) == 1 or not parts[1].strip():
            current = _is_web_search_enabled(session) if is_search_command else bool(session.get(setting_key, False))
            _send_message(
                token,
                chat_id,
                f"{tool_label.title()} is {'ON' if current else 'OFF'} for this chat. Use /{command[1:]} [on|off] to change it.",
            )
            return True, False

        value = parts[1].strip().lower()
        if value not in ("on", "off"):
            _send_message(token, chat_id, f"Usage: /{command[1:]} [on|off]")
            return True, False

        enabled = value == "on"
        if is_search_command:
            _set_web_search_enabled(session, enabled)
        else:
            session[setting_key] = enabled
        if debug_context:
            _debug_session_settings_snapshot(session, chat_id, f"{command}_set")
        _send_message(token, chat_id, f"{tool_label.title()} is now {'ON' if enabled else 'OFF'} for this chat.")
        return True, False

    if command == "/mode":
        session = _get_or_create_session(
            sessions,
            chat_id,
            model_chat_overrides=model_chat_overrides,
            debug_context=debug_context,
            init_stage="session_init",
            sessions_lock=sessions_lock,
        )
        parts = text.split(maxsplit=1)
        current_mode = str(session.get("mode", "message")).lower()

        if len(parts) == 1 or not parts[1].strip():
            _send_message(
                token,
                chat_id,
                "Current mode: "
                f"{current_mode}\n"
                "Use /mode message for one-question/one-answer behavior or /mode chat for multi-turn context.",
            )
            return True, False

        target_mode = parts[1].strip().lower()
        if target_mode not in ("chat", "message"):
            _send_message(token, chat_id, "Usage: /mode [chat|message]")
            return True, False

        if target_mode == current_mode:
            _send_message(token, chat_id, f"Mode is already '{current_mode}'.")
            return True, False

        session["mode"] = target_mode
        _sync_session_prompt_cache(session)
        if target_mode == "message":
            _reset_session_conversation(session)
            if debug_context:
                _debug_session_settings_snapshot(session, chat_id, "mode_set_message")
            _send_message(
                token,
                chat_id,
                "Switched to message mode. Each new message starts a fresh one-turn exchange.",
            )
            return True, False

        conversation_len = len(session.get("conversation", []))
        if debug_context:
            _debug_session_settings_snapshot(session, chat_id, "mode_set_chat")
        if conversation_len > 1:
            _send_message(
                token,
                chat_id,
                "Switched to chat mode. You can continue from the latest exchange.",
            )
        else:
            _send_message(
                token,
                chat_id,
                "Switched to chat mode. Start sending messages for multi-turn context.",
            )
        return True, False

    if command == "/reasoning":
        session = _get_or_create_session(
            sessions,
            chat_id,
            model_chat_overrides=model_chat_overrides,
            debug_context=debug_context,
            init_stage="session_init",
            sessions_lock=sessions_lock,
        )
        parts = text.split(maxsplit=1)

        if len(parts) == 1 or not parts[1].strip():
            effective = _effective_reasoning_effort(session)
            override = session.get("reasoning_effort_override", None)
            source = "session override" if override is not None else "model config"
            _send_message(
                token,
                chat_id,
                "Reasoning effort: "
                f"{_format_reasoning_effort(effective)} ({source}).\n"
                "Use /reasoning <default|off|minimal|low|medium|high|xhigh|max> to change it.",
            )
            return True, False

        is_valid, parsed_value, parsed_label = _parse_reasoning_effort_selector(parts[1])
        if not is_valid:
            _send_message(token, chat_id, "Usage: /reasoning <default|off|minimal|low|medium|high|xhigh|max>")
            return True, False

        session["reasoning_effort_override"] = parsed_value
        if parsed_value is None:
            effective = _effective_reasoning_effort(session)
            if debug_context:
                _debug_session_settings_snapshot(session, chat_id, "reasoning_reset")
            _send_message(
                token,
                chat_id,
                f"Reasoning effort override cleared. Using model config: {_format_reasoning_effort(effective)}.",
            )
            return True, False

        if debug_context:
            _debug_session_settings_snapshot(session, chat_id, "reasoning_set")
        _send_message(token, chat_id, f"Reasoning effort override set to {parsed_label} for this chat.")
        return True, False

    if command == "/new":
        session = _get_or_create_session(
            sessions,
            chat_id,
            model_chat_overrides=model_chat_overrides,
            debug_context=debug_context,
            init_stage="session_init",
            sessions_lock=sessions_lock,
        )
        session["role_key"] = fetch_variable("defaults", "system_role")
        _reset_session_conversation(session)
        if debug_context:
            _debug_session_settings_snapshot(session, chat_id, "new")
        model_title = session["model"].get("model_title", "unknown")
        _send_message(token, chat_id, f"Started a new conversation with model: {model_title}")
        return True, False

    if command == "/models":
        if is_model_locked_chat:
            _send_message(
                token,
                chat_id,
                f"This room is pinned to model '{model_locked_key}'. Model switching is disabled for this chat.",
            )
            return True, False
        models = _build_model_catalog()
        session = _get_or_create_session(
            sessions,
            chat_id,
            model_chat_overrides=model_chat_overrides,
            debug_context=debug_context,
            init_stage="session_init",
            sessions_lock=sessions_lock,
        )
        active_model = session["model"].get("model_title", "")
        _send_message(token, chat_id, _render_models_list(models, active_model))
        _send_message(token, chat_id, "Tip: use /model to list and /model set <name|index> to switch.")
        return True, False

    if command == "/roles":
        roles = _build_roles_catalog()
        session = _get_or_create_session(
            sessions,
            chat_id,
            model_chat_overrides=model_chat_overrides,
            debug_context=debug_context,
            init_stage="session_init",
            sessions_lock=sessions_lock,
        )
        active_role = str(session.get("role_key") or fetch_variable("defaults", "system_role"))
        _send_message(token, chat_id, _render_roles_list(roles, active_role))
        _send_message(token, chat_id, "Tip: use /role to list and /role set <name|index> to switch.")
        return True, False

    if command == "/model":
        if is_model_locked_chat:
            _send_message(
                token,
                chat_id,
                f"This room is pinned to model '{model_locked_key}'. Model switching is disabled for this chat.",
            )
            return True, False

        session = _get_or_create_session(
            sessions,
            chat_id,
            model_chat_overrides=model_chat_overrides,
            debug_context=debug_context,
            init_stage="session_init",
            sessions_lock=sessions_lock,
        )
        parts = text.split(maxsplit=2)

        if len(parts) == 1 or not parts[1].strip():
            models = _build_model_catalog()
            active_model = session["model"].get("model_title", "")
            _send_message(token, chat_id, _render_models_list(models, active_model))
            return True, False

        if len(parts) >= 2 and parts[1].lower() == "set":
            if len(parts) < 3 or not parts[2].strip():
                _send_message(token, chat_id, "Usage: /model set <name|index>")
                return True, False

            model_selector = parts[2].strip()
            models = _build_model_catalog()
            indexed_keys = _indexed_model_keys(models)

            target_model_key = model_selector
            if model_selector.isdigit():
                model_index = int(model_selector)
                if model_index < 1 or model_index > len(indexed_keys):
                    _send_message(
                        token, chat_id, f"Invalid model index '{model_index}'. Use /model to list valid indexes."
                    )
                    return True, False
                target_model_key = indexed_keys[model_index - 1]

            if target_model_key not in models:
                _send_message(token, chat_id, f"Unknown model '{model_selector}'. Use /model to list available models.")
                return True, False

            previous_model = dict(session.get("model", {}))
            session["model"] = dict(models[target_model_key])
            _sync_session_prompt_cache(session)
            if _is_ollama_model(previous_model) and previous_model.get("model_name") != session["model"].get(
                "model_name"
            ):
                _unload_ollama_model(previous_model)

            _reset_session_conversation(session)
            if debug_context:
                _debug_session_settings_snapshot(session, chat_id, "model_set")
            model_name = session["model"].get("model_name", "unknown")
            _send_message(token, chat_id, f"Switched model to {target_model_key} ({model_name}). Conversation reset.")
            return True, False

        _send_message(
            token,
            chat_id,
            "Usage: /model or /model set <name|index>",
        )
        return True, False

    if command == "/role":
        session = _get_or_create_session(
            sessions,
            chat_id,
            model_chat_overrides=model_chat_overrides,
            debug_context=debug_context,
            init_stage="session_init",
        )
        parts = text.split(maxsplit=2)

        if len(parts) == 1 or not parts[1].strip():
            roles = _build_roles_catalog()
            active_role = str(session.get("role_key") or fetch_variable("defaults", "system_role"))
            _send_message(token, chat_id, _render_roles_list(roles, active_role))
            return True, False

        if len(parts) >= 2 and parts[1].lower() == "set":
            if len(parts) < 3 or not parts[2].strip():
                _send_message(token, chat_id, "Usage: /role set <name|index>")
                return True, False

            role_selector = parts[2].strip()
            roles = _build_roles_catalog()
            indexed_keys = _indexed_role_keys(roles)

            target_role_key = role_selector
            if role_selector.isdigit():
                role_index = int(role_selector)
                if role_index < 1 or role_index > len(indexed_keys):
                    _send_message(
                        token, chat_id, f"Invalid role index '{role_index}'. Use /role to list valid indexes."
                    )
                    return True, False
                target_role_key = indexed_keys[role_index - 1]

            if target_role_key not in roles:
                _send_message(token, chat_id, f"Unknown role '{role_selector}'. Use /role to list available roles.")
                return True, False

            current_role_key = str(session.get("role_key") or fetch_variable("defaults", "system_role"))
            if target_role_key == current_role_key:
                _send_message(token, chat_id, f"Role is already '{current_role_key}'.")
                return True, False

            _set_session_role(session, target_role_key, preserve_history=True)
            if debug_context:
                _debug_session_settings_snapshot(session, chat_id, "role_set")
            _send_message(token, chat_id, f"Switched role to {target_role_key}. Conversation kept.")
            return True, False

        _send_message(
            token,
            chat_id,
            "Usage: /role or /role set <name|index>",
        )
        return True, False

    if command == "/shutdown":
        if not admin_chat_ids:
            _send_message(
                token,
                chat_id,
                "Remote shutdown is disabled. Configure chat.telegram.admin_chat_ids to enable it.",
            )
            return True, False
        if chat_id not in admin_chat_ids:
            _send_message(token, chat_id, "Unauthorized for /shutdown.")
            return True, False

        _send_message(token, chat_id, "Shutdown command accepted. Stopping Telegram bot...")
        return True, True

    return False, False


def run_telegram_bot() -> None:
    enabled = bool(fetch_variable("telegram", "enabled", auto_exit=False))
    if not enabled:
        return

    token = fetch_variable("telegram", "bot_token")
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        custom_print("error", "Telegram mode is enabled but chat.telegram.bot_token is not configured.", 1)
    if not _is_valid_telegram_token(token):
        custom_print(
            "error",
            "Invalid Telegram bot token format. Expected '<digits>:<token>' from BotFather.",
            1,
        )

    allowed_chat_ids_raw = fetch_variable("telegram", "allowed_chat_ids", auto_exit=False) or []
    allowed_chat_ids = [int(chat_id) for chat_id in allowed_chat_ids_raw]
    admin_chat_ids_raw = fetch_variable("telegram", "admin_chat_ids", auto_exit=False) or []
    admin_chat_ids = [int(chat_id) for chat_id in admin_chat_ids_raw]
    telegram_debug_context = bool(fetch_variable("telegram", "debug_context", auto_exit=False))
    model_chat_overrides = _build_telegram_model_chat_overrides()

    if allowed_chat_ids:
        # Any model-mapped rooms should be accepted without forcing duplicate config entries.
        allowed_chat_ids = sorted(set(allowed_chat_ids + list(model_chat_overrides.keys())))

    custom_print("warn", "Telegram mode detected. Streaming is disabled in Telegram runtime.")
    if fetch_variable("features", "mcp_client", auto_exit=False):
        custom_print("warn", "Telegram mode detected. MCP is disabled in Telegram runtime.")
        _stop_mcp_server_if_running()
    custom_print("info", "Terminal controls: exit/quit/bye = stop bot, reset/restart = clear in-memory sessions.")
    if model_chat_overrides:
        custom_print(
            "info",
            f"Telegram model room mappings active for {len(model_chat_overrides)} chat room(s).",
        )
    custom_print("info", "Starting Telegram bot polling loop...")
    if telegram_debug_context:
        _debug_startup_default_settings_snapshot()

    max_workers_raw = fetch_variable("telegram", "max_concurrent_updates", auto_exit=False)
    if max_workers_raw in (None, "") or isinstance(max_workers_raw, bool):
        max_workers = 8
    else:
        try:
            max_workers = int(max_workers_raw)
        except (TypeError, ValueError):
            max_workers = 8
    if max_workers < 1:
        max_workers = 8
    custom_print("info", f"Telegram concurrent update workers: {max_workers}")

    # Validate token early and fail fast with a clear message.
    try:
        bot_info = _telegram_api(token, "getMe").get("result", {})
    except RuntimeError as e:
        custom_print("error", f"Unable to start Telegram bot: {e}")
        custom_print("error", "Telegram bot startup aborted. The process can be retried once connectivity is restored.")
        return
    bot_username = bot_info.get("username", "unknown")
    custom_print("ok", f"Telegram bot connected: @{bot_username}")

    sessions: Dict[int, Dict[str, Any]] = {}
    sessions_lock = threading.Lock()
    shutdown_requested = threading.Event()
    worker_executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tg-update")
    ordered_futures: Dict[int, Future] = {}
    ordered_futures_lock = threading.Lock()
    offset = 0
    process_start_ts = int(time.time())

    def _process_update(update: Dict[str, Any]) -> None:
        chat_id = 0
        try:
            if shutdown_requested.is_set():
                return

            message = update.get("message") or update.get("edited_message")
            if not message:
                return

            chat = message.get("chat") or {}
            chat_id = int(chat.get("id", 0))
            if not chat_id or not _is_allowed_chat(chat_id, allowed_chat_ids):
                return

            text = (message.get("text") or "").strip()
            if text.startswith("/"):
                command = text.split()[0].lower()
                if command == "/shutdown":
                    message_ts = int(message.get("date") or 0)
                    # Ignore stale shutdown commands that were sent before this bot process started.
                    if message_ts and message_ts < process_start_ts:
                        custom_print("info", f"Ignored stale /shutdown from chat_id={chat_id}.")
                        return

                handled, should_shutdown = _handle_command(
                    text,
                    chat_id,
                    token,
                    sessions,
                    admin_chat_ids,
                    model_chat_overrides=model_chat_overrides,
                    debug_context=telegram_debug_context,
                    sessions_lock=sessions_lock,
                )
                if should_shutdown:
                    custom_print("info", f"Remote shutdown requested by chat_id={chat_id}.")
                    shutdown_requested.set()
                    return
                if handled:
                    return

            session = _get_or_create_session(
                sessions,
                chat_id,
                model_chat_overrides=model_chat_overrides,
                debug_context=telegram_debug_context,
                init_stage="chat_init",
                sessions_lock=sessions_lock,
            )
            model_title = session["model"].get("model_title", "")
            model_name = session["model"].get("model_name")
            user_content = _build_user_content_from_message(
                token, message, model_title, _uses_responses_api(model_name)
            )
            if not user_content:
                _send_message(
                    token,
                    chat_id,
                    "Unsupported input. Send text, an image, or a .txt/.pdf document.",
                )
                return

            # In message mode, each incoming message starts from a fresh conversation context.
            if str(session.get("mode", "message")).lower() == "message":
                _reset_session_conversation(session)

            session["conversation"].append({"role": "user", "content": user_content})
            if telegram_debug_context:
                _debug_conversation_snapshot(session, chat_id, "after_user_append")
            _telegram_api(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
            reply = _request_model_reply(session, debug_context=telegram_debug_context, chat_id=chat_id)
            _send_message(token, chat_id, reply)
        except Exception as e:
            custom_print("warn", f"Telegram update handling warning: {e}. Continuing...")
            if chat_id:
                try:
                    _send_message(token, chat_id, _build_user_facing_model_error_message(str(e)))
                except Exception as reply_error:
                    custom_print(
                        "warn",
                        f"Telegram fallback error-message warning: {reply_error}. Continuing...",
                    )

    def _submit_update(chat_id: int, update: Dict[str, Any]) -> None:
        with ordered_futures_lock:
            prev_future = ordered_futures.get(chat_id)

            def _run_after_previous(prev: Optional[Future], pending_update: Dict[str, Any]) -> None:
                if prev is not None:
                    try:
                        prev.result()
                    except Exception:
                        # Continue processing later updates in the same chat even if a previous one failed.
                        pass
                _process_update(pending_update)

            next_future = worker_executor.submit(_run_after_previous, prev_future, update)
            ordered_futures[chat_id] = next_future

    try:
        while True:
            if shutdown_requested.is_set():
                break

            terminal_action = _consume_terminal_control_command()
            if terminal_action == "stop":
                custom_print("info", "Exit command received. Stopping Telegram bot...")
                shutdown_requested.set()
                break
            if terminal_action == "reset":
                with sessions_lock:
                    sessions.clear()
                custom_print("info", "Reset command received. In-memory Telegram sessions were cleared.")
                continue

            try:
                updates = _telegram_api(
                    token,
                    "getUpdates",
                    {
                        "offset": offset,
                        # Keep timeout modest to make terminal exit commands responsive.
                        "timeout": 5,
                        "allowed_updates": ["message", "edited_message"],
                    },
                ).get("result", [])
            except Exception as e:
                # Telegram/network hiccups should not stop the runtime.
                custom_print("warn", f"Telegram polling warning: {e}. Retrying...")
                time.sleep(2)
                continue

            for update in updates:
                try:
                    offset = max(offset, int(update["update_id"]) + 1)
                    message = update.get("message") or update.get("edited_message")
                    if not message:
                        continue

                    chat = message.get("chat") or {}
                    chat_id = int(chat.get("id", 0))
                    if not chat_id or not _is_allowed_chat(chat_id, allowed_chat_ids):
                        continue

                    if shutdown_requested.is_set():
                        break

                    _submit_update(chat_id, update)
                except Exception as e:
                    custom_print("warn", f"Telegram update handling warning: {e}. Continuing...")
                    continue

            if shutdown_requested.is_set():
                # Confirm processed updates (including /shutdown) without flushing newer pending messages.
                _telegram_api(
                    token,
                    "getUpdates",
                    {
                        "offset": offset,
                        "timeout": 0,
                        "allowed_updates": ["message", "edited_message"],
                    },
                )
                break
    except KeyboardInterrupt:
        custom_print("info", "Telegram bot interrupted. Stopping...")
    except Exception as e:
        custom_print("error", f"Unexpected fatal Telegram runtime error: {e}")
    finally:
        worker_executor.shutdown(wait=True)
        _unload_ollama_models_in_sessions(sessions)
        _stop_mcp_server_if_running()
        custom_print("exit", "Telegram bot stopped.", 130)
