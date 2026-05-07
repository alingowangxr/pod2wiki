"""Proxy helpers for pod2wiki.

Set PODCAST_PROXY to a full proxy URL such as socks5://127.0.0.1:1080.
If it is missing, the tools run direct instead of failing.
"""

from __future__ import annotations

import os
import socket
from typing import Dict, Optional


def _port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def detect_proxy() -> Optional[str]:
    explicit = os.environ.get("PODCAST_PROXY")
    if explicit:
        return explicit
    for port in range(12345, 12351):
        if _port_open("127.0.0.1", port):
            return f"socks5://127.0.0.1:{port}"
    return None


PROXY = detect_proxy()


def requests_proxy() -> Optional[Dict[str, str]]:
    if not PROXY:
        return None
    return {"http": PROXY, "https": PROXY}
