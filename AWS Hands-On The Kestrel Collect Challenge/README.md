# Kestrel Collect

The course repository for **The Kestrel Collect Challenge**: build a
click-and-collect booking app with an AI assistant, end to end on a public
cloud. This edition uses AWS.

- **The challenge:** [CHALLENGE.md](CHALLENGE.md)
- **Earning the rest of your AWS starter credits:** [docs/starter-credits.md](docs/starter-credits.md)

## Start

Click **Use this template** to make your own copy, clone it, then run the
storefront on your computer:

    python tools/serve.py

and open http://localhost:8000. Until the API exists it shows sample data,
and the footer says so.

## What's here

| Folder | Holds |
|---|---|
| `app/` | The storefront: plain HTML, CSS and JavaScript. No framework, no build step |
| `tools/` | Small helpers, such as the local server |
| `docs/` | Guides |

The rest (`infra/`, `functions/`, `tests/`, `evals/`, `grader/`, `kb/`,
`data/`) arrives as the course reaches it.

## Joining part-way

This branch is always the starting point. Each episode's finished code is
on the `solutions` branch, tagged `eNN-end` (for example `e09-end`), and each
level is tagged `level-1` to `level-4`.
