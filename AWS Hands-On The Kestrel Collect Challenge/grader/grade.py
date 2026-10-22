#!/usr/bin/env python3
"""Grade a live Kestrel Collect deployment against CHALLENGE.md.

    python grader/grade.py --url https://your-domain --level 1
    python grader/grade.py --url https://your-domain --level 1 \\
        --storage-url https://your-bucket.s3.us-east-1.amazonaws.com/index.html

Level 1 only reads: ordinary GET requests, the same as a browser. Level 2
signs in as two customers you provide (GRADER_TOKEN_A and GRADER_TOKEN_B),
and books slots only at the test store, 9999.
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


# ---------------------------------------------------------------- 2.1

OPEN_ROUTES = [("GET", "/api/health"), ("GET", "/api/stores")]
SAMPLE_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
SIGNED_IN_ROUTES = [
    ("GET", "/api/stores/0023/slots?date={today}"),
    ("GET", "/api/bookings"),
    ("POST", "/api/bookings"),
    ("GET", f"/api/bookings/{SAMPLE_ID}"),
    ("DELETE", f"/api/bookings/{SAMPLE_ID}"),
    ("GET", "/api/staff/stores/0023/bookings?date={today}"),
    ("POST", f"/api/staff/bookings/{SAMPLE_ID}/status"),
    ("POST", "/api/assistant/messages"),
    ("POST", "/api/uploads"),
    ("POST", "/api/basket/from-photo"),
    ("POST", "/api/feedback"),
]
FAKE_TOKEN = ("Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
              "eyJzdWIiOiJncmFkZXIiLCJleHAiOjk5OTk5OTk5OTl9.c2lnbmF0dXJl")


def check_2_1(site, args):
    r = Result("2.1", "Every route except health and the store list needs sign-in")
    for method, path in OPEN_ROUTES:
        res = fetch(f"https://{site}{path}", method)
        if res.status == 200:
            r.ok(f"{method} {path} is open (200)")
        else:
            r.fail(f"{method} {path} should be open to anyone but answered {show(res)}")
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    missing = []
    for method, path in SIGNED_IN_ROUTES:
        path = path.format(today=today)
        body = b"{}" if method in ("POST", "PUT", "PATCH") else None
        headers = {"Content-Type": "application/json"} if body else None
        res = fetch(f"https://{site}{path}", method, headers, body)
        if res.status == 404:
            missing.append(f"{method} {path.split('?')[0]}")
            continue
        if res.status not in (401, 403):
            r.fail(f"{method} {path} answered {show(res)} with no token: anyone can call it")
            continue
        forged = fetch(f"https://{site}{path}", method, {**(headers or {}), "Authorization": FAKE_TOKEN}, body)
        if forged.status not in (401, 403):
            r.fail(f"{method} {path} accepted a forged token ({show(forged)})")
        else:
            r.ok(f"{method} {path.split('?')[0]} refuses no token and a forged one ({res.status}, {forged.status})")
    if missing:
        r.ok(f"not built yet (404): {', '.join(missing)}")
    return r


# ---------------------------------------------------------------- 2.2

def claims(token):
    """Read a JWT's payload. No signature check: the API does that; we only need the groups."""
    try:
        part = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except (IndexError, ValueError):
        return {}


def staff_of(token):
    return {g.removeprefix("staff-") for g in claims(token).get("cognito:groups", []) if g.startswith("staff-")}


def api(site, token, method, path, body=None):
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    res = fetch(f"https://{site}{path}", method, headers, data)
    try:
        res.json = json.loads(res.body or b"null")
    except ValueError:
        res.json = None
    return res


def check_2_2(site, args):
    r = Result("2.2", "Customers see only their own bookings; staff only their store")
    a, b = os.environ.get("GRADER_TOKEN_A"), os.environ.get("GRADER_TOKEN_B")
    if not (a and b):
        r.skip = ("set GRADER_TOKEN_A and GRADER_TOKEN_B to two customers' access tokens: sign in "
                  "as each, then copy \"access\" from kestrel.tokens in the browser's session storage")
        return r
    mine = api(site, a, "GET", "/api/bookings")
    if mine.status != 200 or not isinstance(mine.json, list):
        r.fail(f"customer A's GET /api/bookings answered {show(mine)}: is the token current (an hour)?")
        return r
    if not mine.json:
        r.skip = "customer A has no bookings: book any slot as A, then run this again"
        return r
    b_stores = staff_of(b)
    # Prefer a booking at a store where B isn't staff: there B must be refused.
    target = next((x for x in mine.json if x["store_id"] not in b_stores), mine.json[0])
    booking, store = target["booking_id"], target["store_id"]

    if store in b_stores:
        r.ok(f"customer B works at store {store}, so may see A's booking there: not tested")
    else:
        res = api(site, b, "GET", f"/api/bookings/{booking}")
        if res.status in (403, 404):
            r.ok(f"B asking for A's booking gets {res.status}")
        else:
            r.fail(f"B asked for A's booking {booking} and got {show(res)}: anyone signed in can read it")
        res = api(site, b, "POST", f"/api/staff/bookings/{booking}/status", {"status": "PICKING"})
        if res.status in (403, 404):
            r.ok(f"B moving A's order on gets {res.status}")
        elif res.status == 200:
            r.fail("B changed the status of A's booking")
        else:
            r.ok(f"B moving A's order on gets {res.status} (route not built yet?)" if res.status == 404 else
                 f"B moving A's order on gets {res.status}")
        listed = api(site, b, "GET", "/api/bookings")
        if listed.status == 200 and any(x.get("booking_id") == booking for x in listed.json or []):
            r.fail("A's booking appears in B's list of bookings")
        else:
            r.ok("A's booking isn't in B's list")

    day = target.get("store_day", "#").split("#")[1] or target["slot_start"][:10]
    a_stores = staff_of(a)
    for who, token, stores in (("A", a, a_stores), ("B", b, b_stores)):
        other = next((s for s in ("9999", "0001", "0023") if s not in stores), None)
        res = api(site, token, "GET", f"/api/staff/stores/{other}/bookings?date={day}")
        if res.status in (403, 404):
            r.ok(f"{who} asking for store {other}'s orders gets {res.status}")
        else:
            r.fail(f"{who} doesn't work at store {other} but read its orders ({show(res)})")
    return r


# ---------------------------------------------------------------- 2.3

UK_STORE = "0023"


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def last_sunday(year, month):
    end = datetime.date(year, month, 31)
    return end - datetime.timedelta(days=(end.weekday() + 1) % 7)


def uk_offset(instant):
    """How far UK time is ahead of UTC at an instant: one hour from 01:00 UTC on the
    last Sunday in March to 01:00 UTC on the last Sunday in October. Written out,
    because Python on Windows has no time zone database without an extra package."""
    utc = datetime.timezone.utc
    one = datetime.time(1, tzinfo=utc)
    starts = datetime.datetime.combine(last_sunday(instant.year, 3), one)
    ends = datetime.datetime.combine(last_sunday(instant.year, 10), one)
    return datetime.timedelta(hours=1 if starts <= instant < ends else 0)


def uk_time(slot_start):
    t = datetime.datetime.strptime(slot_start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return t + uk_offset(t)


def slots_wrong(day, slots):
    """What's wrong with one day's slots, in words, or None."""
    try:
        times = [uk_time(x["slot_start"]) for x in slots]
    except (KeyError, TypeError, ValueError):
        return f"{day:%a %d %b}: the slots don't look like 2026-10-24T08:00:00Z"
    expected = [f"{day} {hour:02}:00" for hour in range(8, 20)]
    got = [t.strftime("%Y-%m-%d %H:%M") for t in times]
    if got == expected:
        return None
    if not got:
        return f"{day:%a %d %b}: no slots"
    return (f"{day:%a %d %b}: {len(got)} slots from {times[0]:%H:%M} to {times[-1]:%H:%M} UK time"
            f"{'' if times[0].date() == day else ' on ' + format(times[0], '%a %d %b')}, "
            "not 12 from 08:00 to 19:00")


def check_2_3(site, args):
    r = Result("2.3", "Slots correct in UK time, across a clock change")
    a = os.environ.get("GRADER_TOKEN_A")
    if not a:
        r.skip = "set GRADER_TOKEN_A (see 2.2): slots need a signed-in customer"
        return r
    now = utc_now()
    today = (now + uk_offset(now)).date()
    days = [today + datetime.timedelta(days=d) for d in range(7)]

    by_day = {}
    for day in days:
        res = api(site, a, "GET", f"/api/stores/{UK_STORE}/slots?date={day}")
        if res.status != 200 or not isinstance(res.json, list):
            r.fail(f"GET /api/stores/{UK_STORE}/slots?date={day} answered {show(res)}")
            continue
        by_day[day] = [x.get("slot_start") for x in res.json]
        wrong = slots_wrong(day, res.json)
        if wrong:
            r.fail(f"one day at a time: {wrong}")
    if by_day and not r.fails:
        r.ok(f"one day at a time: 12 slots from 08:00 to 19:00 UK time on each of the next 7 days")

    week = api(site, a, "GET", f"/api/stores/{UK_STORE}/week")
    if week.status == 404:
        r.ok(f"GET /api/stores/{UK_STORE}/week: not built yet (404)")
    elif week.status != 200 or not isinstance(week.json, list):
        r.fail(f"GET /api/stores/{UK_STORE}/week answered {show(week)}")
    else:
        bad = 0
        for entry in week.json:
            try:
                day = datetime.date.fromisoformat(entry["date"])
                wrong = slots_wrong(day, entry["slots"])
            except (KeyError, TypeError, ValueError):
                wrong = f"an entry doesn't look like {{\"date\": \"{today}\", \"slots\": [...]}}"
            if wrong:
                bad += 1
                r.fail(f"the week: {wrong}")
            elif by_day.get(day) and [x["slot_start"] for x in entry["slots"]] != by_day[day]:
                bad += 1
                r.fail(f"the week: {day:%a %d %b} doesn't match the same day's slots asked for alone")
        if not bad:
            r.ok(f"the week: {len(week.json)} days, each 08:00 to 19:00 UK time, matching the days asked for alone")

    noon = lambda d: datetime.datetime.combine(d, datetime.time(12, tzinfo=datetime.timezone.utc))
    changes = [d for d in days[1:] if uk_offset(noon(d)) != uk_offset(noon(d - datetime.timedelta(days=1)))]
    if changes:
        r.ok(f"these 7 days include the clock change on {changes[0]:%A %d %B %Y}")
    else:
        year = today.year
        upcoming = sorted(d for y in (year, year + 1) for d in (last_sunday(y, 3), last_sunday(y, 10)) if d > today)
        r.ok(f"no clock change in the next 7 days, so this run can't test one; the next is "
             f"{upcoming[0]:%A %d %B %Y}. Your unit tests must cover it (episode 20)")
    return r


# ---------------------------------------------------------------- 2.4

TEST_STORE = "9999"
RACE = 50
ACTIVE = {"BOOKED", "PICKING", "READY"}
NEXT_STATUS = {"BOOKED": "PICKING", "PICKING": "READY", "READY": "COLLECTED"}


def collect(site, staff, booking):
    """As test-store staff, move a test booking on to COLLECTED, so it stops
    counting towards customer A's two bookings on the go."""
    status = booking["status"]
    while status in NEXT_STATUS:
        res = api(site, staff, "POST", f"/api/staff/bookings/{booking['booking_id']}/status",
                  {"status": NEXT_STATUS[status]})
        if res.status != 200:
            return f"moving {booking['booking_id']} on from {status} answered {show(res)}"
        status = NEXT_STATUS[status]
    return None


def slot_orders(site, staff, slot_start):
    res = api(site, staff, "GET", f"/api/staff/stores/{TEST_STORE}/bookings?date={slot_start[:10]}")
    if res.status != 200 or not isinstance(res.json, list):
        return None
    return [x for x in res.json if x.get("slot_start") == slot_start]


def empty_test_slot(site, customer, staff):
    """The soonest test-store slot, still open for booking, that nobody has booked."""
    now = datetime.datetime.now(datetime.timezone.utc)
    soonest = (now + datetime.timedelta(minutes=75)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for ahead in range(8):     # UTC days; the API refuses the ones outside its window
        day = (now + datetime.timedelta(days=ahead)).date().isoformat()
        res = api(site, customer, "GET", f"/api/stores/{TEST_STORE}/slots?date={day}")
        if res.status != 200 or not isinstance(res.json, list):
            continue
        for slot in res.json:
            if slot["slot_start"] >= soonest and slot["booked"] == 0 and slot["capacity"] >= 1:
                if slot_orders(site, staff, slot["slot_start"]) == []:
                    return slot
    return None


def test_store_setup(site, r):
    """Customer A, test-store staff B and an empty test-store slot, or None (with r told why)."""
    a, b = os.environ.get("GRADER_TOKEN_A"), os.environ.get("GRADER_TOKEN_B")
    if not (a and b):
        r.skip = "set GRADER_TOKEN_A and GRADER_TOKEN_B (see 2.2)"
        return None
    if TEST_STORE not in staff_of(b):
        r.skip = (f"customer B must be staff at the test store: in Cognito add B to staff-{TEST_STORE}, "
                  "sign in as B again, and copy B's new access token")
        return None
    mine = api(site, a, "GET", "/api/bookings")
    if mine.status != 200 or not isinstance(mine.json, list):
        r.fail(f"customer A's GET /api/bookings answered {show(mine)}: is the token current (an hour)?")
        return None
    if sum(x.get("status") in ACTIVE for x in mine.json) >= 2:
        r.skip = "customer A already has 2 bookings on the go: use an account with at most one"
        return None
    slot = empty_test_slot(site, a, b)
    if not slot:
        r.skip = f"no empty slot at store {TEST_STORE} still open for booking (or B can't list its orders)"
        return None
    return a, b, slot


def burst(count, request):
    """Send count requests, all released at the same moment. Returns the responses."""
    gate = threading.Barrier(count)
    answers = [None] * count

    def one(i):
        try:
            gate.wait(timeout=30)
        except threading.BrokenBarrierError:
            pass
        answers[i] = request()

    threads = [threading.Thread(target=one, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return answers


def tally(answers):
    """"1 x 201, 49 x 409 (that slot is full)" """
    kinds = {}
    for x in answers:
        why = x.json.get("error") if isinstance(x.json, dict) else None
        key = f"{x.status} ({why})" if why else str(x.status or x.error)
        kinds[key] = kinds.get(key, 0) + 1
    return ", ".join(f"{n} x {k}" for k, n in sorted(kinds.items()))


def slot_count(site, token, start):
    res = api(site, token, "GET", f"/api/stores/{TEST_STORE}/slots?date={start[:10]}")
    if res.status != 200 or not isinstance(res.json, list):
        return None
    return next((x["booked"] for x in res.json if x.get("slot_start") == start), None)


def check_2_4(site, args):
    r = Result("2.4", "A slot never takes more bookings than its capacity")
    setup = test_store_setup(site, r)
    if not setup:
        return r
    a, b, slot = setup
    start, capacity = slot["slot_start"], slot["capacity"]
    body = {"store_id": TEST_STORE, "slot_start": start}

    # Fill all but one place, one booking at a time, so the race is for the last place.
    for _ in range(capacity - 1):
        res = api(site, a, "POST", "/api/bookings", body)
        if res.status != 201:
            r.fail(f"booking store {TEST_STORE}, {start} one at a time answered {show(res)}")
            return r
        problem = collect(site, b, res.json)
        if problem:
            r.fail(problem)
            return r

    # Now RACE requests for the last place, all released at the same moment.
    answers = burst(RACE, lambda: api(site, a, "POST", "/api/bookings", body))
    won = [x for x in answers if x.status == 201]
    r.ok(f"{RACE} requests at once for the last place at store {TEST_STORE}, {start}: {tally(answers)}")

    orders = [x for x in slot_orders(site, b, start) or [] if x.get("status") != "CANCELLED"]
    counted = slot_count(site, a, start)
    if len(won) > 1:
        r.fail(f"{len(won)} of them were booked: the last place went {len(won)} times")
    elif not won:
        r.fail("none of them was booked: exactly one should get the last place")
    else:
        r.ok("exactly one was booked")
    if len(orders) > capacity:
        r.fail(f"the slot holds {len(orders)} bookings, but its capacity is {capacity}")
    if counted is not None and counted != len(orders):
        r.fail(f"the slot's count says {counted} booked, but it holds {len(orders)} bookings")

    # Tidy up: every test booking in that slot becomes COLLECTED.
    for booking in orders:
        problem = collect(site, b, booking)
        if problem:
            r.ok(f"tidying up: {problem}")
            break
    else:
        r.ok(f"tidied up: {len(orders)} test bookings in that slot marked collected")
    return r


# ---------------------------------------------------------------- 2.5

CANCELS = 20


def check_2_5(site, args):
    r = Result("2.5", "A booking and its slot's count succeed or fail together")
    setup = test_store_setup(site, r)
    if not setup:
        return r
    a, b, slot = setup
    start = slot["slot_start"]
    made = api(site, a, "POST", "/api/bookings", {"store_id": TEST_STORE, "slot_start": start})
    if made.status != 201:
        r.fail(f"booking store {TEST_STORE}, {start} answered {show(made)}")
        return r
    booking = made.json["booking_id"]
    before = slot_count(site, a, start)

    # The same customer cancels the same booking CANCELS times at once: a
    # double tap, a retry, a second tab. One cancel must win, and only once.
    path = f"/api/bookings/{booking}/cancel"
    answers = burst(CANCELS, lambda: api(site, a, "POST", path))
    if all(x.status == 404 for x in answers):
        r.skip = f"POST /api/bookings/{{id}}/cancel answered 404: cancelling isn't built yet (episode 19)"
        collect(site, b, made.json)
        return r
    r.ok(f"{CANCELS} cancels at once for one booking at store {TEST_STORE}, {start}: {tally(answers)}")

    after = api(site, a, "GET", f"/api/bookings/{booking}")
    cancelled = after.status == 200 and isinstance(after.json, dict) and after.json.get("status") == "CANCELLED"
    live = [x for x in slot_orders(site, b, start) or [] if x.get("status") != "CANCELLED"]
    counted = slot_count(site, a, start)
    wins = sum(x.status == 200 for x in answers)
    if wins > 1:
        r.fail(f"{wins} cancels succeeded for one booking")
    if counted != len(live):
        r.fail(f"the slot's count went from {before} to {counted}, but it holds {len(live)} "
               f"bookings that aren't cancelled: some cancels gave the place back and then failed")
    elif cancelled and wins == 1:
        r.ok(f"exactly one cancel succeeded, and the slot's count went from {before} to {counted}")
    elif not cancelled:
        r.ok("no cancel got through, and nothing changed: the booking and the count still agree")

    # Tidy up, and check that a cancel on its own works.
    if not cancelled:
        again = api(site, a, "POST", path)
        if again.status == 200:
            r.ok("a single cancel afterwards worked")
        else:
            r.fail(f"a single cancel afterwards answered {show(again)}")
            collect(site, b, made.json)
    return r


def not_yet(num, title, episode):
    def check(site, args):
        r = Result(num, title)
        r.skip = f"this check arrives with episode {episode}"
        return r
    return check


LEVELS = {
    1: [check_1_1, check_1_2, check_1_3, check_1_4, check_1_5],
    2: [check_2_1,
        check_2_2,
        check_2_3,
        check_2_4,
        check_2_5,
        not_yet("2.6", "Excess requests are refused before they reach your code", 22),
        not_yet("2.7", "Other websites can't call the API from a customer's browser", 22)],
}


def site_from(url):
    host = urlsplit(url if "://" in url else f"https://{url}").hostname or ""
    return host[4:] if host.startswith("www.") else host


def main(argv=None):
    p = argparse.ArgumentParser(description="Grade a live Kestrel Collect deployment.")
    p.add_argument("--url", required=True, help="your site, for example https://kestrelcollect.com")
    p.add_argument("--level", type=int, default=1, help="1 to 4; each level includes the ones before")
    p.add_argument("--storage-url", help="your storage's own address, for requirement 1.2")
    args = p.parse_args(argv)
    if args.level not in LEVELS and args.level > max(LEVELS):
        print(f"Level {args.level} checks arrive with Level {args.level}. Update the course "
              "repository with git pull.")
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
