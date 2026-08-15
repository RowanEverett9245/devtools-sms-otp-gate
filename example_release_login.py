import json
import os

from release_otp import DevtoolsLoginService, InfraiSmsClient, VerifyCodeRequest


def main() -> None:
    phone = os.environ.get("DEMO_PHONE")
    code = os.environ.get("DEMO_CODE")
    if not phone or not code:
        raise RuntimeError("DEMO_PHONE and DEMO_CODE are required")

    result = DevtoolsLoginService(InfraiSmsClient()).verify_code(
        VerifyCodeRequest(
            phone=phone,
            code=code,
            build_event="build.completed",
            release_operation="publish",
            operation_id="release-demo",
        )
    )
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
