# Git Smart HTTP Proxy

## Intent

SpeleoDB exposes Git smart-HTTP endpoints for project repositories while
keeping the backing GitLab deployment private. The proxy has two independent
security responsibilities:

- SpeleoDB authentication and project permissions decide whether the requesting
  user may fetch from or push to a project.
- Server-side GitLab credentials authenticate the already-authorized proxy
  request to the internal repository.

Client credentials must never be forwarded to GitLab. The proxied HTTP request
URL remains credential-free, and internal GitLab credentials must never appear
in client responses or logs. The proxy is a protocol boundary, not a
general-purpose HTTP forwarder. The existing repository recovery workflow has
separate Git remote credential ownership in `GitlabManager`.

## Request Boundary

The proxy constructs a credential-free GitLab repository URL and supplies the
internal OAuth token through Requests' explicit Basic Authentication support.
It forwards only headers needed by Git smart HTTP:

- `User-Agent`
- `Accept`
- `Content-Type`
- `Git-Protocol`
- `Cache-Control`
- `Pragma`

`Accept-Encoding` is forced to `identity` so streamed bytes do not require
proxy-side content decoding. Client authorization, cookies, host, and
edge/proxy headers are not forwarded.

Automatic redirects are disabled. A redirect can indicate an authentication,
canonical-host, or infrastructure problem; following it could turn that
problem into a successful HTML response that is invalid Git protocol data.

For a missing repository, the proxy preserves the existing one-time recovery
flow: on the first upstream `404`, SpeleoDB asks `GitlabManager` to create or
clone the project and retries the request once. A repeated `404` is an upstream
failure. Every response discarded during retry is closed before the next
request.

## Response Validation and Streaming

A successful upstream response must have HTTP status `200` and the content type
for the requested smart-HTTP phase:

| Request | Expected content type |
| --- | --- |
| `GET .../info/refs?service=<service>` | `application/x-<service>-advertisement` |
| `POST .../git-upload-pack` or `git-receive-pack` | `application/x-<service>-result` |

Content-type comparison is case-insensitive and ignores media-type parameters
such as `charset`. Redirects, non-`200` statuses, and unexpected content types
are rejected before streaming begins. This prevents HTML login/error documents
and other non-Git payloads from being mistaken for pkt-line data.

Once validated, a successful response is byte-transparent. The proxy yields
each non-empty upstream chunk unchanged; it does not decode, parse, reframe, or
rewrite pkt-lines. In particular, branding text inside a payload is not
modified. This preserves arbitrary chunk boundaries and binary data while
keeping memory use constant: repository responses are never buffered in full.

The upstream Requests response remains open for the lifetime of the Django
stream and is closed in a `finally` block on normal completion, read failure,
or client disconnect. A deferred read error is logged and re-raised. Because
headers may already have been sent when a stream fails, the proxy cannot safely
replace that partial response with a new HTTP status at that point.

## Failure and Observability Policy

An invalid upstream response or a failure before streaming returns:

- HTTP `502 Bad Gateway`
- `Content-Type: text/plain`
- `Cache-Control: no-store`
- The fixed message `SpeleoDB Git service is temporarily unavailable.`

The response intentionally contains no GitLab status text, exception details,
redirect target, or upstream body. Locally generated SpeleoDB errors, such as
invalid service selection, branch restrictions, authentication failures, and
permission failures, remain owned by their existing application behavior.

Safe diagnostic logs include only the SpeleoDB project ID, request method, Git
service, upstream status, normalized content type, and upstream request ID when
one is available. Logs must not include:

- GitLab tokens or credential-bearing URLs
- Authorization or cookie headers
- Client request bodies or upstream response bodies
- Redirect locations

This metadata distinguishes common failure classes—HTML login responses,
redirects, missing repositories, and upstream server failures—without exposing
credentials, Git payloads, or infrastructure details to clients or logs.

## Verification

Automated tests should mock GitLab and cover:

- Exact byte preservation for advertisements and result streams, including
  binary data, arbitrary chunk boundaries, multiple pkt-lines, and payloads
  containing `GitLab`.
- Rejection of HTML (including `<!DOCTYPE...GitLab`), redirects, unexpected
  content types, and upstream `4xx`/`5xx` responses with a sanitized `502`.
- Correct phase-specific content-type validation and protocol response headers.
- Header allowlisting, separate internal authentication, credential-free URLs,
  and disabled redirects.
- First-`404` recovery followed by success, repeated-`404` failure, and response
  closure on every branch.
- Connection timeouts, request failures, deferred stream failures, and public
  endpoint authentication and permission enforcement.

Disconnect coverage must close Django's test-client WSGI iterator after partial
consumption, rather than calling `response.close()` directly. The iterator owns
the test client's `request_finished` signal isolation. Bypassing it can close a
`TestCase` transaction's PostgreSQL connection; SQLite's in-memory backend
ignores that close and can mask the test-lifecycle bug.

Run the focused backend tests and static checks, followed by the full suite:

```bash
uv run pytest -q speleodb/git_proxy/tests.py
uv run ruff check speleodb/git_proxy
uv run mypy speleodb/git_proxy
uv run pytest
```

Operational verification should run `git ls-remote` through SpeleoDB and a
credential-safe direct `info/refs` diagnostic from the deployed environment.
A request must produce either valid Git smart-HTTP output or the controlled
`502`; it must never expose HTML as a successful Git response. Use the safe log
metadata to check the configured GitLab host and group and the internal token's
scope and expiry.

## Performance Characteristics

Successful bodies are streamed in bounded chunks, so memory use is independent
of repository size. Response validation uses status and headers only and does
not scan or buffer the body. The sole additional upstream request is the
existing retry after an initial repository `404`; all other failures terminate
without retry.
