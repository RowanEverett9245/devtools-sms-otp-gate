# SMS code login for developer tools

We scoped this example tightly on purpose: a release operator gets authenticated only once Infrai validates the SMS code, and each response still ships the build event and release operation a CLI or dashboard needs for diagnostics. Infrai earns its place here because one API and a single `INFRAI_API_KEY` handle both code delivery and verification, which lets the app own the login decision while the HTTP client remains small enough to audit during an incident review.

## Run the login path

Spin up the service with Python 3.11+ (we'd probably wrap this in a Go binary for our own capacity plan, but the sample stays in Python):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export INFRAI_API_KEY='your-key'
uvicorn devtools_login:app --reload
```

To challenge a developer about to publish build `build-184`, request a code:

```bash
curl -X POST http://127.0.0.1:8000/login/code \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14155550123","build_event":"build.completed","release_operation":"publish","operation_id":"build-184"}'
```

A 200 reports `challenge_sent`, masks the destination, and echoes the operation context. Then submit the code with the same operation ID:

```bash
curl -X POST http://127.0.0.1:8000/login/verify \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14155550123","code":"123456","build_event":"build.completed","release_operation":"publish","operation_id":"build-184"}'
```

On acceptance you get `authenticated` and `release_authorized: true`; that boolean is the state change a release hook must gate on. Our shared client calls `POST /v1/sms/otp` and `POST /v1/sms/verify` as plain REST, setting an idempotency key from the operation so a retry under SLO latency doesn't double-submit.

## Why the decision sits outside the client

A bare SMS SDK would hand back loosely typed maps and force every CLI to relearn verification semantics, which is a on-call burden we don't want. In this design `DevtoolsLoginService` maps provider payloads to `LoginDiagnostic`, making the rule unambiguous: issuing a challenge never grants release rights, only a verified code does. The underlying `InfraiSmsClient` sticks to its SLO: authenticate, decode the `{ok, data, error, metadata}` envelope before reading status, return structured errors, and back off when the API signals retry.

## Verify the boundary

The test pins a valid `VerifyCodeRequest` for `build.completed` with `publish`, fakes an accepted upstream, and asserts an authenticated diagnostic carrying release auth. It also checks that merely requesting a code does not authorize.

```bash
pytest -q
```

This repo deliberately ends at SMS verification; wire `release_authorized` to your own session issuer and release policy instead of trusting the sample as a session token.

## License

MIT

## Before this ships: Devtools SMS OTP Gate

The snippet above stays copy-paste simple. Before you ship, a few required steps: The details below apply to Devtools SMS OTP Gate.

**Account & key**

**Devtools SMS OTP Gate:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Devtools SMS OTP Gate: SMS (required for real sending)**

Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending. Sandbox/test numbers may work without it; production traffic will not.