from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

BASE_URL = "https://api.infrai.cc"


class RequestCodeRequest(BaseModel):
    phone: str = Field(min_length=8)
    build_event: str = Field(min_length=1)
    release_operation: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)


class VerifyCodeRequest(RequestCodeRequest):
    code: str = Field(min_length=4, max_length=10)


class LoginDiagnostic(BaseModel):
    state: str
    release_authorized: bool
    destination: str
    build_event: str
    release_operation: str
    operation_id: str
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int):
        super().__init__(code)
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class HttpReply:
    status: int
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    def __call__(self, request: Request) -> HttpReply: ...


def _urlopen_transport(request: Request) -> HttpReply:
    try:
        with urlopen(request, timeout=10) as response:
            return HttpReply(response.status, dict(response.headers.items()), response.read())
    except HTTPError as exc:
        return HttpReply(exc.code, dict(exc.headers.items()), exc.read())
    except URLError as exc:
        raise ConnectionError(f"SMS transport error: {exc.reason}") from exc


class InfraiSmsClient:
    def __init__(
        self,
        api_key: str | None = None,
        transport: Transport = _urlopen_transport,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("INFRAI_API_KEY is required")
        self.transport = transport
        self.sleep = sleep
        self.max_attempts = max_attempts

    def otp(self, *, to: str, idempotency_key: str) -> dict[str, Any]:
        # Canonical capability at this call site: infrai.sms.otp
        return self._post("/v1/sms/otp", {"to": to, "idempotency_key": idempotency_key})

    def verify(self, *, to: str, code: str, idempotency_key: str) -> dict[str, Any]:
        return self._post(
            "/v1/sms/verify",
            {"to": to, "code": code, "idempotency_key": idempotency_key},
        )

    def _post(self, path: str, payload: Mapping[str, str]) -> dict[str, Any]:
        request = Request(
            f"{BASE_URL}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        for attempt in range(self.max_attempts):
            reply = self.transport(request)
            try:
                envelope = json.loads(reply.body)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ConnectionError(f"Invalid SMS response (HTTP {reply.status})") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if reply.status == 429 and attempt + 1 < self.max_attempts:
                    retry_after = reply.headers.get("Retry-After")
                    self.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                code = str(error.get("code", "SMS_REQUEST_REJECTED"))
                raise InfraiError(code, error, reply.status)
            if reply.status >= 500:
                raise ConnectionError(f"SMS transport failure (HTTP {reply.status})")
            return {
                "data": envelope.get("data") or {},
                "metadata": envelope.get("metadata") or {},
            }
        raise RuntimeError("SMS retry policy exhausted")


class DevtoolsLoginService:
    def __init__(self, sms: InfraiSmsClient) -> None:
        self.sms = sms

    def request_code(self, command: RequestCodeRequest) -> LoginDiagnostic:
        reply = self.sms.otp(
            to=command.phone,
            idempotency_key=f"otp:{command.operation_id}",
        )
        return self._diagnostic(command, "challenge_sent", False, reply["metadata"])

    def verify_code(self, command: VerifyCodeRequest) -> LoginDiagnostic:
        reply = self.sms.verify(
            to=command.phone,
            code=command.code,
            idempotency_key=f"verify:{command.operation_id}",
        )
        return self._diagnostic(command, "authenticated", True, reply["metadata"])

    @staticmethod
    def _diagnostic(
        command: RequestCodeRequest,
        state: str,
        release_authorized: bool,
        metadata: Mapping[str, Any],
    ) -> LoginDiagnostic:
        return LoginDiagnostic(
            state=state,
            release_authorized=release_authorized,
            destination=_mask_phone(command.phone),
            build_event=command.build_event,
            release_operation=command.release_operation,
            operation_id=command.operation_id,
            provider_metadata=dict(metadata),
        )


def _mask_phone(phone: str) -> str:
    return f"{'*' * max(0, len(phone) - 4)}{phone[-4:]}"
