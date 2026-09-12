"""Small encrypted credential store for the Jarvis desktop app.

On Windows, credentials are protected with DPAPI and bound to the current
Windows user. The encrypted file is never intended to be committed to Git.
On non-Windows systems this module is a no-op so provider configuration keeps
working through normal environment variables.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

_STORE_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Jarvis"
_STORE_PATH = _STORE_DIR / "credentials.dat"


def _protect(data: bytes) -> bytes:
    if os.name != "nt":
        return data
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    target = DATA_BLOB()
    if not crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)):
        raise OSError("Windows credential protection failed")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


def _unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        return data
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    target = DATA_BLOB()
    if not crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)):
        raise OSError("Windows credential decryption failed")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


def load_credentials() -> dict[str, str]:
    try:
        raw = _STORE_PATH.read_bytes()
        payload: Any = json.loads(_unprotect(base64.b64decode(raw)).decode("utf-8"))
        return {str(k): str(v) for k, v in payload.items() if isinstance(k, str) and isinstance(v, str) and v}
    except (OSError, ValueError, TypeError, json.JSONDecodeError, base64.binascii.Error):
        return {}


def get_credential(name: str) -> str:
    return load_credentials().get(name, "")


def set_credential(name: str, value: str) -> None:
    if not value:
        return
    credentials = load_credentials()
    credentials[name] = value
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    encoded = base64.b64encode(_protect(json.dumps(credentials, separators=(",", ":")).encode("utf-8")))
    temp = _STORE_PATH.with_suffix(".tmp")
    temp.write_bytes(encoded)
    os.replace(temp, _STORE_PATH)


def delete_credential(name: str) -> None:
    credentials = load_credentials()
    if name not in credentials:
        return
    del credentials[name]
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    encoded = base64.b64encode(_protect(json.dumps(credentials, separators=(",", ":")).encode("utf-8")))
    temp = _STORE_PATH.with_suffix(".tmp")
    temp.write_bytes(encoded)
    os.replace(temp, _STORE_PATH)
