"""
DashScope / 百炼统一调用入口。

目标：
1. 按模型族做保守的并发与匀速调度，避免瞬时突发触发限流保护。
2. 为 429 / 5xx 等可恢复错误提供统一指数退避。
3. 同时支持 async httpx 调用和 dashscope SDK 的同步调用。
"""
from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPolicy:
    name: str
    aliases: tuple[str, ...]
    max_concurrency: int
    min_interval_seconds: float
    max_retries: int = 4
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 20.0


POLICIES: tuple[ModelPolicy, ...] = (
    # qwen-long 和上传链路是当前真实导入流程里最容易先被打满的部分。
    ModelPolicy(
        name="qwen-long",
        aliases=("qwen-long",),
        max_concurrency=4,
        min_interval_seconds=0.15,
    ),
    # qwen-turbo 在答案解析、作文话题、模板/范文生成里被频繁使用。
    ModelPolicy(
        name="qwen-turbo",
        aliases=("qwen-turbo",),
        max_concurrency=4,
        min_interval_seconds=0.15,
    ),
    # qwen-plus 配额更宽松，但仍然需要削峰，避免短时间内突增。
    ModelPolicy(
        name="qwen-plus",
        aliases=("qwen-plus", "qwen3.5-plus"),
        max_concurrency=8,
        min_interval_seconds=0.08,
    ),
    ModelPolicy(
        name="dashscope-upload",
        aliases=("dashscope-upload",),
        max_concurrency=3,
        min_interval_seconds=0.20,
        max_retries=3,
    ),
)

DEFAULT_POLICY = ModelPolicy(
    name="default",
    aliases=(),
    max_concurrency=3,
    min_interval_seconds=0.20,
    max_retries=3,
)

RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
RETRYABLE_ERROR_SIGNALS = (
    "requests rate limit exceeded",
    "you exceeded your current requests list",
    "allocated quota exceeded",
    "you exceeded your current quota",
    "request rate increased too quickly",
    "rate limit",
    "timed out",
    "timeout",
    "connection reset",
    "temporarily unavailable",
)


class DashScopeRequestError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body

    def __str__(self) -> str:
        base = super().__str__()
        if self.body:
            return f"{base} - {self.body}"
        return base


class _GateState:
    def __init__(self, policy: ModelPolicy):
        self.policy = policy
        self.semaphore = threading.BoundedSemaphore(policy.max_concurrency)
        self.lock = threading.Lock()
        self.next_allowed_at = 0.0

    def reserve_wait_seconds(self) -> float:
        with self.lock:
            now = time.monotonic()
            ready_at = max(now, self.next_allowed_at)
            self.next_allowed_at = ready_at + self.policy.min_interval_seconds
            return max(0.0, ready_at - now)


class DashScopeLimiter:
    def __init__(self) -> None:
        self._states: dict[str, _GateState] = {}
        self._states_lock = threading.Lock()

    def policy_for(self, model: str) -> ModelPolicy:
        if not model:
            return DEFAULT_POLICY
        for policy in POLICIES:
            for alias in policy.aliases:
                if model == alias or model.startswith(f"{alias}-"):
                    return policy
        return DEFAULT_POLICY

    def _get_state(self, model: str) -> _GateState:
        policy = self.policy_for(model)
        with self._states_lock:
            state = self._states.get(policy.name)
            if state is None:
                state = _GateState(policy)
                self._states[policy.name] = state
            return state

    async def acquire_async(self, model: str) -> _GateState:
        state = self._get_state(model)
        while not state.semaphore.acquire(blocking=False):
            await asyncio.sleep(0.05)

        wait_seconds = state.reserve_wait_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        return state

    @contextmanager
    def acquire_sync(self, model: str):
        state = self._get_state(model)
        state.semaphore.acquire()
        try:
            wait_seconds = state.reserve_wait_seconds()
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            yield
        finally:
            state.semaphore.release()


limiter = DashScopeLimiter()


def _format_error_message(exc: Exception) -> str:
    if isinstance(exc, DashScopeRequestError):
        if exc.status_code is not None:
            return f"{exc.status_code}: {exc}"
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        return f"{exc.response.status_code}: {exc}"
    return str(exc)


def _is_retryable_exception(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in RETRYABLE_STATUS_CODES:
        return True

    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None) in RETRYABLE_STATUS_CODES:
        return True

    message = _format_error_message(exc).lower()
    return any(signal in message for signal in RETRYABLE_ERROR_SIGNALS)


def _backoff_seconds(policy: ModelPolicy, attempt: int) -> float:
    base = min(policy.base_delay_seconds * (2 ** attempt), policy.max_delay_seconds)
    return base * random.uniform(0.85, 1.25)


async def run_with_async_retries(
    *,
    model: str,
    operation: str,
    func: Callable[[], Any],
    max_retries: int | None = None,
) -> Any:
    policy = limiter.policy_for(model)
    retry_limit = policy.max_retries if max_retries is None else max_retries
    last_error: Exception | None = None

    for attempt in range(retry_limit):
        state = await limiter.acquire_async(model)
        try:
            return await func()
        except Exception as exc:
            last_error = exc
            if not _is_retryable_exception(exc) or attempt >= retry_limit - 1:
                raise

            delay = _backoff_seconds(policy, attempt)
            logger.warning(
                "DashScope async call retrying: operation=%s model=%s attempt=%s/%s wait=%.2fs error=%s",
                operation,
                model,
                attempt + 1,
                retry_limit,
                delay,
                _format_error_message(exc),
            )
            await asyncio.sleep(delay)
        finally:
            state.semaphore.release()

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"DashScope async call failed unexpectedly: {operation}")


def run_with_sync_retries(
    *,
    model: str,
    operation: str,
    func: Callable[[], Any],
    max_retries: int | None = None,
) -> Any:
    policy = limiter.policy_for(model)
    retry_limit = policy.max_retries if max_retries is None else max_retries
    last_error: Exception | None = None

    for attempt in range(retry_limit):
        try:
            with limiter.acquire_sync(model):
                return func()
        except Exception as exc:
            last_error = exc
            if not _is_retryable_exception(exc) or attempt >= retry_limit - 1:
                raise

            delay = _backoff_seconds(policy, attempt)
            logger.warning(
                "DashScope sync call retrying: operation=%s model=%s attempt=%s/%s wait=%.2fs error=%s",
                operation,
                model,
                attempt + 1,
                retry_limit,
                delay,
                _format_error_message(exc),
            )
            time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"DashScope sync call failed unexpectedly: {operation}")


async def async_chat_completion(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    operation: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_seconds: float = 120.0,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if extra_payload:
        payload.update(extra_payload)

    async def _call() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if response.status_code != 200:
                raise DashScopeRequestError(
                    f"API调用失败: {response.status_code}",
                    status_code=response.status_code,
                    body=response.text,
                )
            return response.json()

    return await run_with_async_retries(
        model=model,
        operation=operation,
        func=_call,
    )


async def async_upload_file(
    *,
    api_key: str,
    file_path: str | Path,
    purpose: str,
    operation: str,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    path = Path(file_path)

    async def _call() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            with path.open("rb") as fh:
                response = await client.post(
                    "https://dashscope.aliyuncs.com/compatible-mode/v1/files",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={
                        "file": (
                            path.name,
                            fh,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    },
                    data={"purpose": purpose},
                )

            if response.status_code != 200:
                raise DashScopeRequestError(
                    "上传文件失败",
                    status_code=response.status_code,
                    body=response.text,
                )
            return response.json()

    return await run_with_async_retries(
        model="dashscope-upload",
        operation=operation,
        func=_call,
        max_retries=3,
    )


def sync_generation_call(
    *,
    api_key: str,
    model: str,
    prompt: str,
    operation: str,
    result_format: str = "message",
    **kwargs: Any,
):
    import dashscope
    from dashscope import Generation

    dashscope.api_key = api_key

    def _call():
        response = Generation.call(
            model=model,
            prompt=prompt,
            result_format=result_format,
            **kwargs,
        )
        status_code = getattr(response, "status_code", None)
        if status_code != 200:
            raise DashScopeRequestError(
                getattr(response, "message", "DashScope SDK 调用失败"),
                status_code=status_code,
            )
        return response

    return run_with_sync_retries(
        model=model,
        operation=operation,
        func=_call,
    )
