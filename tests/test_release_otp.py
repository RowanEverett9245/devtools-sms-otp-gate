from typing import Any

from release_otp import DevtoolsLoginService, RequestCodeRequest, VerifyCodeRequest


class AcceptedSms:
    def otp(self, **request: str) -> dict[str, Any]:
        assert request["idempotency_key"] == "otp:build-184"
        return {"data": {"message_id": "msg-1"}, "metadata": {"vendor": "auto"}}

    def verify(self, **request: str) -> dict[str, Any]:
        assert request == {
            "to": "+14155550123",
            "code": "123456",
            "idempotency_key": "verify:build-184",
        }
        return {"data": {"verified": True}, "metadata": {"vendor": "auto"}}


def test_release_is_authorized_only_after_code_verification() -> None:
    service = DevtoolsLoginService(AcceptedSms())  # type: ignore[arg-type]
    context = {
        "phone": "+14155550123",
        "build_event": "build.completed",
        "release_operation": "publish",
        "operation_id": "build-184",
    }

    sent = service.request_code(RequestCodeRequest(**context))
    verified = service.verify_code(VerifyCodeRequest(**context, code="123456"))

    assert sent.state == "challenge_sent"
    assert sent.release_authorized is False
    assert verified.state == "authenticated"
    assert verified.release_authorized is True
    assert verified.operation_id == "build-184"
    assert verified.destination == "********0123"
