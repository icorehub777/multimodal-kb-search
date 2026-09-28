from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Protocol

from kbsearch_cli.errors import AuthenticationError

GOOGLE_OAUTH_CREDENTIAL_TARGET = "KBSearch.GoogleDriveOAuth"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2


class CredentialStore(Protocol):
    def read(self) -> str | None: ...

    def write(self, value: str) -> None: ...

    def delete(self) -> bool: ...


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class WindowsCredentialStore:
    def __init__(self, target: str = GOOGLE_OAUTH_CREDENTIAL_TARGET) -> None:
        self._target = target

    @staticmethod
    def _advapi32():
        try:
            api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        except (AttributeError, OSError) as exc:
            raise AuthenticationError(
                "Windows Credential Manager is unavailable on this system."
            ) from exc
        api.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(_Credential)),
        ]
        api.CredReadW.restype = wintypes.BOOL
        api.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredFree.restype = None
        return api

    def read(self) -> str | None:
        api = self._advapi32()
        credential = ctypes.POINTER(_Credential)()
        if not api.CredReadW(self._target, _CRED_TYPE_GENERIC, 0, ctypes.byref(credential)):
            error = ctypes.get_last_error()
            if error == 1168:
                return None
            raise AuthenticationError(f"Unable to read Windows credential (error {error}).")
        try:
            item = credential.contents
            data = ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize)
            return data.decode("utf-8")
        finally:
            api.CredFree(credential)

    def write(self, value: str) -> None:
        api = self._advapi32()
        encoded = value.encode("utf-8")
        blob = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
        credential = _Credential()
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = self._target
        credential.CredentialBlobSize = len(encoded)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "KBSearch"
        if not api.CredWriteW(ctypes.byref(credential), 0):
            error = ctypes.get_last_error()
            raise AuthenticationError(f"Unable to write Windows credential (error {error}).")

    def delete(self) -> bool:
        api = self._advapi32()
        if api.CredDeleteW(self._target, _CRED_TYPE_GENERIC, 0):
            return True
        error = ctypes.get_last_error()
        if error == 1168:
            return False
        raise AuthenticationError(f"Unable to delete Windows credential (error {error}).")
