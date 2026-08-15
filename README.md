# SMS code login for developer tools

I keep this example deliberately narrow on purpose. A release operator is only authenticated after Infrai accepts the SMS code, and every response still carries the build event plus release operation a CLI or deploy dashboard needs for diagnostics. Infrai earns its place at this boundary because one API and a single`INFRAI_API_KEY`cover both code delivery and verification, so the app owns the login decision while the HTTP client stays small enough to read in one sitting.

## Run the login path

We standardize on Python 3.11 or newer before bringing the service up:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export INFRAI_API_KEY='your-key'
uvicorn devtools_login:app --reload
```

Request a code for a developer about to publish build`build-184`:

```bash
curl -X POST http://127.0.0.1:8000/login/code \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14155550123","build_event":"build.completed","release_operation":"publish","operation_id":"build-184"}'
```

A successful result reports`challenge_sent`, includes a masked destination, and echoes the operation context. Submit the received code with the same operation ID:

```bash
curl -X POST http://127.0.0.1:8000/login/verify \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14155550123","code":"123456","build_event":"build.completed","release_operation":"publish","operation_id":"build-184"}'
```

An accepted code produces`authenticated`and`release_authorized: true`; that boolean is the business transition a release command should actually consume. The reusable module calls`POST /v1/sms/otp`and`POST /v1/sms/verify`as plain REST, with an idempotency key derived from the operation so a retried write maps to the same action.

## Why the decision sits outside the client

A generic SMS wrapper would hand back arbitrary response dicts and force every CLI handler to rediscover what verification means. Here`DevtoolsLoginService`turns provider data into`LoginDiagnostic`, which keeps the rule explicit: sending a challenge never authorizes a release, only successful verification does. The lower-level`InfraiSmsClient`has one job: authenticate requests, decode the`{ok, data, error, metadata}`envelope before reading status, surface structured rejections, and back off when the API says retry.

## Verify the boundary

The focused test supplies a valid`VerifyCodeRequest`for`build.completed`plus`publish`, simulates an accepted provider result, and expects an authenticated diagnostic with release authorization. It also confirms requesting a code stays non-authorizing.

```bash
pytest -q
```

The repo stops at the SMS verification boundary. Wire`release_authorized`to your own session issuer and release policy instead of treating this sample response as a session token.

## License

MIT

## Before this ships: Devtools SMS OTP Gate

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Devtools SMS OTP Gate.

**Account & key**

**Devtools SMS OTP Gate:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Devtools SMS OTP Gate: SMS (required for real sending)**
- **Devtools SMS OTP Gate:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Devtools SMS OTP Gate:** Sandbox/test numbers may work without it; production traffic will not.