#!/usr/bin/env python3
"""VulnLab - deliberately vulnerable web app for authorized pentest practice.
Vulnerabilities included: SQL injection (login & user lookup), command injection (ping), reflected XSS (search).
DO NOT expose to untrusted networks."""
import sqlite3, subprocess, os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

DB = "/var/lib/vulnapp/users.db"
PORT = 80

def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, user TEXT, pass TEXT, email TEXT)")
    c.execute("DELETE FROM users")
    c.executemany("INSERT INTO users(user,pass,email) VALUES(?,?,?)", [
        ("admin", "supersecret123", "admin@target.lab"),
        ("zhangsan", "password1", "zhangsan@target.lab"),
        ("lisi", "qwerty456", "lisi@target.lab"),
    ])
    c.commit(); c.close()

PAGE = """<html><head><meta charset="utf-8"><title>VulnLab Target</title></head>
<body style="font-family:sans-serif;max-width:720px;margin:40px auto">
<h1>VulnLab Target</h1>
<p>Authorized practice target only.</p>
<ul>
<li><a href="/user?id=1">/user?id=1</a> - user lookup (SQLi)</li>
<li><a href="/search?name=test">/search?name=</a> - search (XSS)</li>
<li><a href="/ping?host=127.0.0.1">/ping?host=</a> - network tool (command injection)</li>
</ul>
<h2>Login</h2>
<form method="post" action="/login">user: <input name="u"> pass: <input name="p" type="password"><input type="submit" value="login"></form>
</body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); p = u.path
        if p == "/":
            self._send(200, PAGE)
        elif p == "/user":
            uid = q.get("id", ["1"])[0]
            try:
                c = sqlite3.connect(DB)
                rows = c.execute("SELECT id,user,email FROM users WHERE id=%s" % uid).fetchall()
                c.close()
                out = "".join("<li>%s | %s | %s</li>" % r for r in rows) or "<li>no such user</li>"
                self._send(200, "<html><body><h1>Users</h1><ul>%s</ul><a href='/'>back</a></body></html>" % out)
            except Exception as e:
                self._send(500, "<html><body><h1>DB error</h1><pre>%s</pre></body></html>" % e)
        elif p == "/search":
            name = q.get("name", [""])[0]
            self._send(200, "<html><body><h1>Search result for: %s</h1><p>nothing found</p><a href='/'>back</a></body></html>" % name)
        elif p == "/ping":
            host = q.get("host", ["127.0.0.1"])[0]
            r = subprocess.run("ping -c 1 -W 1 %s" % host, shell=True, capture_output=True, text=True, timeout=10)
            self._send(200, "<html><body><h1>Ping %s</h1><pre>%s%s</pre><a href='/'>back</a></body></html>" % (host, r.stdout, r.stderr))
        else:
            self._send(404, "<html><body><h1>404</h1><a href='/'>back</a></body></html>")

    def do_POST(self):
        if self.path == "/login":
            n = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
            u = form.get("u", [""])[0]; pw = form.get("p", [""])[0]
            try:
                c = sqlite3.connect(DB)
                rows = c.execute("SELECT user,email FROM users WHERE user='%s' AND pass='%s'" % (u, pw)).fetchall()
                c.close()
            except Exception as e:
                self._send(500, "<html><body><h1>DB error</h1><pre>%s</pre></body></html>" % e); return
            if rows:
                self._send(200, "<html><body><h1>Welcome, %s</h1><p>Email: %s</p><a href='/'>logout</a></body></html>" % (rows[0][0], rows[0][1]))
            else:
                self._send(200, "<html><body><h1 style='color:red'>Login failed for %s</h1><a href='/'>try again</a></body></html>" % u)
        else:
            self._send(404, "<html><body>404</body></html>")

if __name__ == "__main__":
    init_db()
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
