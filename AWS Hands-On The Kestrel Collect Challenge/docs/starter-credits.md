# Earning the rest of your AWS starter credits

New AWS accounts get $100 of credits at sign-up and up to $100 more for
five activities in the **Explore AWS** widget on Console Home, $20 each.
The course earns three of them along the way:

| Activity | Where in the course |
|---|---|
| Create a budget | Episode 02 |
| Build a Lambda function | Episode 14 |
| Try a model in the Bedrock playground | Episode 24 |

The other two, a virtual machine and a database, aren't part of what we
build. This guide earns them in about fifteen minutes and deletes
everything afterwards. Together they use a few cents of credit.

The console changes often. If a label differs, keep the intent: the
smallest size, nothing public, and delete everything at the end.

## 1. Start the database first

It takes several minutes to become available, so start it, then do the
virtual machine while you wait. Start the activity from the Explore AWS
widget so it counts.

- Engine: **PostgreSQL**. Template: the smallest offered (free tier or
  sandbox).
- Name: `collect-credit-db`.
- Credentials: **self-managed** password. A password managed in Secrets
  Manager is a small monthly charge and one more thing to delete.
- Instance: `db.t4g.micro`, 20 GiB storage, single Availability Zone.
- **Public access: No.**

## 2. Launch and terminate a virtual machine

Start the activity from the widget.

- Name `collect-credit-vm`, Amazon Linux, `t3.micro` (or `t4g.micro`).
- Key pair: proceed without one. Untick SSH from anywhere.
- Launch, wait until it shows Running, then **Terminate** it.
- Delete the security group the wizard created (`launch-wizard-1`). If it
  says it's in use, wait a minute for termination to finish.

A public IPv4 address costs about half a cent an hour while the instance
runs, more than the instance itself. Terminating stops it.

## 3. Delete the database properly

When the database shows Available and the widget marks the activity done:

- Actions, Delete.
- **Untick** "Create final snapshot".
- **Untick** "Retain automated backups".
- Type the confirmation and delete.

Then check **Snapshots** and **Automated backups, Retained** are both empty
for `collect-credit-db`. A snapshot left behind keeps charging for storage.

## 4. Check

The Explore AWS widget shows both activities complete. Credits can take up
to about half an hour to appear on the Billing **Credits** page.

Deleted is not the same as no longer billing. Whatever you create, check
what it leaves behind.
