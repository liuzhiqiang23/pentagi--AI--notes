#!/usr/bin/env python3
"""Functional test suite for the fixed vulnapp — verifies all 9 vulnerability fixes."""
import http.client
import os
import sqlite3
import subprocess
import sys
import time
from urllib.parse import quote

TEST_DB = "/tmp/test_vulnapp_users.db"
TEST_PORT = 18080

# Read the source and patch DB and PORT for testing
with open("vulnapp_fixed.py", "r") as f:
    src = f.read()

src = src.replace('DB = "/var/lib/vulnapp/users.db"', f'DB = "{TEST_DB}"')
src = src.replace("PORT = 80", f"PORT = {TEST_PORT}")

patched_path = "/tmp/vulnapp_test_instance.py"
with open(patched_path, "w") as f:
    f.write(src)

proc = subprocess.Popen(
    [sys.executable, patched_path],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
time.sleep(1.5)

results = []

def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((name, status, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))

def http_get(path, port=TEST_PORT):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", "replace")
    headers = dict(resp.getheaders())
    conn.close()
    return resp.status, headers, body

def http_post(path, data, port=TEST_PORT):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", path, body=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", "replace")
    headers = dict(resp.getheaders())
    conn.close()
    return resp.status, headers, body

try:
    # ===== Fix 1: SQL Injection in /user?id= =====
    # 1a: Non-integer id (URL-encoded space)
    status, _, body = http_get("/user?id=" + quote("1 OR 1=1"))
    test("Fix1a: Non-integer id rejected (400)", status == 400, f"got {status}")

    # 1b: Valid integer works
    status, _, body = http_get("/user?id=1")
    test("Fix1b: Valid id returns 200", status == 200, f"got {status}")
    test("Fix1b: Admin user found", "admin" in body and "admin@target.lab" in body)

    # 1c: UNION-based injection
    status, _, body = http_get("/user?id=" + quote("1 UNION SELECT 1,2,3"))
    test("Fix1c: UNION injection blocked", status == 400, f"got {status}")

    # ===== Fix 2: SQL Injection in /login =====
    # 2a: Valid login
    status, _, body = http_post("/login", "u=admin&p=supersecret123")
    test("Fix2a: Valid login succeeds", "Welcome" in body and "admin" in body, f"status={status}")

    # 2b: SQL injection in login
    status, _, body = http_post("/login", "u=" + quote("admin' OR '1'='1") + "&p=anything")
    test("Fix2b: SQL injection login blocked", "Welcome" not in body, f"status={status}")

    # 2c: No username in failure message
    status, _, body = http_post("/login", "u=admin&p=wrongpass")
    test("Fix2c: No username in failure msg", "Login failed" in body and "Invalid username or password" in body)
    # Check that "admin" does not appear in the failure page (except in standard HTML)
    # The failure page should NOT contain the submitted username
    test("Fix2c: Username not leaked", "admin" not in body, f"'admin' in failure body: {'admin' in body}")

    # ===== Fix 3: OS Command Injection in /ping =====
    # 3a: Valid host works
    status, _, body = http_get("/ping?host=127.0.0.1")
    test("Fix3a: Valid ping host works", status == 200, f"got {status}")

    # 3b: Semicolon
    status, _, body = http_get("/ping?host=" + quote("127.0.0.1;id"))
    test("Fix3b: Semicolon injection blocked", status == 400, f"got {status}")

    # 3c: Pipe
    status, _, body = http_get("/ping?host=" + quote("127.0.0.1|id"))
    test("Fix3c: Pipe injection blocked", status == 400, f"got {status}")

    # 3d: Backticks
    status, _, body = http_get("/ping?host=" + quote("127.0.0.1`id`"))
    test("Fix3d: Backtick injection blocked", status == 400, f"got {status}")

    # 3e: $()
    status, _, body = http_get("/ping?host=" + quote("$(id)"))
    test("Fix3e: Dollar-paren injection blocked", status == 400, f"got {status}")

    # 3f: Ampersand
    status, _, body = http_get("/ping?host=" + quote("127.0.0.1&&id"))
    test("Fix3f: Ampersand injection blocked", status == 400, f"got {status}")

    # 3g: Space
    status, _, body = http_get("/ping?host=" + quote("127.0.0.1 id"))
    test("Fix3g: Space injection blocked", status == 400, f"got {status}")

    # ===== Fix 4: Reflected XSS in /search =====
    status, _, body = http_get("/search?name=" + quote("<script>alert(1)</script>"))
    test("Fix4a: XSS script tag escaped", "<script>alert(1)</script>" not in body)
    test("Fix4a: XSS escaped to entities", "&lt;script&gt;" in body, f"body snippet: {body[:200]}")

    status, _, body = http_get("/search?name=" + quote("<img src=x onerror=alert(1)>"))
    test("Fix4b: img onerror XSS escaped", "<img" not in body, f"raw img tag in body: {'<img' in body}")

    # ===== Fix 5: Password hashing =====
    conn = sqlite3.connect(TEST_DB)
    rows = conn.execute("SELECT user, pass FROM users").fetchall()
    conn.close()
    all_hashed = all(r[1].startswith("pbkdf2$") for r in rows)
    test("Fix5: Passwords are hashed (PBKDF2)", all_hashed, f"sample: {rows[0][1][:40]}...")
    no_plaintext = all("supersecret123" not in r[1] and "password1" not in r[1] and "qwerty456" not in r[1] for r in rows)
    test("Fix5: No plaintext passwords in DB", no_plaintext)

    # ===== Fix 6: Security headers =====
    status, headers, body = http_get("/")
    required_headers = {
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; object-src 'none'",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-Xss-Protection": "1; mode=block",
        "Referrer-Policy": "no-referrer",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    }
    for hname, expected_val in required_headers.items():
        actual = headers.get(hname, "")
        test(f"Fix6: Header {hname}", actual == expected_val, f"expected='{expected_val}', got='{actual}'")

    # ===== Fix 7: Generic error handling =====
    status, _, body = http_get("/nonexistent")
    test("Fix7: 404 page is clean", status == 404 and "Traceback" not in body)

    # ===== Fix 8: Login rate limiting =====
    # Make failed login attempts until rate limited
    rate_limited = False
    for i in range(8):
        status, _, body = http_post("/login", f"u=nonexistent{i}&p=wrongpass")
        if status == 429:
            rate_limited = True
            break
    test("Fix8: Rate limiting triggers 429", rate_limited, f"429 received: {rate_limited}")

    status, _, body = http_post("/login", "u=test&p=test")
    test("Fix8: 429 response has correct message", "429" in body and "Too Many Requests" in body)

    # ===== Fix 9: Drop privileges comment =====
    with open("vulnapp_fixed.py", "r") as f:
        full_src = f.read()
    has_drop_priv = "setuid" in full_src and "www-data" in full_src and "setgid" in full_src
    test("Fix9: Drop privileges instruction present", has_drop_priv)

    # ===== Summary =====
    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    print(f"Results: {passed} passed, {failed} failed, {len(results)} total")
    if failed:
        print("\nFailed tests:")
        for name, status, detail in results:
            if status == "FAIL":
                print(f"  - {name}: {detail}")
    print("=" * 60)

finally:
    proc.terminate()
    proc.wait()
    try:
        os.unlink(TEST_DB)
        os.unlink(patched_path)
    except:
        pass

sys.exit(0 if all(s == "PASS" for _, s, _ in results) else 1)
