"""
LM Studio Client Wrapper for cc-prompt-studio

Using the exact SDK pattern from 1_Charactor-Kreator/core/bbw.py
"""

import importlib
import json
import threading
import urllib.error
import urllib.request
import subprocess
import sys
from typing import List, Optional, Dict, Any


_SDK_MODULE = None
_SDK_ERROR = None
_SDK_INSTALL_ATTEMPTED = False


def _run_subprocess(command, timeout):
    """Run subprocess command with timeout."""
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _attempt_lmstudio_install():
    """Attempt to install LM Studio Python SDK."""
    command = [sys.executable, "-m", "pip", "install", "lmstudio"]
    result = _run_subprocess(command, timeout=60)
    return result.returncode == 0


def _get_lmstudio_sdk():
    """
    Get LM Studio Python SDK module with auto-install fallback.
    """
    global _SDK_MODULE, _SDK_ERROR, _SDK_INSTALL_ATTEMPTED

    if _SDK_MODULE:
        return _SDK_MODULE

    _SDK_INSTALL_ATTEMPTED = True

    try:
        _SDK_MODULE = importlib.import_module("lmstudio")
        return _SDK_MODULE
    except ImportError:
        if _attempt_lmstudio_install():
            _SDK_MODULE = importlib.import_module("lmstudio")
            return _SDK_MODULE
        else:
            _SDK_ERROR = "LM Studio Python SDK not available"
            return None


def _call_lm_studio_with_timeout(lms_model, chat, config, timeout_seconds):
    """Call lms_model.respond() with a timeout using a background thread."""
    result = {"response": None, "error": None}

    def _call():
        try:
            result["response"] = lms_model.respond(chat, config=config)
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=_call, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        raise TimeoutError(f"LM Studio request timed out after {timeout_seconds} seconds.")

    if result["error"] is not None:
        raise result["error"]

    return result["response"]


def get_lm_studio_models(host: str = "localhost", port: int = 1234) -> List[str]:
    """Probe LM Studio for available LLM models."""
    try:
        url = f"http://{host}:{port}/v1/models"
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if "data" in data:
                return [model["id"] for model in data["data"]]
            return []
    except Exception as exc:
        print(f"[LM Studio] Error fetching models: {exc}")
        return []


def is_model_loaded(model: str, host: str = "localhost", port: int = 1234) -> bool:
    """Check if a specific model is currently loaded in LM Studio."""
    try:
        models = get_lm_studio_models(host, port)
        return any(m == model or m.endswith("/" + model) for m in models)
    except:
        return False


def wait_for_model(model: str, host: str = "localhost", port: int = 1234, max_wait: int = 60) -> bool:
    """Wait for a model to be loaded in LM Studio."""
    import time
    print(f"[LM Studio] Waiting for model '{model}' to load...")

    for i in range(max_wait):
        if is_model_loaded(model, host, port):
            print(f"[LM Studio] Model '{model}' is ready!")
            return True
        time.sleep(1)

    print(f"[LM Studio] Timeout waiting for model '{model}'")
    return False


def call_lm_studio(
    model: str,
    user_prompt: str,
    system_prompt: str = "",
    host: str = "localhost",
    port: int = 1234,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    seed: int = 0,
    wait_for_load: bool = False,
    timeout_seconds: int = 300,
) -> str:
    """
    Call LM Studio with the given prompt and return the response.

    Uses the exact SDK pattern from 1_Charactor-Kreator.
    """
    # Optionally wait for model to be loaded
    if wait_for_load:
        wait_for_model(model, host, port, max_wait=60)

    lms = _get_lmstudio_sdk()

    if not lms:
        return "Error: LM Studio SDK not available. Install with: pip install lmstudio"

    try:
        # Get model (using the SDK's llm() method)
        lms_model = lms.llm(model)

        if lms_model is None:
            return f"Error: LM Studio could not load model '{model}'"

        # Create chat and add prompts
        chat = lms.Chat()
        chat.add_system_prompt(system_prompt)
        chat.add_user_message(user_prompt)

        # Config with camelCase keys (SDK expects this)
        config = {
            "temperature": temperature,
            "maxTokens": max_tokens,
            "seed": seed,
        }

        # Call with timeout
        response = _call_lm_studio_with_timeout(lms_model, chat, config, timeout_seconds)

        # Extract content from response
        return getattr(response, "content", str(response))

    except Exception as exc:
        return f"Error: {exc}"


def get_sdk_error() -> Optional[str]:
    """Get the SDK error message if SDK failed to load."""
    return _SDK_ERROR


def is_sdk_available() -> bool:
    """Check if LM Studio SDK is available."""
    return _get_lmstudio_sdk() is not None
