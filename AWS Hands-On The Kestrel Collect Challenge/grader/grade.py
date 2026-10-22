#!/usr/bin/env python3
"""Grade a live Kestrel Collect deployment against CHALLENGE.md.

    python grader/grade.py --url https://your-domain --level 1
    python grader/grade.py --url https://your-domain --level 1 \\
        --storage-url https://your-bucket.s3.us-east-1.amazonaws.com/index.html

Level 1 only reads: ordinary GET requests, the same as a browser. Level 2
signs in as two customers you provide (GRADER_TOKEN_A and GRADER_TOKEN_B),
and books slots only at the test store, 9999.

New checks arrive as the course goes on. Get them with:

    python grader/grade.py --update
Standard library only, Python 3.10 or later. Exit code 0 when every check
passes, 1 when any fails, 2 when none fails but some were skipped.
"""
import argparse
import base64
import datetime
import http.client
import json
import os
import re
import secrets
import socket
import ssl
import sys
import threading
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

UPDATE_URL = ("https://raw.githubusercontent.com/sthithapragna/sthithapragna-new/main/"
              "AWS%20Hands-On%20The%20Kestrel%20Collect%20Challenge/grader/grade.py")
TIMEOUT = 15
USER_AGENT = "kestrel-collect-grader/1"
DEPLOY_LIMIT = 300          # requirement 1.5: visible within 5 minutes
HSTS_MIN = 15552000         # 180 days
CDN_HEADERS = ("x-cache", "x-amz-cf-id", "x-amz-cf-pop", "x-azure-ref",
               "cf-ray", "x-served-by", "cdn-cache-control")
SAFE_REFERRER = {"no-referrer", "same-origin", "strict-origin",
                 "strict-origin-when-cross-origin", "origin"}


class Response:
    def __init__(self, status, headers, body=b"", error=None):
        self.status = status
        self.headers = headers      # lower-case names
        self.body = body
        self.error = error

    def h(self, name):
        return self.headers.get(name.lower(), "")


def fetch(url, method="GET", headers=None, body=None):
    """One request, without following redirects. Never raises: errors go in .error."""
    parts = urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    try:
        if parts.scheme == "https":
            conn = http.client.HTTPSConnection(parts.hostname, parts.port or 443, timeout=TIMEOUT,
                                               context=ssl.create_default_context())
        else:
            conn = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=TIMEOUT)
        conn.request(method, path, body=body,
                     headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity",
                              "Accept": "*/*", **(headers or {})})
        res = conn.getresponse()
        headers = {}
        for k, v in res.getheaders():
            k = k.lower()
            headers[k] = f"{headers[k]}, {v}" if k in headers else v
        body = res.read(2_000_000)
        conn.close()
        return Response(res.status, headers, body)
    except ssl.SSLCertVerificationError as e:
        return Response(None, {}, error=f"certificate isn't valid: {e.verify_message}")
    except socket.gaierror:
        return Response(None, {}, error="the name doesn't resolve (no DNS record)")
    except (OSError, http.client.HTTPException) as e:
        return Response(None, {}, error=f"couldn't connect: {e}")


def show(res):
    return res.error or f"{res.status}"


def is_html(res):
    return res.status == 200 and "text/html" in res.h("content-type")


def is_redirect(res):
    return res.status in (301, 302, 307, 308)


class Result:
    def __init__(self, num, title):
        self.num, self.title = num, title
        self.fails, self.notes, self.skip = [], [], None

    def ok(self, msg):
        self.notes.append(msg)

    def fail(self, msg):
        self.fails.append(msg)

    @property
    def status(self):
        return "SKIP" if self.skip else "FAIL" if self.fails else "PASS"


# ---------------------------------------------------------------- 1.1

def check_1_1(site, args):
    r = Result("1.1", "HTTPS on your own domain, through a CDN, apex and www")
    apex = f"https://{site}/"
    res = fetch(apex)
    if not is_html(res):
        r.fail(f"{apex} answered {show(res)}, not a 200 web page")
        return r
    r.ok(f"{apex} answered 200 with a valid certificate")
    if any(res.h(h) for h in CDN_HEADERS) or res.h("via"):
        r.ok("served through a CDN (" + ", ".join(h for h in CDN_HEADERS + ("via",) if res.h(h)) + ")")
    else:
        r.fail("no sign of a CDN in the response headers: is the domain pointing straight at storage?")

    www = f"https://www.{site}/"
    res = fetch(www)
    if is_redirect(res) and res.h("location").startswith(f"https://{site}/"):
        r.ok(f"{www} redirects to the apex ({res.status})")
    elif is_html(res):
        r.ok(f"{www} serves the site too. Note: two addresses for one site break sign-in in Level 2")
    else:
        r.fail(f"{www} answered {show(res)}")

    for url in (f"http://{site}/", f"http://www.{site}/"):
        res = fetch(url)
        if is_redirect(res) and res.h("location").startswith("https://"):
            r.ok(f"{url} redirects to HTTPS ({res.status})")
        elif res.status == 200:
            r.fail(f"{url} serves the site over plain HTTP instead of redirecting")
        else:
            r.fail(f"{url} answered {show(res)}, not a redirect to HTTPS")
    return r


# ---------------------------------------------------------------- 1.2

def check_1_2(site, args):
    r = Result("1.2", "The storage behind the CDN is private")
    if not args.storage_url:
        r.skip = ("give your storage's own address with --storage-url, for example "
                  "https://collect-site-abc123.s3.us-east-1.amazonaws.com/index.html")
        return r
    urls = [args.storage_url]
    if urlsplit(args.storage_url).path in ("", "/"):
        urls.append(urljoin(args.storage_url, "/index.html"))
    for url in urls:
        res = fetch(url)
        if res.status == 200:
            r.fail(f"{url} answered 200: anyone can read your storage without the CDN")
        elif res.status in (401, 403, 404):
            r.ok(f"{url} refused the request ({res.status})")
        else:
            r.skip = f"couldn't check {url}: {show(res)}. Is the address right?"
    return r


# ---------------------------------------------------------------- 1.3

def check_1_3(site, args):
    r = Result("1.3", "Deep links load the app; missing files still fail")
    for path in ("/bookings", "/stores/0023"):
        res = fetch(f"https://{site}{path}")
        if is_html(res):
            r.ok(f"{path} loads the app (200)")
        else:
            r.fail(f"{path} answered {show(res)}: a customer following a link gets an error")
    token = secrets.token_hex(4)
    for path in (f"/js/does-not-exist-{token}.js", f"/does-not-exist-{token}.css"):
        res = fetch(f"https://{site}{path}")
        if res.status == 200:
            r.fail(f"{path} answered 200 for a file that doesn't exist: an error-page rule is "
                   "turning every error into the app, so broken deploys look healthy")
        elif res.status is None:
            r.fail(f"{path}: {res.error}")
        else:
            r.ok(f"{path} fails as it should ({res.status})")
    return r


# ---------------------------------------------------------------- 1.4

def max_age(value, name="max-age"):
    m = re.search(rf"(?:^|[,\s]){name}\s*=\s*\"?(\d+)", value, re.I)
    return int(m.group(1)) if m else None


def check_1_4(site, args):
    r = Result("1.4", "Security headers")
    res = fetch(f"https://{site}/")
    if res.status is None:
        r.fail(f"https://{site}/: {res.error}")
        return r
    hsts = res.h("strict-transport-security")
    age = max_age(hsts)
    if age is None:
        r.fail("no Strict-Transport-Security header")
    elif age < HSTS_MIN:
        r.fail(f"Strict-Transport-Security max-age is {age}: use at least {HSTS_MIN} (180 days)")
    else:
        r.ok(f"Strict-Transport-Security: {hsts}")
    if res.h("x-content-type-options").strip().lower() == "nosniff":
        r.ok("X-Content-Type-Options: nosniff")
    else:
        r.fail("no X-Content-Type-Options: nosniff")
    xfo = res.h("x-frame-options").strip().upper()
    csp = res.h("content-security-policy")
    if xfo in ("DENY", "SAMEORIGIN"):
        r.ok(f"X-Frame-Options: {xfo}")
    elif "frame-ancestors" in csp:
        r.ok("Content-Security-Policy sets frame-ancestors")
    else:
        r.fail("no frame protection (X-Frame-Options or a CSP frame-ancestors)")
    policies = [p.strip().lower() for p in res.h("referrer-policy").split(",") if p.strip()]
    if policies and policies[-1] in SAFE_REFERRER:
        r.ok(f"Referrer-Policy: {policies[-1]}")
    elif policies:
        r.fail(f"Referrer-Policy {policies[-1]} sends full addresses to other sites")
    else:
        r.fail("no Referrer-Policy header")
    return r


# ---------------------------------------------------------------- 1.5

def cache_times(cc):
    """(browser seconds, CDN seconds) a response may be reused, or None if left to guesswork."""
    cc = cc.lower()
    if "no-store" in cc:
        return 0, 0
    browser = 0 if "no-cache" in cc else max_age(cc)
    shared = max_age(cc, "s-maxage")
    cdn = shared if shared is not None else (0 if "no-cache" in cc else max_age(cc))
    return browser, cdn


VERSION_SEGMENT = re.compile(r"^(v?\d+([._-]\d+)*|[0-9a-f]{7,64}|\d{8,}([._-]\d+)*)$", re.I)
HASHED_NAME = re.compile(r"[.-](?=[A-Za-z0-9_]*\d)[A-Za-z0-9_]{8,}\.(m?js|css|svg|png|woff2?)$")


def versioned(path):
    *folders, name = path.split("/")
    return any(VERSION_SEGMENT.match(f) for f in folders if f) or bool(HASHED_NAME.search(name))


class Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.base, self.refs = None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "base" and a.get("href") and self.base is None:
            self.base = a["href"]
        elif tag == "script" and a.get("src"):
            self.refs.append(a["src"])
        elif tag == "link" and a.get("href") and set((a.get("rel") or "").lower().split()) & {
                "stylesheet", "icon", "modulepreload", "preload"}:
            self.refs.append(a["href"])


IMPORTS = re.compile(r"""(?:^|[;\s])(?:import|export)\b[^'";]*?\bfrom\s*["']([^"']+)["']"""
                     r"""|(?:^|[;\s])import\s*\(?\s*["']([^"']+)["']""", re.M)


def check_1_5(site, args):
    r = Result("1.5", f"A deploy reaches customers within {DEPLOY_LIMIT // 60} minutes, without breaking cached pages")
    page = f"https://{site}/"
    res = fetch(page)
    if not is_html(res):
        r.fail(f"{page} answered {show(res)}")
        return r
    cc = res.h("cache-control")
    if not cc:
        r.fail("the page has no Cache-Control header, so the CDN keeps it for its default time "
               "(24 hours on CloudFront) and browsers guess")
    else:
        browser, cdn = cache_times(cc)
        if browser is None:
            r.fail(f"the page's Cache-Control ({cc}) has no max-age, so browsers guess how long to keep it")
        elif browser + (cdn or 0) > DEPLOY_LIMIT:
            r.fail(f"the page can be reused for {browser + cdn} s (browser {browser} s + CDN {cdn} s), "
                   f"longer than {DEPLOY_LIMIT} s")
        else:
            r.ok(f"the page: Cache-Control {cc} (browser {browser} s + CDN {cdn} s)")
            held = res.h("age")
            if held.isdigit() and int(held) > max(cdn, 1) + 60:
                r.fail(f"but the CDN has held this copy for {held} s: its own settings override yours, "
                       "or an old copy is still cached")

    parser = Refs()
    parser.feed(res.body.decode("utf-8", "replace"))
    base = urljoin(page, parser.base or "/")
    queue = [urljoin(base, ref) for ref in parser.refs]
    seen, checked, unversioned, unset, too_long = set(), 0, [], [], []
    while queue and checked < 60:
        url = queue.pop(0)
        if url in seen or urlsplit(url).hostname != site:
            continue
        seen.add(url)
        checked += 1
        path = urlsplit(url).path
        res = fetch(url)
        if res.status != 200:
            r.fail(f"{path} is referenced by the page but answered {show(res)}: the page is broken right now")
            continue
        cc = res.h("cache-control")
        browser, cdn = cache_times(cc) if cc else (None, None)
        if browser is None:
            unset.append(path)
        elif browser + (cdn or 0) > DEPLOY_LIMIT and not versioned(path):
            too_long.append(path)
        elif not versioned(path):
            unversioned.append(path)
        if path.endswith((".js", ".mjs")):
            text = res.body.decode("utf-8", "replace")
            for m in IMPORTS.finditer(text):
                spec = m.group(1) or m.group(2)
                if spec.startswith((".", "/")):
                    queue.append(urljoin(url, spec))
    if unset:
        r.fail(f"{len(unset)} files the page loads have no max-age in Cache-Control, so the CDN and "
               f"browsers keep them as long as they like: {', '.join(unset)}")
    if too_long:
        r.fail(f"{len(too_long)} files are cached for more than {DEPLOY_LIMIT} s, but their addresses "
               f"never change, so a deploy can't replace them in time: {', '.join(too_long)}")
    if checked == 0:
        r.fail("the page references no scripts or stylesheets to check")
    elif not r.fails:
        r.ok(f"{checked} files the page loads all answer 200 with Cache-Control")
        if unversioned:
            r.ok(f"note: {len(unversioned)} files keep the same address across deploys, so a page "
                 "open during a deploy can mix old and new files")
        else:
            r.ok("every file's address changes with each release, so open pages keep working")
    return r


# ---------------------------------------------------------------- the levels

# The episode that adds each check. The course folder only publishes checks
# for episodes that are live; the rest show as "arrives with episode NN".
ARRIVES = {"2.1": 16, "2.2": 17, "2.4": 18, "2.5": 19, "2.3": 20}


def not_yet(num, title, episode):
    def check(site, args):
        r = Result(num, title)
        r.skip = f"this check arrives with episode {episode}"
        return r
    return check


LEVELS = {
    1: [check_1_1, check_1_2, check_1_3, check_1_4, check_1_5],
    2: [not_yet("2.1", "Every route except health and the store list needs sign-in", 16),
        not_yet("2.2", "Customers see only their own bookings; staff only their store", 17),
        not_yet("2.3", "Slots correct in UK time, across a clock change", 20),
        not_yet("2.4", "A slot never takes more bookings than its capacity", 18),
        not_yet("2.5", "A booking and its slot's count succeed or fail together", 19),
        not_yet("2.6", "Excess requests are refused before they reach your code", 22),
        not_yet("2.7", "Other websites can't call the API from a customer's browser", 22)],
}


def site_from(url):
    host = urlsplit(url if "://" in url else f"https://{url}").hostname or ""
    return host[4:] if host.startswith("www.") else host


def check_list(source):
    return sorted(set(re.findall(r"^def check_(\d)_(\d+)\(", source, re.M)), key=lambda x: (int(x[0]), int(x[1])))


def update():
    """Replace this file with the newest grader from the course folder."""
    here = os.path.abspath(__file__)
    res = fetch(UPDATE_URL)
    text = res.body.decode("utf-8", "replace") if res.status == 200 else ""
    if res.status != 200 or "def main(" not in text or "Kestrel Collect grader" not in text:
        print(f"Couldn't download the latest grader ({show(res)}). Yours is unchanged.")
        return 1
    with open(here, encoding="utf-8") as f:
        mine = f.read()
    if text.replace("\r\n", "\n") == mine.replace("\r\n", "\n"):
        print("The grader is already up to date.")
        return 0
    before, after = check_list(mine), check_list(text)
    if set(after) < set(before):
        print("Your grader already has every check the course folder has, and more. Keeping yours.")
        return 0
    with open(here, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    new = [f"{a}.{b}" for a, b in after if (a, b) not in before]
    print("Updated the grader." + (f" New checks: {', '.join(new)}." if new else "")
          + " Commit grader/grade.py so your pipeline uses it too.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Grade a live Kestrel Collect deployment.")
    p.add_argument("--update", action="store_true", help="download the newest grader from the course folder, then stop")
    p.add_argument("--url", help="your site, for example https://kestrelcollect.com")
    p.add_argument("--level", type=int, default=1, help="1 to 4; each level includes the ones before")
    p.add_argument("--storage-url", help="your storage's own address, for requirement 1.2")
    args = p.parse_args(argv)
    if args.update:
        return update()
    if not args.url:
        p.error("--url is required (or use --update)")
    if args.level not in LEVELS and args.level > max(LEVELS):
        print(f"Level {args.level} checks arrive with Level {args.level}. When they're out, "
              "python grader/grade.py --update fetches them.")
        return 2
    site = site_from(args.url)
    print(f"Kestrel Collect grader: Level {args.level}, https://{site}\n")
    results = []
    for level in sorted(k for k in LEVELS if k <= args.level):
        for check in LEVELS[level]:
            res = check(site, args)
            results.append(res)
            print(f"{res.status} {res.num} {res.title}")
            for msg in res.fails:
                print(f"     x {msg}")
            for msg in res.notes:
                print(f"       {msg}")
            if res.skip:
                print(f"     - {res.skip}")
            print()
    counts = {s: sum(r.status == s for r in results) for s in ("PASS", "FAIL", "SKIP")}
    print(f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    return 1 if counts["FAIL"] else 2 if counts["SKIP"] else 0


if __name__ == "__main__":
    sys.exit(main())
