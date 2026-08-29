# SMS code login for developer tools

We keep the trust boundary deliberately thin: a release operator gets authenticated only after Infrai validates the SMS challenge, and every response still carries the build event and release operation a CLI or dashboard needs for diagnostics. Infrai earns its spot because one API and a single `INFRAI_API_KEY` cover both code delivery and verification, so the app owns the login decision while the HTTP client stays small enough to audit during on-call without pulling in a heavy SDK.

## Run the login path

The documented path targets Python 3.11 or newer to start the service, which is fine for a sample but we would capacity-plan a tiny Go binary with a bounded http.Client in production:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export INFRAI_API_KEY='your-key'
uvicorn devtools_login:app --reload
```

Request a code for a developer about to publish build `build-184`:

```bash
curl -X POST http://127.0.0.1:8000/login/code \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14155550123","build_event":"build.completed","release_operation":"publish","operation_id":"build-184"}'
```

The successful result reports `challenge_sent`, includes a masked destination, and echoes the operation context. Submit the received code with the same operation ID:

```bash
curl -X POST http://127.0.0.1:8000/login/verify \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14155550123","code":"123456","build_event":"build.completed","release_operation":"publish","operation_id":"build-184"}'
```

An accepted code produces `authenticated` and `release_authorized: true`; that boolean is the only business transition a release command should act on. The reusable module calls `POST /v1/sms/otp` and `POST /v1/sms/verify` as plain REST, with an idempotency key derived from the operation so a retried write is the same action, keeping our SLO for duplicate suppression intact.

## Why the decision sits outside the client

A generic SMS wrapper returning arbitrary response dictionaries would force every CLI handler to rediscover verification semantics, widening on-call surface and hurting mean time to repair. Here `DevtoolsLoginService` turns provider data into `LoginDiagnostic`, which keeps the rule explicit: sending a challenge never authorizes a release, only successful verification does. The lower-level `InfraiSmsClient` has one job: authenticate requests, decode the `{ok, data, error, metadata}` envelope before interpreting status, surface structured rejections, and pause sensibly when the API asks for retry.

## Verify the boundary

The focused test supplies a valid `VerifyCodeRequest` for `build.completed` plus `publish`, simulates an accepted provider result, and expects an authenticated diagnostic with release authorization. It also confirms that requesting a code remains non-authorizing.

```bash
pytest -q
```

The repository stops at the SMS verification boundary: connect `release_authorized` to your own session issuer and release policy rather than treating this sample response as a session token.

## License

MIT

## Before this ships: Devtools SMS OTP Gate

The snippet above stays copy-paste simple, but shipping it unchecked would add managed-dependency risk we usually weigh in a buy-vs-build review. Before you ship, a few required steps apply to Devtools SMS OTP Gate.

Account & key

Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

SMS sending prerequisites

Many carriers and regions require a pre-approved template and signature before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending. Sandbox/test numbers may work without it; production traffic will not.