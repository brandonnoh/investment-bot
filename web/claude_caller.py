#!/usr/bin/env python3
"""Claude API/CLI 호출 — API 키 우선, OAuth CLI 폴백."""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT_ROOT = Path(__file__).parent.parent

CLAUDE_BIN = shutil.which("claude") or "/usr/local/bin/claude"
_CRED_SRC = Path("/root/.claude-host/.credentials.json")
_CRED_DST = Path("/root/.claude/.credentials.json")


def _cred_expiry(path: Path) -> int:
    """credentials.json의 claudeAiOauth.expiresAt(ms) 반환. 파싱 실패 시 0."""
    try:
        data = json.loads(path.read_text())
        return int(data.get("claudeAiOauth", {}).get("expiresAt", 0))
    except Exception:
        return 0


def sync_credentials() -> None:
    """호스트 재인증 후 갱신된 OAuth 토큰을 컨테이너로 동기화.
    컨테이너 토큰이 더 최신(expiresAt 기준)이면 덮어쓰지 않음."""
    if not _CRED_SRC.exists():
        return
    try:
        if _CRED_DST.exists() and _cred_expiry(_CRED_DST) > _cred_expiry(_CRED_SRC):
            return
        shutil.copy2(str(_CRED_SRC), str(_CRED_DST))
    except Exception as e:
        print(f"[advisor] credentials 동기화 실패: {e}")


def _is_auth_error(text: str) -> bool:
    """텍스트가 Anthropic 인증 오류를 포함하는지 확인."""
    low = text.lower()
    return (
        "authentication_error" in low
        or "failed to authenticate" in low
        or "invalid authentication" in low
    )


def _extract_cli_result(raw: str) -> str:
    """--output-format json 응답에서 result 텍스트 추출. 실패 시 원본 반환."""
    for line in reversed(raw.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and "result" in obj:
                return obj["result"]
        except (json.JSONDecodeError, ValueError):
            continue
    return raw.strip()


def _call_claude_api(prompt: str, system: str = "") -> str:
    """Anthropic Messages API 동기 호출. system이 있으면 캐싱 적용."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 없음")
    body: dict = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "prompt-caching-2024-07-31",
        "content-type": "application/json",
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["content"][0]["text"].strip()


def _call_claude_cli(prompt: str, system: str = "") -> str:
    """Claude CLI 호출. system이 있으면 프롬프트 앞에 prepend."""
    full_prompt = f"<system>\n{system}\n</system>\n\n{prompt}" if system else prompt
    result = subprocess.run(
        [CLAUDE_BIN, "--output-format", "json", "-p", "-"],
        input=full_prompt,
        capture_output=True,
        text=True,
        timeout=600,
        cwd=str(PROJECT_ROOT),
    )
    combined = result.stdout + result.stderr
    if _is_auth_error(combined):
        raise RuntimeError("Claude 인증 만료 — 호스트에서 재로그인 필요")
    if result.returncode != 0 and not result.stdout.strip():
        raise RuntimeError(f"Claude CLI 실패: {result.stderr[:300]}")
    text = _extract_cli_result(result.stdout)
    if _is_auth_error(text):
        raise RuntimeError("Claude 인증 만료 — 호스트에서 재로그인 필요")
    return text


def call_claude(prompt: str, system: str = "") -> str:
    """Claude 호출 (API 키 우선, CLI 폴백)."""
    try:
        return _call_claude_api(prompt, system=system)
    except RuntimeError:
        pass
    except Exception as e:
        print(f"[advisor] API 호출 실패, CLI 폴백: {e}")
    sync_credentials()
    return _call_claude_cli(prompt, system=system)


def stream_via_api(prompt: str, system: str = ""):
    """Anthropic API SSE 스트리밍 — content_block_delta 이벤트 yield."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 없음")
    body: dict = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "prompt-caching-2024-07-31",
        "content-type": "application/json",
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "content_block_delta":
                text = event.get("delta", {}).get("text", "")
                if text:
                    yield {"type": "text", "text": text}


def stream_via_cli(prompt: str, system: str = ""):
    """Claude CLI로 전체 응답 수신 후 50자 청크로 yield."""
    full_prompt = f"<system>\n{system}\n</system>\n\n{prompt}" if system else prompt
    result = subprocess.run(
        [CLAUDE_BIN, "--output-format", "json", "-p", "-"],
        input=full_prompt,
        capture_output=True,
        text=True,
        timeout=600,
        cwd=str(PROJECT_ROOT),
    )
    combined = result.stdout + result.stderr
    if _is_auth_error(combined):
        raise RuntimeError("Claude 인증 만료 — 호스트에서 재로그인 필요")
    if result.returncode != 0 and not result.stdout.strip():
        raise RuntimeError(f"Claude CLI 실패: {result.stderr[:300]}")
    text = _extract_cli_result(result.stdout)
    if _is_auth_error(text):
        raise RuntimeError("Claude 인증 만료 — 호스트에서 재로그인 필요")
    for i in range(0, len(text), 50):
        yield {"type": "text", "text": text[i : i + 50]}
