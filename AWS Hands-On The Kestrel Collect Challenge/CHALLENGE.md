# The Kestrel Collect Challenge

Build a real product on a public cloud, end to end, the way a small team
would ship it. This document says **what** to build and how it will be
checked. It never says how to build it, and it never names a cloud
provider's service, so the same challenge works on AWS, Azure and Google
Cloud.

> **Credit.** The shape of this challenge is borrowed from the
> [Cloud Resume Challenge](https://cloudresumechallenge.dev/), created by
> Forrest Brazeal and now run by ExamPro: a spec rather than a tutorial,
> one real thing to show, and every core service wired together. This
> challenge is not affiliated with it. The original is free and worth
> doing too.

## The brief

Kestrel Foods is a UK grocer. It is piloting **Kestrel Collect**, a
click-and-collect service, in six stores.

- **Customers** sign in, choose a store, book a one-hour collection slot,
  and pay when they collect.
- **Staff** see their own store's orders and move each one from picking,
  to ready, to collected.
- **Ask Kestrel**, an assistant, answers questions from Kestrel's own
  policy documents, and can book or cancel a slot for a customer after
  asking first.
- **Photo to basket** turns a photo of a handwritten shopping list into a
  draft basket of real products.
- **Feedback** after collection is sorted automatically, and urgent
  complaints reach the store the same day.

### Business rules

- Slots start on the hour from 08:00 to 19:00 UK time, every day: 12 a day.
- Customers can book today and up to 6 days ahead.
- Booking and cancelling close 1 hour before a slot starts.
- A customer can hold at most 2 active bookings.
- A Superstore slot holds 8 orders; a Local store slot holds 4.
- A reminder goes out 2 hours before the slot, unless the booking was made
  after that point or has been cancelled.
- An order not collected within 1 hour after its slot ends is a no-show.
- Times are always shown in UK time, including across clock changes.
- A hidden test store (`9999`) exists for automated tests. Customers never
  see it.

The course folder provides Kestrel's policy documents (`kb/`), its
product catalogue and a labelled feedback set (`data/`), and the starter
front end (`app/`).

## Rules

These apply at every level.

1. **It is live, on your own domain.** Screenshots don't count.
2. **Everything is code.** From Level 1 on, all infrastructure is defined
   in code. Anything you click together to learn, you import afterwards.
3. **No long-lived credentials**, on your computer or in your pipeline.
4. **The assistant answers from Kestrel's documents**, or says it doesn't
   know and offers a person.
5. **It costs less than $5 a month when idle**, not counting the domain.

## Level 1: Storefront

| # | Requirement | Checked by |
|---|---|---|
| 1.1 | The front end is served over HTTPS from a CDN, on your own domain, at both the apex and `www`. Plain HTTP redirects to HTTPS. | Grader |
| 1.2 | The storage behind the CDN is private. Requesting it directly is refused. | Grader |
| 1.3 | Deep links such as `/bookings` load the app, not an error page, and a request for a file that doesn't exist still fails. | Grader |
| 1.4 | Responses carry security headers: HSTS, `X-Content-Type-Options`, frame protection and a referrer policy. | Grader |
| 1.5 | A change you deploy is visible to customers within 5 minutes, without breaking cached pages. | Grader |
| 1.6 | All Level 1 infrastructure is in code, with state stored remotely and locked during changes. | Your write-up |
| 1.7 | Merging to the main branch deploys the front end. The pipeline holds no long-lived cloud credentials. | Your write-up |
| 1.8 | The cloud account is safe: the root user has MFA and no access keys, and budget alerts watch both real spending and credit use. | Your write-up |

## Level 2: Booking app

| # | Requirement | Checked by |
|---|---|---|
| 2.1 | Customers can sign up and sign in. Every API route except health and the store list rejects requests without a valid token. | Grader |
| 2.2 | Customers can see and change only their own bookings. Staff can see only their own store's orders. | Grader |
| 2.3 | Slot availability is correct in UK time for 7 days, including across a clock change. | Grader |
| 2.4 | A slot never takes more bookings than its capacity, even when 50 requests arrive at once for its last place. | Grader |
| 2.5 | A booking and the change to its slot's capacity succeed or fail together. | Grader |
| 2.6 | One client cannot flood the API: excessive requests are refused before they reach your code. | Grader |
| 2.7 | Browsers on other websites cannot call your API on a customer's behalf. | Grader |
| 2.8 | The back end is deployed by the pipeline, and failing tests stop the deploy. | Your write-up |

## Level 3: AI

| # | Requirement | Checked by |
|---|---|---|
| 3.1 | Ask Kestrel answers from Kestrel's documents and names the document it used. When the documents don't cover a question, it says so and offers a person. | Grader |
| 3.2 | When a document changes, answers reflect it within 15 minutes, with no manual step. | Grader |
| 3.3 | The assistant can list, book and cancel slots, only for the signed-in customer, only after the customer confirms, and never twice for one request. | Grader |
| 3.4 | No prompt can make the assistant reveal another customer's data or its own instructions. | Grader (attack set) |
| 3.5 | Harmful requests and personal data are filtered, without blocking ordinary grocery questions. | Grader (attack and false-positive sets) |
| 3.6 | Photo to basket only ever proposes products from the catalogue, and the customer confirms before anything is saved. | Grader |
| 3.7 | Feedback is labelled with a sentiment and a topic, and urgent complaints are flagged to the store. | Your write-up |
| 3.8 | An AI evaluation runs in the pipeline against a fixed test set, and a drop below your threshold fails the build. | Your write-up |
| 3.9 | Each customer has a daily AI spending limit, and the cost of each conversation is recorded. | Grader |

## Level 4: Production-ready

| # | Requirement | Checked by |
|---|---|---|
| 4.1 | Confirmations go through a queue. Failed messages are kept for inspection, and no customer gets the same email twice. | Grader |
| 4.2 | Email comes from your domain and passes SPF, DKIM and DMARC. | Grader |
| 4.3 | Reminders are scheduled per booking, and cancelled bookings get none. | Grader |
| 4.4 | Each order moves through booked, picking, ready and collected, or becomes a no-show on time. | Grader |
| 4.5 | Alarms reach you for errors, slow responses, stuck messages and AI spending. You have tested at least one. | Your write-up |
| 4.6 | End-to-end tests run against your live system without touching real customers or real slots. | Your write-up |
| 4.7 | Every role has only the permissions it uses, and a security review's findings are resolved. | Your write-up |
| 4.8 | You have handled one incident and written a blameless postmortem. | Your write-up |
| 4.9 | The whole system can be destroyed and rebuilt from code, in an empty account, in under an hour. | Your write-up |

## The write-up

Publish one article or README covering: an architecture diagram, three
decisions you made and what you traded off, one thing that broke and how
you found it, the incident postmortem, and what it costs to run.

## The grader

`grader/` checks a live deployment against the requirements marked
**Grader**, by level. It comes with the starter files, so it's in your own
repository. New checks arrive as the course goes on; fetch them with
`python grader/grade.py --update`, then run it:

    python grader/grade.py --url https://your-domain --level 1

At Level 1 it only sends ordinary GET requests. It needs nothing but
Python 3.10 or later. For 1.2, add `--storage-url` with your storage's own address.

It reports each requirement by number. Requirements marked
**Your write-up** are checked by reading your write-up and repository.

## Where the levels end

Each level is a finished thing to show an employer. Stop at any level, or
skip ahead: the course folder has a download for every level, so you can
deploy Level 2 and start straight at Level 3.
