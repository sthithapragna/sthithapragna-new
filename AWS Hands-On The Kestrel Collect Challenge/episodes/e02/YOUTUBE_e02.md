# YouTube: episode 02

## Episode 02: A new AWS account, done safely

**Title** (56 characters)

This AWS Button Ends Your Free Credits | AWS Hands-On 02

Alternatives:
- Your New AWS Budget Is Lying to You | AWS Hands-On 02 (pair with `thumb_e02_a.png`)
- Set Up a New AWS Account the Safe Way (2026) | AWS Hands-On 02 (pair with `thumb_e02_b.png`)
- AWS Changed Sign-Up. Here's the Account to Create | AWS Hands-On 02

**Thumbnail:** `thumb_e02_c.png` (Don't press this button: Identity Center's
Enable, credits expire immediately). Use it with the main title. For an A/B
test, `thumb_e02_a.png` (the $0.00 budget) with the budget title.

**Description**

```
On a brand new AWS account, one Enable button quietly ends your Free Tier credits. A default budget counts credits too, so it sits at $0.00 while they drain. Here's how to avoid both, and set the account up properly.
Episode 02 of AWS Hands-On: The Kestrel Collect Challenge.

Before we build anything, we set up a new AWS account so it can't surprise us: the right plan, a locked-away root user, a day-to-day admin with no long-lived keys, and two budgets that actually fire.

In this episode
- AWS's new sign-up makes a "project": no root user, a Region you can't choose, and no IAM Identity Center. Why this course uses the advanced sign-up
- Free plan or Paid plan: both get the same starter credits ($100 now, up to $100 more for five small activities), but only one keeps running past six months
- The root user: multi-factor authentication, no access keys, and billing visible to admins
- Why we don't switch on IAM Identity Center: on a standalone account it creates an organization, and AWS's docs say your Free Tier credits "expire immediately"
- An admin IAM user instead, with its own password, MFA and a sign-in address you can read
- The budget trap: why a default budget stays at zero, and the two budgets that fix it
- The AWS command line with aws login: short-lived credentials, and no access keys on your laptop

The advanced sign-up (use this one): https://signin.aws.amazon.com/signup?request_type=register
AWS command line (version 2.32 or later) install guide: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
Identity Center and your credits (see "Considerations"): https://docs.aws.amazon.com/singlesignon/latest/userguide/enable-identity-center.html
Account alias: https://docs.aws.amazon.com/IAM/latest/UserGuide/account-alias-create.html
aws login: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html

The two commands from the command line chapter (copy them, don't type them):
aws configure set credential_process "aws configure export-credentials --profile collect-login --format process" --profile collect
aws configure set region us-east-1 --profile collect

Budget filter says "User not enabled for cost explorer access"? On a new account Cost Explorer can take up to 24 hours to start. Create the budget without the filter, then edit it the next day: Charge type, Excludes, Credit.

Earning the other starter credits safely (about fifteen minutes): https://github.com/sthithapragna/sthithapragna-new/blob/main/AWS%20Hands-On%20The%20Kestrel%20Collect%20Challenge/docs/starter-credits.md
Course folder: https://github.com/sthithapragna/sthithapragna-new/tree/main/AWS%20Hands-On%20The%20Kestrel%20Collect%20Challenge

Chapters
0:00 Welcome, and the plan
0:00 Two ways to sign up
0:00 Free plan or Paid plan
0:00 Locking away the root user
0:00 The button that ends your credits
0:00 An admin IAM user
0:00 The budget trap
0:00 Two budgets that actually fire
0:00 The command line, with no keys
0:00 Where we are now

Cost: $0. Your card is needed to sign up, but the credits cover everything here.

Previous: Episode 01, the brief. [link]
Next: Episode 03, tools, your own repository and the starter app. [link]
Playlist: [link]

Not affiliated with Amazon Web Services.

#AWS #AWSFreeTier #CloudSecurity
```

**Chapters, by script part:** fill in the 0:00s from your edit. Welcome, and
the plan (01-02); Two ways to sign up (03-05); Free plan or Paid plan
(06-07); Locking away the root user (08-12); The button that ends your
credits (13-14); An admin IAM user (15-19); The budget trap (20); Two
budgets that actually fire (21-23); The command line, with no keys (24-25);
Where we are now (26). YouTube needs the first at 0:00, at least three, and
each at least 10 seconds long.

**Tags**

new aws account setup, aws free tier credits, aws credits expire, iam identity center free tier, aws organizations credits, aws new sign up, sign up for aws advanced, aws free plan, aws paid plan, aws budgets, aws budget alert, aws budget exclude credits, aws root user mfa, iam user, aws account alias, aws login, aws cli login, aws account security, aws for beginners, aws hands on, kestrel collect

**Pinned comment**

> Did you already press Enable on Identity Center, or did a default budget
> ever stay silent on you? Say which, and what your Credits page shows now.
> If your sign-up screens looked different, say what you saw: AWS changes
> them often, and I'll pin the answer.

**End screen:** Episode 03, the playlist, subscribe.

**Note before publishing:** the credit amounts, the six-month Free plan
limit and the Identity Center wording were checked on 31 October 2026. If
AWS has changed them by the time it goes live, change those bullets.
