# Kestrel Collect

The starter files for **AWS Hands-On: The Kestrel Collect Challenge**: build
a click-and-collect booking app with an AI assistant, end to end on AWS.

- **The challenge:** [CHALLENGE.md](CHALLENGE.md)
- **Earning the rest of your AWS starter credits:** [docs/starter-credits.md](docs/starter-credits.md)
- **The course folder** (downloads, and each episode's files): [AWS Hands-On The Kestrel Collect Challenge](https://github.com/sthithapragna/sthithapragna-new/tree/main/AWS%20Hands-On%20The%20Kestrel%20Collect%20Challenge)

## Start

1. On GitHub, create an empty public repository called `kestrel-collect`
   (no README, no .gitignore), and clone it.
2. Download [kestrel-collect-starter.zip](https://github.com/sthithapragna/sthithapragna-new/raw/main/AWS%20Hands-On%20The%20Kestrel%20Collect%20Challenge/downloads/kestrel-collect-starter.zip)
   and unzip it into that folder. Windows:
   `Expand-Archive $HOME\Downloads\kestrel-collect-starter.zip -DestinationPath .`
   Mac or Linux: `unzip ~/Downloads/kestrel-collect-starter.zip`
3. Commit and push it, then run the storefront on your computer:

       python tools/serve.py

   and open http://localhost:8000. Until the API exists it shows sample
   data, and the footer says so.

Episode 03 does all of this on camera.

## What's here

| Folder | Holds |
|---|---|
| `app/` | The storefront: plain HTML, CSS and JavaScript. No framework, no build step |
| `tools/` | Small helpers, such as the local server |
| `docs/` | Guides |
| `grader/` | Checks your live system against the challenge, from episode 08 |

The rest (`infra/`, `functions/`, `tests/`, `evals/`, `kb/`, `data/`)
arrives as the course reaches it.

## Following along, and joining part-way

- **Each episode's files** (the ones its narration says to copy in) appear,
  once the episode is out, in
  [`episodes/`](https://github.com/sthithapragna/sthithapragna-new/tree/main/AWS%20Hands-On%20The%20Kestrel%20Collect%20Challenge/episodes) in the course folder, one folder per episode.
- **Each episode's finished code**, once the episode is out, is a zip in
  [`downloads/`](https://github.com/sthithapragna/sthithapragna-new/tree/main/AWS%20Hands-On%20The%20Kestrel%20Collect%20Challenge/downloads): `kestrel-collect-e09-end.zip` is the whole
  repository as it stands at the end of episode 09. To join at episode 10,
  unzip that one into your empty repository instead of the starter.
- **Each level's end** is the zip of its last episode: Level 1 is
  `kestrel-collect-e12-end.zip`.
- **New grader checks** arrive as the course goes on:
  `python grader/grade.py --update`.

Not affiliated with Amazon Web Services.
