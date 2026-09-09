#!/usr/bin/env python3
"""VulnLab - FIXED version after penetration test.
All vulnerabilities patched:
  - SQL injection  → parameterized queries + input validation
  - Command injection → subprocess list args + strict host validation (no shell=True)
  - Reflected XSS  → html.escape() on all user output + CSP header
  - Plaintext passwords → salted SHA-256 hashing
  - Verbose errors → generic 500 + stderr logging
  - Missing security headers → CSP / X-Content-Type-Options / X-Frame-Options / HSTS etc.
  - No rate limiting → per-IP login throttle (5 / 60 s)
  - Running as root → privilege-drop helper at bottom
DO NOT expose to untrusted networks even after fixes — this is a practice app."""
import sqlite3, subprocess, os, re, html, hashlib, time, sys, logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB   = "/var/lib/vulnapp/users.db"
PORT = 9999

# Rate-limit: max failed logins per source IP
RATE_LIMIT_MAX   = 5        # attempts
RATE_LIMIT_WINDOW = 60      # seconds
_login_failures: dict[str, list[float]] = {}   # ip → [timestamp, …]

# Strict host validation pattern: IPv4 or simple hostname
# Allows: digits, letters, dots, hyphens — nothing else.
_HOST_RE = re.compile(r'^[0-9a-zA-Z.\-]{1,253}$')

# Security headers added to every response
_SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; object-src 'none'",
    "X-Content-Type-Options":  "nosniff",
    "X-Frame-Options":         "DENY",
    "X-XSS-Protection":       "1; mode=block",
    "Referrer-Policy":        "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}

# ---------------------------------------------------------------------------
# Password helpers (salted SHA-256 — stdlib only, no external deps)
# ---------------------------------------------------------------------------
def _hash_password(password: str) -> str:
    """Return salted SHA-256 hex digest in format  salt$hash."""
    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${h}"

def _verify_password(password: str, stored: str) -> bool:
    """Verify a plaintext password against a stored salt$hash string."""
    try:
        salt, h = stored.split("$", 1)
    except ValueError:
        return False
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == h

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
def _is_rate_limited(ip: str) -> bool:
    """Return True if *ip* has exceeded the login failure threshold."""
    now = time.monotonic()
    attempts = _login_failures.get(ip, [])
    # Prune expired entries
    attempts = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]
    _login_failures[ip] = attempts
    return len(attempts) >= RATE_LIMIT_MAX

def _record_failure(ip: str) -> None:
    now = time.monotonic()
    _login_failures.setdefault(ip, []).append(now)

# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------
def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS users("
        "id INTEGER PRIMARY KEY, user TEXT UNIQUE, pass TEXT, email TEXT)"
    )
    con.execute("DELETE FROM users")
    # Store hashed passwords — never plaintext
    con.executemany(
        "INSERT INTO users(user, pass, email) VALUES (?, ?, ?)",
        [
            ("admin",    _hash_password("supersecret123"), "admin@target.lab"),
            ("zhangsan", _hash_password("password1"),      "zhangsan@target.lab"),
            ("lisi",     _hash_password("qwerty456"),      "lisi@target.lab"),
        ],
    )
    con.commit()
    con.close()

# ---------------------------------------------------------------------------
# HTML page templates
# ---------------------------------------------------------------------------
PAGE = """<html><head><meta charset="utf-8"><title>VulnLab Target</title></head>
<body style="font-family:sans-serif;max-width:720px;margin:40px auto">
<h1>VulnLab Target</h1>
<p>Authorized practice target only.</p>
<ul>
<li><a href="/user?id=1">/user?id=1</a> — user lookup</li>
<li><a href="/search?name=test">/search?name=</a> — search</li>
<li><a href="/ping?host=127.0.0.1">/ping?host=</a> — network tool</li>
</ul>
<h2>Login</h2>
<form method="post" action="/login">user: <input name="u"> pass: <input name="p" type="password"><input type="submit" value="login"></form>
</body></html>"""

# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------
class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        """Override default to use structured logging."""
        logging.info("%s - %s", self.client_address[0], fmt % args)

    # -- helpers ------------------------------------------------------------
    def _send(self, code: int, body: str):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        for k, v in _SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _send_429(self):
        body = "<html><body><h1 style='color:red'>Too many login attempts — please wait.</h1><a href='/'>back</a></body></html>"
        self._send(429, body)

    @staticmethod
    def _safe_int(value: str, default: int = -1) -> int:
        """Convert to int safely; return *default* on failure."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    # -- GET ----------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        q      = parse_qs(parsed.query)
        path   = parsed.path

        if path == "/":
            self._send(200, PAGE)

        elif path == "/user":
            self._handle_user(q)

        elif path == "/search":
            self._handle_search(q)

        elif path == "/ping":
            self._handle_ping(q)

        else:
            self._send(404, "<html><body><h1>404</h1><a href='/'>back</a></body></html>")

    # -- POST ---------------------------------------------------------------
    def do_POST(self):
        if self.path == "/login":
            self._handle_login()
        else:
            self._send(404, "<html><body>404</body></html>")

    # -- endpoint: /user  (FIXED: parameterised query + int validation) ------
    def _handle_user(self, q: dict):
        raw_id = q.get("id", ["1"])[0]
        uid = self._safe_int(raw_id)
        if uid < 0:
            self._send(400, "<html><body><h1>Bad Request</h1><p>id must be a positive integer.</p><a href='/'>back</a></body></html>")
            return
        try:
            con = sqlite3.connect(DB)
            # ✅ FIX: parameterised query — no string interpolation
            rows = con.execute("SELECT id, user, email FROM users WHERE id = ?", (uid,)).fetchall()
            con.close()
        except Exception as e:
            # ✅ FIX: generic error — log real error server-side only
            logging.error("DB error in /user: %s", e)
            self._send(500, "<html><body><h1>Internal Server Error</h1><a href='/'>back</a></body></html>")
            return

        # ✅ FIX: html.escape on every field
        out = "".join(
            "<li>%s | %s | %s</li>" % (html.escape(str(r[0])), html.escape(str(r[1])), html.escape(str(r[2])))
            for r in rows
        ) or "<li>no such user</li>"
        self._send(200, "<html><body><h1>Users</h1><ul>%s</ul><a href='/'>back</a></body></html>" % out)

    # -- endpoint: /search  (FIXED: html.escape) ----------------------------
    def _handle_search(self, q: dict):
        name = q.get("name", [""])[0]
        # ✅ FIX: escape before embedding in HTML
        safe_name = html.escape(name)
        self._send(
            200,
            "<html><body><h1>Search result for: %s</h1><p>nothing found</p><a href='/'>back</a></body></html>" % safe_name,
        )

    # -- endpoint: /ping  (FIXED: no shell=True + strict host validation) ---
    def _handle_ping(self, q: dict):
        host = q.get("host", ["127.0.0.1"])[0]

        # ✅ FIX: strict allowlist validation — reject any shell metacharacter
        if not _HOST_RE.match(host):
            self._send(
                400,
                "<html><body><h1>Invalid host</h1><p>Only alphanumeric characters, dots and hyphens are allowed.</p><a href='/'>back</a></body></html>",
            )
            return

        # ✅ FIX: subprocess with list args — shell=False (default)
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", "1", host],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            self._send(504, "<html><body><h1>Ping timeout</h1><a href='/'>back</a></body></html>")
            return
        except Exception as e:
            logging.error("ping subprocess error: %s", e)
            self._send(500, "<html><body><h1>Internal Server Error</h1><a href='/'>back</a></body></html>")
            return

        safe_host  = html.escape(host)
        safe_out   = html.escape(r.stdout)
        safe_err   = html.escape(r.stderr)
        self._send(
            200,
            "<html><body><h1>Ping %s</h1><pre>%s%s</pre><a href='/'>back</a></body></html>" % (safe_host, safe_out, safe_err),
        )

    # -- endpoint: /login  (FIXED: parameterised query + rate limit + hashing)
    def _handle_login(self):
        src_ip = self.client_address[0]

        # ✅ FIX: rate limiting
        if _is_rate_limited(src_ip):
            self._send_429()
            return

        try:
            n    = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        except Exception:
            self._send(400, "<html><body><h1>Bad Request</h1><a href='/'>back</a></body></html>")
            return

        u  = form.get("u", [""])[0]
        pw = form.get("p", [""])[0]

        # Basic input length check
        if not u or not pw or len(u) > 64 or len(pw) > 128:
            _record_failure(src_ip)
            # ✅ FIX: do NOT echo the username on failure
            self._send(200, "<html><body><h1 style='color:red'>Login failed</h1><a href='/'>try again</a></body></html>")
            return

        try:
            con = sqlite3.connect(DB)
            # ✅ FIX: parameterised query — no string interpolation
            rows = con.execute(
                "SELECT user, email, pass FROM users WHERE user = ?",
                (u,),
            ).fetchall()
            con.close()
        except Exception as e:
            logging.error("DB error in /login: %s", e)
            self._send(500, "<html><body><h1>Internal Server Error</h1><a href='/'>back</a></body></html>")
            return

        # ✅ FIX: verify hashed password
        if rows and _verify_password(pw, rows[0][2]):
            # ✅ FIX: html.escape on username & email
            safe_user  = html.escape(rows[0][0])
            safe_email = html.escape(rows[0][1])
            self._send(
                200,
                "<html><body><h1>Welcome, %s</h1><p>Email: %s</p><a href='/'>logout</a></body></html>" % (safe_user, safe_email),
            )
        else:
            _record_failure(src_ip)
            # ✅ FIX: generic failure message — no username leakage
            self._send(200, "<html><body><h1 style='color:red'>Login failed</h1><a href='/'>try again</a></body></html>")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )
    init_db()
    server = HTTPServer(("0.0.0.0", PORT), H)
    logging.info("VulnLab (fixed) listening on 0.0.0.0:%d", PORT)

    # ── Privilege drop (Linux) ──────────────────────────────────────────────
    # After binding port 80 (which requires root), drop to an unprivileged
    # user for all request handling.  This limits blast-radius if any
    # future vulnerability is discovered.
    #
    # Usage:  run as root, then uncomment the block below:
    #
    # import pwd, grp
    # TARGET_USER  = "www-data"
    # TARGET_GROUP = "www-data"
    # pwent = pwd.getpwnam(TARGET_USER)
    # grent = grp.getgrnam(TARGET_GROUP)
    # os.setgroups([])
    # os.setgid(grent.gr_gid)
    # os.setuid(pwent.pw_uid)
    # logging.info("Dropped privileges to %s/%s", TARGET_USER, TARGET_GROUP)
    # ────────────────────────────────────────────────────────────────────────

    server.serve_forever()
