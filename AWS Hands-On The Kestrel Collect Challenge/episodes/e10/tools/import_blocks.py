#!/usr/bin/env python3
"""Write infra/imports.tf: Terraform import blocks for what we clicked.

    python tools/import_blocks.py

Asks AWS (through the AWS CLI) for the ID of each resource built in the
console in episodes 04 to 07, and writes one import block per resource.
It only reads. Apply the plan once, then delete infra/imports.tf: the
certificate's ARN holds your account ID, so the file is never committed.

Reads domain_name from infra/terraform.tfvars and AWS_PROFILE from .env.
"""
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INFRA = ROOT / "infra"
FUNCTION = "collect-spa-routing"


def load_env():
    env = dict(os.environ)
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                env.setdefault(key.strip(), value.strip().strip('"'))
    return env


def aws(*args, env=None):
    exe = shutil.which("aws")
    if not exe:
        sys.exit("The AWS CLI isn't on your PATH.")
    res = subprocess.run([exe, *args, "--output", "json"], env=env, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"aws {' '.join(args)} failed:\n{res.stderr.strip()}\n"
                 "If it's a sign-in error, run: aws login --profile collect-login")
    return json.loads(res.stdout or "{}")


def tfvar(name):
    text = (INFRA / "terraform.tfvars").read_text(encoding="utf-8")
    m = re.search(rf'^\s*{name}\s*=\s*"([^"]*)"', text, re.M)
    return m.group(1) if m else None


def find(domain, call):
    names = [domain, f"www.{domain}"]

    dists = call("cloudfront", "list-distributions").get("DistributionList", {}).get("Items", [])
    dist = next((d for d in dists if domain in d.get("Aliases", {}).get("Items", [])), None)
    if not dist:
        sys.exit(f"No CloudFront distribution has {domain} as an alternate domain name (episode 07).")
    s3 = [o for o in dist["Origins"]["Items"] if ".s3." in o["DomainName"]]
    if len(s3) != 1:
        sys.exit("Expected exactly one S3 origin on the distribution.")
    origin = s3[0]
    bucket = origin["DomainName"].split(".s3.")[0]
    cert = dist["ViewerCertificate"].get("ACMCertificateArn")
    web_acl = dist.get("WebACLId", "")

    zones = call("route53", "list-hosted-zones-by-name", "--dns-name", domain)["HostedZones"]
    zone = next((z for z in zones if z["Name"] == f"{domain}."), None)
    if not zone:
        sys.exit(f"No hosted zone named {domain} (episode 06).")
    zone_id = zone["Id"].split("/")[-1]

    records = call("route53", "list-resource-record-sets", "--hosted-zone-id", zone_id)["ResourceRecordSets"]
    present = {(r["Name"].rstrip("."), r["Type"]) for r in records}
    validation = {}
    for r in records:
        first, _, rest = r["Name"].rstrip(".").partition(".")
        if r["Type"] == "CNAME" and first.startswith("_") and rest in names:
            validation[rest] = r["Name"].rstrip(".")
    missing = [f"{n} {t}" for n in names for t in ("A", "AAAA") if (n, t) not in present]
    missing += [f"validation CNAME for {n}" for n in names if n not in validation]
    if missing:
        sys.exit("Missing in Route 53: " + ", ".join(missing))

    blocks = [
        ("aws_s3_bucket.site", bucket),
        ("aws_s3_bucket_public_access_block.site", bucket),
        ("aws_s3_bucket_policy.site", bucket),
        ("aws_cloudfront_origin_access_control.site", origin["OriginAccessControlId"]),
        ("aws_cloudfront_function.routing", FUNCTION),
        ("aws_cloudfront_distribution.storefront", dist["Id"]),
        ("aws_route53_zone.main", zone_id),
        ("aws_acm_certificate.site", cert),
    ]
    for n in names:
        blocks.append((f'aws_route53_record.validation["{n}"]', f"{zone_id}_{validation[n]}_CNAME"))
    for n in names:
        blocks.append((f'aws_route53_record.site_a["{n}"]', f"{zone_id}_{n}_A"))
        blocks.append((f'aws_route53_record.site_aaaa["{n}"]', f"{zone_id}_{n}_AAAA"))
    return blocks, bucket, web_acl


def render(blocks):
    out = [f"# Written by tools/import_blocks.py on {datetime.date.today()}.",
           "# Apply it once, then delete it. It holds your account ID, so it is never committed.", ""]
    for to, id_ in blocks:
        out += ["import {", f"  to = {to}", f'  id = "{id_}"', "}", ""]
    return "\n".join(out)


def main():
    domain = tfvar("domain_name")
    if not domain:
        sys.exit("Set domain_name in infra/terraform.tfvars first.")
    env = load_env()
    blocks, bucket, web_acl = find(domain, lambda *a: aws(*a, env=env))
    (INFRA / "imports.tf").write_text(render(blocks), encoding="utf-8")
    print(f"Wrote infra/imports.tf: {len(blocks)} import blocks.\n")

    suffix = bucket.removeprefix("collect-site-")
    acl_name = web_acl.split("/webacl/")[1].split("/")[0] if "/webacl/" in web_acl else ""
    print("Check infra/terraform.tfvars against what AWS says:")
    for name, real in (("site_suffix", suffix), ("web_acl_name", acl_name)):
        have = tfvar(name)
        mark = "ok" if have == real else f"CHANGE IT (it says \"{have}\")"
        print(f'  {name} = "{real}"   {mark}')


if __name__ == "__main__":
    main()
