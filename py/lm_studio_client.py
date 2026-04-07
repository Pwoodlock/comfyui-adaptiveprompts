"""
LM Studio Client Wrapper for cc-prompt-studio

Reuses LM Studio integration patterns from 1_Charactor-Kreator/core/common.py
and 1_Charactor-Kreator/core/bbw.py

Provides:
- Model probing/listing from LM Studio
- LLM completion with system/user prompts
- SDK auto-install with HTTP fallback
"""

import importlib
import json
import urllib.request
import urllib.error
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
    if command[-1] == "lmstudio" and result.returncode == 0:
        return True
    return False


def _get_lmstudio_sdk():
    """
    Get LM Studio Python SDK module with auto-install fallback.

    Returns:
        lmstudio module or None if unavailable
    """
    global _SDK_MODULE, _SDK_ERROR, _SDK_INSTALL_ATTEMPTED

    if _SDK_MODULE:
        return _SDK_MODULE

    _SDK_INSTALL_ATTEMPTED = True

    try:
        _SDK_MODULE = importlib.import_module("lmstudio")
        return _SDK_MODULE
    except ImportError:
        # Attempt auto-install
        if _attempt_lmstudio_install():
            _SDK_MODULE = importlib.import_module("lmstudio")
            return _SDK_MODULE
        else:
            _SDK_ERROR = (
                "LM Studio Python SDK is not available and the automatic install path did not succeed. "
                f"Install it manually with `{sys.executable} -m pip install lmstudio`."
            )
            return None


def get_lm_studio_models(host: str = "localhost", port: int = 1234) -> List[str]:
    """
    Probe LM Studio for available LLM models.

    Args:
        host: LM Studio host
        port: LM Studio port

    Returns:
        List of model names, or empty list if unavailable
    """
    try:
        url = f"http://{host}:{port}/v1/models"
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if "data" in data:
                return [model["id"] for model in data["data"]]
            return []
    except Exception as exc:
        return []


def call_lm_studio(
    model: str,
    user_prompt: str,
    system_prompt: str = "",
    host: str = "localhost",
    port: int = 1234,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """
    Call LM Studio with the given prompt and return the response.

    Args:
        model: Model name/ID
        user_prompt: User message/prompt
        system_prompt: System message (optional)
        host: LM Studio host
        port: LM Studio port
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        LLM response text
    """
    lms = _get_lmstudio_sdk()

    if lms:
        # Use SDK
        try:
            lms_model = lms.llm(model)
            chat = lms.Chat()

            if system_prompt:
                chat.add_system_prompt(system_prompt)

            response = chat.complete(user_prompt)

            # Extract text from response
            if hasattr(response, 'choices'):
                if response.choices and len(response.choices) > 0:
                    return response.choices[0].message.content
            return str(response)

        except Exception as exc:
            return f"SDK Error: {exc}"
    else:
        # HTTP fallback
        return _http_lm_studio_request(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            host=host,
            port=port,
            temperature=temperature,
            max_tokens=max_tokens
        )


def _http_lm_studio_request(
    model: str,
    user_prompt: str,
    system_prompt: str = "",
    host: str = "localhost",
    port: int = 1234,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """
    HTTP API fallback for LM Studio requests.
    """
    url = f"http://{host}:{port}/v1/chat/completions"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            return "Error: Unexpected response format"

    except Exception as exc:
        return f"HTTP Error: {exc}"


def get_sdk_error() -> Optional[str]:
    """Get the SDK error message if SDK failed to load."""
    return _SDK_ERROR


def is_sdk_available() -> bool:
    """Check if LM Studio SDK is available."""
    return _get_lmstudio_sdk() is not None
