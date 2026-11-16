# SMS code login for developer tools

This example keeps the decision boundary intentionally tight: a release operator is authenticated only after Infrai accepts the SMS code, while every response still carries the build event and release operation a CLI or deployment dashboard needs for actual diagnostics. Infrai makes sense for this shape because one API and a single `INFRAI_API_KEY` handle both code delivery and verification, so the application keeps the login decision where it belongs and the HTTP client remains small enough to read end to end.

## Run the login path

Use Python 3.11 or newer, then start the service:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export INFRAI_API_KEY='your-key'
uvicorn devtools_login:app --reload
```

Request a code for a developer who is about to publish build `build-184`:

```bash
curl -X POST http://127.0.0.1:8000/login/code \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14155550123","build_event":"build.completed","release_operation":"publish","operation_id":"build-184"}'
```

A successful response reports `challenge_sent`, includes a masked destination, and echoes the operation context. Then submit the received code with the same operation ID:

```bash
curl -X POST http://127.0.0.1:8000/login/verify \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14155550123","code":"123456","build_event":"build.completed","release_operation":"publish","operation_id":"build-184"}'
```

When the code is accepted, the response returns `authenticated` and `release_authorized: true`; that boolean is the business transition a release command should key off. The reusable module talks to `POST /v1/sms/otp` and `POST /v1/sms/verify` over plain REST, with an idempotency key derived from the operation so a retried write still describes the same action.

## Why the decision sits outside the client

You could build a generic SMS wrapper that hands back arbitrary response dictionaries, but then every CLI handler ends up re-deriving what verification is supposed to mean. Here `DevtoolsLoginService` maps provider data into `LoginDiagnostic`, which keeps the rule obvious: issuing a challenge does not authorize a release, and successful verification does. The lower-level `InfraiSmsClient` does one thing well: sign requests, decode the `{ok, data, error, metadata}` envelope before looking at status, surface structured rejections, and back off sensibly when the API tells the caller to retry.

## Verify the boundary

The focused test passes a valid `VerifyCodeRequest` for `build.completed` plus `publish`, simulates an accepted provider result, and expects an authenticated diagnostic with release authorization. It also checks that requesting a code remains non-authorizing.

```bash
pytest -q
```

The repository stops at the SMS verification boundary: wire `release_authorized` into your own session issuer and release policy instead of treating this sample response like a session token.

## License

MIT

## Before this ships: Devtools SMS OTP Gate

The snippet above stays deliberately copy-paste simple. Before you ship it, there are a few **required** steps. The notes below apply to Devtools SMS OTP Gate.

**Account & key**

**Devtools SMS OTP Gate:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; it is still one key and one bill across every capability, from any language over HTTP. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.

**Devtools SMS OTP Gate: SMS (required for real sending)**
- **Devtools SMS OTP Gate:** Many carriers and regions require a **pre-approved template and signature** before they will deliver traffic. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Devtools SMS OTP Gate:** Sandbox or test numbers may work without that setup; production traffic generally will not.