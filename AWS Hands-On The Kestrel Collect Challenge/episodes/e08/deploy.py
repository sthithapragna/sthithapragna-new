#!/usr/bin/env python3
"""Deploy the storefront as a release that never changes.

    python tools/deploy.py              # deploy the current commit
    python tools/deploy.py --dry-run    # print the commands, run nothing

1. Every file except index.html goes to releases/<commit>/, cached for a
   year. A new commit gets a new folder, so its files never go stale.
2. Then index.html goes to the top of the bucket, pointing at that folder,
   cached for 60 seconds by the CDN and revalidated by every browser.

Pages already open keep loading their own release, which is still there.
Never run `aws s3 sync --delete` on the bucket: it deletes the releases.

Reads COLLECT_SUFFIX (and AWS_PROFILE) from the environment or from .env.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "app"
ASSETS_CACHE = "public, max-age=31536000, immutable"
PAGE_CACHE = "public, max-age=0, s-maxage=60"
BASE_TAG = '<base href="/">'


def load_env():
    env = dict(os.environ)
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                env.setdefault(key.strip(), value.strip().strip('"'))
    return env


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def run(cmd, env, dry_run):
    print("+ " + " ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
    if dry_run:
        return
    try:
        subprocess.run([shutil.which("aws"), *cmd[1:]], env=env, check=True)
    except subprocess.CalledProcessError:
        sys.exit("Stopped: that command failed, so nothing after it ran. "
                 "If it was a sign-in error, run: aws login --profile collect-login")


def main():
    p = argparse.ArgumentParser(description="Deploy the storefront as a release.")
    p.add_argument("--bucket", help="default: collect-site-<COLLECT_SUFFIX>")
    p.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")
    args = p.parse_args()

    env = load_env()
    bucket = args.bucket or (env.get("COLLECT_SUFFIX") and f"collect-site-{env['COLLECT_SUFFIX']}")
    if not bucket:
        sys.exit("No bucket: set COLLECT_SUFFIX in .env, or pass --bucket.")
    if not shutil.which("aws"):
        sys.exit("The AWS CLI isn't on your PATH.")
    if git("status", "--porcelain", "--", "app"):
        sys.exit("app/ has uncommitted changes. Commit them first: a release is named after its commit.")
    release = git("rev-parse", "--short=12", "HEAD")

    page = (APP / "index.html").read_text(encoding="utf-8")
    if page.count(BASE_TAG) != 1:
        sys.exit(f"app/index.html needs exactly one {BASE_TAG} line.")
    page = page.replace(BASE_TAG, f'<base href="/releases/{release}/">')

    print(f"Release {release} to s3://{bucket}\n")
    run(["aws", "s3", "cp", str(APP), f"s3://{bucket}/releases/{release}/", "--recursive",
         "--exclude", "index.html", "--cache-control", ASSETS_CACHE], env, args.dry_run)
    with tempfile.TemporaryDirectory() as tmp:
        index = pathlib.Path(tmp) / "index.html"
        index.write_text(page, encoding="utf-8")
        run(["aws", "s3", "cp", str(index), f"s3://{bucket}/index.html",
             "--content-type", "text/html; charset=utf-8", "--cache-control", PAGE_CACHE],
            env, args.dry_run)
    print(f"\nDone. Customers get release {release} within a minute.")


if __name__ == "__main__":
    main()
