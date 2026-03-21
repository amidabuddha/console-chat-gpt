import base64
import io
import re
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from pypdf import PdfReader
from unichat import MODELS_LIST, UnifiedChatApi
from unichat.api_helper import openai

from console_gpt.catch_errors import handle_with_exceptions
from console_gpt.config_manager import fetch_variable
from console_gpt.custom_stdout import custom_print
from console_gpt.ollama_helper import (is_ollama_running, list_ollama_models,
                                       start_ollama)
from mcp_servers.server_manager import ServerManager

REQUEST_TIMEOUT_SECONDS = 120


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

    data = response.json()
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


def _consume_terminal_exit_signal() -> bool:
    """Allow stopping Telegram runtime by typing 'exit'/'quit' in the terminal."""
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        readable, _, _ = select.select([sys.stdin], [], [], 0)
        if not readable:
            return False
        command = sys.stdin.readline().strip().lower()
        return command in ("exit", "quit", "bye")
    except Exception:
        return False


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


def _send_message(token: str, chat_id: int, text: str) -> None:
    for part in _chunk_text(text.strip() or "(empty response)"):
        _telegram_api(token, "sendMessage", {"chat_id": chat_id, "text": part})


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
    role_data = fetch_variable("roles")
    system_role = role_data.get(role_key, "Deliver precise and informative virtual assistance.")

    temperature = fetch_variable("defaults", "temperature")
    return {
        "model": model_data,
        "temperature": temperature,
        "conversation": [{"role": "system", "content": system_role}],
    }


def _default_system_role_content() -> str:
    role_key = fetch_variable("defaults", "system_role")
    role_data = fetch_variable("roles")
    return role_data.get(role_key, "Deliver precise and informative virtual assistance.")


def _reset_session_conversation(session: Dict[str, Any]) -> None:
    session["conversation"] = [{"role": "system", "content": _default_system_role_content()}]


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

    try:
        ollama_models = list_ollama_models()
    except Exception:
        ollama_models = []

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


def _uses_responses_api(model_name: Optional[str]) -> bool:
    return model_name in MODELS_LIST["openai_models"]


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


def _request_model_reply(session: Dict[str, Any]) -> str:
    model_data = session["model"]
    model_name = model_data.get("model_name")
    model_title = model_data.get("model_title")
    api_key = model_data.get("api_key")
    base_url = model_data.get("base_url")
    reasoning_effort = model_data.get("reasoning_effort")
    temperature = session["temperature"]
    conversation = session["conversation"]

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
        client = openai.OpenAI(**client_params)
        params = {
            "model": model_name,
            "input": conversation[1:] if conversation[0]["role"] == "system" else conversation,
            "stream": False,
        }
        if conversation[0]["role"] == "system":
            params["instructions"] = "Formatting re-enabled\n" + conversation[0]["content"]
        if reasoning_effort:
            params.setdefault("reasoning", {})["effort"] = reasoning_effort
            params["reasoning"]["summary"] = "detailed"
        else:
            params["temperature"] = temperature

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

    client = openai.OpenAI(**client_params) if ollama_model else UnifiedChatApi(**client_params)
    params = {
        "model": model_name,
        "messages": conversation,
        "temperature": temperature,
        "stream": False,
    }
    if reasoning_effort:
        params["reasoning_effort"] = reasoning_effort

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
            content: List[Dict[str, Any]] = []
            if caption:
                content.append({"type": "text", "text": caption})
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded_image},
                }
            )
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
) -> Tuple[bool, bool]:
    command = text.split()[0].lower()
    if command == "/start":
        _send_message(
            token,
            chat_id,
            "Telegram mode is active. Send text, images, or .txt/.pdf files to chat with your configured model.\n"
            "Commands: /help, /new, /models, /model, /shutdown",
        )
        return True, False

    if command == "/help":
        _send_message(
            token,
            chat_id,
            "Commands:\n"
            "/new - reset current conversation\n"
            "/models - list available models (config + Ollama, if available)\n"
            "/model - show active model for this chat\n"
            "/model set <name> - switch active model for this chat\n"
            "/shutdown - stop bot runtime (admin chat IDs only)\n"
            "/help - show this message\n\n"
            "You can also send:\n"
            "- plain text\n"
            "- photos (with optional caption)\n"
            "- .txt or .pdf documents (with optional caption)",
        )
        return True, False

    if command == "/new":
        session = sessions.setdefault(chat_id, _build_default_session())
        _reset_session_conversation(session)
        model_title = session["model"].get("model_title", "unknown")
        _send_message(token, chat_id, f"Started a new conversation with model: {model_title}")
        return True, False

    if command == "/models":
        models = _build_model_catalog()
        session = sessions.setdefault(chat_id, _build_default_session())
        active_model = session["model"].get("model_title", "")
        _send_message(token, chat_id, _render_models_list(models, active_model))
        return True, False

    if command == "/model":
        session = sessions.setdefault(chat_id, _build_default_session())
        parts = text.split(maxsplit=2)

        if len(parts) >= 2 and parts[1].lower() in ("list", "ls"):
            models = _build_model_catalog()
            active_model = session["model"].get("model_title", "")
            _send_message(token, chat_id, _render_models_list(models, active_model))
            return True, False

        if len(parts) >= 2 and parts[1].lower() == "set":
            if len(parts) < 3 or not parts[2].strip():
                _send_message(token, chat_id, "Usage: /model set <name>")
                return True, False

            model_selector = parts[2].strip()
            models = _build_model_catalog()
            indexed_keys = _indexed_model_keys(models)

            target_model_key = model_selector
            if model_selector.isdigit():
                model_index = int(model_selector)
                if model_index < 1 or model_index > len(indexed_keys):
                    _send_message(
                        token, chat_id, f"Invalid model index '{model_index}'. Use /models to list valid indexes."
                    )
                    return True, False
                target_model_key = indexed_keys[model_index - 1]

            if target_model_key not in models:
                _send_message(
                    token, chat_id, f"Unknown model '{model_selector}'. Use /models to list available models."
                )
                return True, False

            previous_model = dict(session.get("model", {}))
            session["model"] = dict(models[target_model_key])
            if _is_ollama_model(previous_model) and previous_model.get("model_name") != session["model"].get(
                "model_name"
            ):
                _unload_ollama_model(previous_model)

            _reset_session_conversation(session)
            model_name = session["model"].get("model_name", "unknown")
            _send_message(token, chat_id, f"Switched model to {target_model_key} ({model_name}). Conversation reset.")
            return True, False

        model_name = session["model"].get("model_name", "unknown")
        model_title = session["model"].get("model_title", "unknown")
        _send_message(
            token,
            chat_id,
            f"Active model: {model_title} ({model_name})\nUse /models to list available models or /model set <name> to switch.",
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

    custom_print("warn", "Telegram mode detected. Streaming is disabled in Telegram runtime.")
    if fetch_variable("features", "mcp_client", auto_exit=False):
        custom_print("warn", "Telegram mode detected. MCP is disabled in Telegram runtime.")
        _stop_mcp_server_if_running()
    custom_print("info", "Starting Telegram bot polling loop...")

    # Validate token early and fail fast with a clear message.
    bot_info = _telegram_api(token, "getMe").get("result", {})
    bot_username = bot_info.get("username", "unknown")
    custom_print("ok", f"Telegram bot connected: @{bot_username}")

    sessions: Dict[int, Dict[str, Any]] = {}
    offset = 0
    process_start_ts = int(time.time())
    shutdown_requested = False

    try:
        while True:
            if _consume_terminal_exit_signal():
                custom_print("info", "Exit command received. Stopping Telegram bot...")
                break

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

            for update in updates:
                offset = max(offset, int(update["update_id"]) + 1)
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue

                chat = message.get("chat") or {}
                chat_id = int(chat.get("id", 0))
                if not chat_id or not _is_allowed_chat(chat_id, allowed_chat_ids):
                    continue

                text = (message.get("text") or "").strip()
                if text.startswith("/"):
                    command = text.split()[0].lower()
                    if command == "/shutdown":
                        message_ts = int(message.get("date") or 0)
                        # Ignore stale shutdown commands that were sent before this bot process started.
                        if message_ts and message_ts < process_start_ts:
                            custom_print("info", f"Ignored stale /shutdown from chat_id={chat_id}.")
                            continue
                    handled, should_shutdown = _handle_command(text, chat_id, token, sessions, admin_chat_ids)
                    if should_shutdown:
                        custom_print("info", f"Remote shutdown requested by chat_id={chat_id}.")
                        shutdown_requested = True
                        break
                    if handled:
                        continue

                session = sessions.setdefault(chat_id, _build_default_session())
                model_title = session["model"].get("model_title", "")
                model_name = session["model"].get("model_name")
                user_content = _build_user_content_from_message(
                    token, message, model_title, _uses_responses_api(model_name)
                )
                if not user_content:
                    _send_message(token, chat_id, "Unsupported input. Send text, an image, or a .txt/.pdf document.")
                    continue

                session["conversation"].append({"role": "user", "content": user_content})
                _telegram_api(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
                reply = _request_model_reply(session)
                _send_message(token, chat_id, reply)

            if shutdown_requested:
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
        custom_print("error", f"Telegram loop error: {e}")
        try:
            time.sleep(2)
        except KeyboardInterrupt:
            pass
    finally:
        _unload_ollama_models_in_sessions(sessions)
        _stop_mcp_server_if_running()
        custom_print("exit", "Telegram bot stopped.", 130)
