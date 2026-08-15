from fastapi import FastAPI, HTTPException

from release_otp import (
    DevtoolsLoginService,
    InfraiError,
    InfraiSmsClient,
    LoginDiagnostic,
    RequestCodeRequest,
    VerifyCodeRequest,
)

app = FastAPI(title="Developer tools SMS login")


def _service() -> DevtoolsLoginService:
    return DevtoolsLoginService(InfraiSmsClient())


def _client_error(error: InfraiError) -> HTTPException:
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return HTTPException(status_code=status, detail={"code": error.code, **error.detail})


@app.post("/login/code", response_model=LoginDiagnostic)
def request_code(command: RequestCodeRequest) -> LoginDiagnostic:
    try:
        return _service().request_code(command)
    except InfraiError as error:
        raise _client_error(error) from error


@app.post("/login/verify", response_model=LoginDiagnostic)
def verify_code(command: VerifyCodeRequest) -> LoginDiagnostic:
    try:
        return _service().verify_code(command)
    except InfraiError as error:
        raise _client_error(error) from error
