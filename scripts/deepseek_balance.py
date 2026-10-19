#!/usr/bin/env python3
"""Read the balance shown by DSH's signed-in DeepSeek account.

DSH keeps an account grant in its own credential store and queries
Platform's recharge wallets. omastat reuses that grant against the same
endpoint so the number matches the DSH account UI. If no DSH account grant is
present, the previous official API-key balance remains as a fallback.

Only public balance numbers leave this module. The account grant is used as
the x-dsh-auth-token header and is never stored in snapshots or diagnostics.
"""
from __future__ import annotations

import datetime
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import urllib.request

BALANCE_URL = "https://api.deepseek.com/user/balance"
PLATFORM_ORIGIN = "https://platform.deepseek.com"
DSH_SUMMARY_PATH = "/api/v0/users/get_user_summary"
DSH_CLIENT_VERSION = "0.2.1-rc.2"
BALANCE_TTL = 300
BALANCE_RETRY = 60
_KEY_RE = re.compile(r"(?m)^\s*DEEPSEEK_API_KEY\s*:\s*['\"]?(sk-[A-Za-z0-9_-]{8,})['\"]?\s*$")
_TOKEN_RE = re.compile(r"(?ms)deepseek-account-platform/default:.*?payload:.*?token:\s*['\"]?([^\s'\"]+).*?issuer:\s*['\"]?([^\s'\"]+)")


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _credentials_paths(home):
    home = Path(home or Path.home())
    dsh_home = os.environ.get("DSH_HOME")
    if dsh_home:
        return [Path(dsh_home) / ".credentials.yaml"]
    return [home / ".dsh" / ".credentials.yaml"]


def _read_credentials_text(home):
    for path in _credentials_paths(home):
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return ""


def read_api_key(home=None):
    """Return a DeepSeek API key from env or DSH's credential store."""
    env_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if env_key.startswith("sk-") and len(env_key) > 8:
        return env_key
    text = _read_credentials_text(home)
    match = _KEY_RE.search(text)
    return match.group(1) if match else None


def read_dsh_credentials(home=None):
    """Return (account grant token, platform origin) from DSH credentials."""
    text = _read_credentials_text(home)
    if not text:
        return None, None
    token = issuer = None
    try:
        import yaml
        data = yaml.safe_load(text)
        record = (((data or {}).get("records") or {}).get("deepseek-account-platform/default") or {})
        payload = record.get("payload") if isinstance(record, dict) else None
        if isinstance(payload, dict):
            token = payload.get("token") if isinstance(payload.get("token"), str) else None
            issuer = payload.get("issuer") if isinstance(payload.get("issuer"), str) else None
    except Exception:
        token = issuer = None
    if not token:
        match = _TOKEN_RE.search(text)
        if match:
            token, issuer = match.group(1), match.group(2)
    token = (token or "").strip()
    issuer = (issuer or PLATFORM_ORIGIN).strip()
    if not token or not issuer.startswith("https://"):
        return None, None
    return token, issuer.rstrip("/")


def _wallet(entries):
    if not isinstance(entries, list):
        return None
    values = [entry for entry in entries if isinstance(entry, dict)]
    if not values:
        return None
    entry = next((item for item in values
                  if str(item.get("currency") or "").upper() == "CNY"), values[0])
    balance = _number(entry.get("balance"))
    if balance is None:
        return None
    return {"currency": str(entry.get("currency") or "CNY")[:8], "balance": balance}


def fetch_dsh_balance(token, issuer=PLATFORM_ORIGIN, timeout=8):
    """Query the same Platform summary endpoint as DSH's account panel."""
    headers = {
        "accept": "application/json",
        "user-agent": "omastat/1.0",
        "x-dsh-auth-token": token,
        "x-client-bundle-id": "",
        "x-client-platform": "web",
        "x-client-version": DSH_CLIENT_VERSION,
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": str(int(datetime.datetime.now().astimezone().utcoffset().total_seconds())),
    }
    request = urllib.request.Request(issuer.rstrip("/") + DSH_SUMMARY_PATH, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("DSH balance HTTP " + str(response.status))
        payload = json.loads(response.read().decode("utf-8", "replace"))
    envelope = payload if isinstance(payload, dict) else {}
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    if envelope.get("code") != 0 or data.get("biz_code") != 0:
        raise ValueError("DSH balance rejected")
    summary = data.get("biz_data") if isinstance(data.get("biz_data"), dict) else {}
    normal = _wallet(summary.get("normal_wallets"))
    bonus = _wallet(summary.get("bonus_wallets"))
    if normal is None and bonus is None:
        raise ValueError("no DSH balance")
    total = normal["balance"] if normal is not None else bonus["balance"]
    return {
        "available": True,
        "source": "dsh",
        "currency": (normal or bonus)["currency"],
        "total": total,
        "normal": normal["balance"] if normal is not None else None,
        "bonus": bonus["balance"] if bonus is not None else None,
        "fetchedAtMs": int(time.time() * 1000),
    }


def fetch_balance(key, timeout=8):
    """Return public balance fields from the official DeepSeek API."""
    request = urllib.request.Request(
        BALANCE_URL,
        headers={
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
            "User-Agent": "omastat/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("balance HTTP " + str(response.status))
        payload = json.loads(response.read().decode("utf-8", "replace"))
    if not isinstance(payload, dict):
        raise ValueError("invalid balance response")
    infos = [entry for entry in payload.get("balance_infos", [])
             if isinstance(entry, dict)] if isinstance(payload.get("balance_infos"), list) else []
    if not infos:
        raise ValueError("no balance info")
    info = next((entry for entry in infos
                 if str(entry.get("currency") or "").upper() == "CNY"), infos[0])
    total = _number(info.get("total_balance"))
    if total is None:
        raise ValueError("no total balance")
    return {
        "available": payload.get("is_available") is not False,
        "source": "api",
        "currency": str(info.get("currency") or "CNY")[:8],
        "total": total,
        "granted": _number(info.get("granted_balance")),
        "toppedUp": _number(info.get("topped_up_balance")),
        "fetchedAtMs": int(time.time() * 1000),
    }


class DeepSeekBalance:
    """Non-blocking balance cache used by the long-running agent service."""

    def __init__(self, home=None, fetcher=None, ttl=BALANCE_TTL, retry=BALANCE_RETRY):
        self.home = Path(home or Path.home())
        self.dsh_token, self.dsh_issuer = read_dsh_credentials(self.home)
        self.key = read_api_key(self.home)
        if self.dsh_token:
            self.source = "dsh"
            self.credential = self.dsh_token
            self._default_fetcher = lambda token: fetch_dsh_balance(token, self.dsh_issuer)
        elif self.key:
            self.source = "api"
            self.credential = self.key
            self._default_fetcher = fetch_balance
        else:
            self.source = None
            self.credential = None
            self._default_fetcher = fetch_balance
        self.fetcher = fetcher or self._default_fetcher
        self.ttl = max(60, int(ttl))
        self.retry = max(15, int(retry))
        self._lock = threading.Lock()
        self._thread = None
        self._state = "unconfigured" if not self.credential else "idle"
        self._data = None
        self._last_attempt = 0.0
        self._error = ""

    @property
    def pending(self):
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def request(self, now=None, force=False):
        now = time.time() if now is None else float(now)
        with self._lock:
            if not self.credential:
                self._state = "unconfigured"
                return
            if self._thread is not None and self._thread.is_alive():
                return
            if self._last_attempt:
                cooldown = 30 if force else (self.retry if self._state == "error" else self.ttl)
                if now - self._last_attempt < cooldown:
                    return
            self._state = "loading"
            self._last_attempt = now
            self._thread = threading.Thread(target=self._run, name="deepseek-balance", daemon=True)
            thread = self._thread
        thread.start()

    def _run(self):
        try:
            data = self.fetcher(self.credential)
        except Exception as error:  # Keep only the exception type; never log credentials.
            with self._lock:
                self._state = "error"
                self._error = type(error).__name__
                self._last_attempt = time.time()
                self._thread = None
        else:
            with self._lock:
                self._data = data
                self._state = "ok"
                self._error = ""
                self._last_attempt = time.time()
                self._thread = None

    def refresh_sync(self, now=None):
        """Synchronous fetch for tests and one-shot diagnostics."""
        now = time.time() if now is None else float(now)
        with self._lock:
            if not self.credential:
                self._state = "unconfigured"
                return self.snapshot(now)
            self._state = "loading"
            self._last_attempt = now
        try:
            data = self.fetcher(self.credential)
        except Exception as error:
            with self._lock:
                self._state = "error"
                self._error = type(error).__name__
        else:
            with self._lock:
                self._data = data
                self._state = "ok"
                self._error = ""
        return self.snapshot(now)

    def snapshot(self, now=None):
        now = time.time() if now is None else float(now)
        with self._lock:
            data = dict(self._data) if isinstance(self._data, dict) else None
            state = self._state
        if data and state == "ok" and data.get("fetchedAtMs") is not None:
            if now - data["fetchedAtMs"] / 1000.0 > self.ttl * 2:
                state = "stale"
        return {
            "state": state,
            "configured": bool(self.credential),
            "source": data.get("source") if data else self.source,
            "currency": data.get("currency") if data else None,
            "total": data.get("total") if data else None,
            "normal": data.get("normal") if data else None,
            "bonus": data.get("bonus") if data else None,
            "granted": data.get("granted") if data else None,
            "toppedUp": data.get("toppedUp") if data else None,
            "available": data.get("available") if data else None,
            "fetchedAtMs": data.get("fetchedAtMs") if data else None,
        }
