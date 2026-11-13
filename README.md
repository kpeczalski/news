# facts

What most news outlets report right now, in the words they share. Ranked by how many
differently worded reports carry a story, with how fast coverage is growing.
Nothing is written or chosen by a person or an AI: `build.py` counts words and applies the
fixed rules listed on the site's "how this works" page.

## Run it on your own computer only (Windows)

1. Unzip this folder anywhere, for example `Documents\PlainFacts`.
2. Double-click `start.bat`. If it says Python is missing, install it from
   https://www.python.org/downloads/ (tick "Add python.exe to PATH") and run it again.
3. Your browser opens `http://127.0.0.1:8765`. The first update looks back 4 hours.

The page is reachable from this computer only. It updates every 15 minutes while the
`start.bat` window is open; close the window to stop. On Mac or Linux run `python3 run_local.py`.

## Or put it online (free, public address)

1. Open `site/how.html` and replace `CONTACT EMAIL` and `PUBLISHER NAME, COUNTRY` with yours.
2. Create a **public** repository on GitHub and upload everything in this folder, including the `.github` folder.
3. Open the **Actions** tab, choose **update**, press **Run workflow**. The first run looks back 4 hours.
4. When it finishes: **Settings → Pages → Source: Deploy from a branch → `gh-pages` / root**.
5. The site is at `https://<your-name>.github.io/<repository>/`.

If the "Publish" step fails with a permission error, set **Settings → Actions → General →
Workflow permissions → Read and write** and run it again.

It then rebuilds every 15 minutes. An open page checks for new data every 5 minutes.

## What is in here

| File | Purpose |
|---|---|
| `build.py` | Screens, groups, compresses, ranks. Standard-library Python only. |
| `test_build.py` | 24 tests, one or more per rule. Run before every build. |
| `rules/` | Editable, published blocklists (headline patterns, outlets). |
| `site/` | The page, the method page, the self-hosted font. |
| `run_local.py`, `start.bat` | Run it on your own computer only. |
| `.github/workflows/update.yml` | The 15-minute timer. Plain git, no third-party actions. |

The published site, the day-by-day archive and the program's memory live on the `gh-pages`
branch, rewritten as a single commit on every run.

## Settings (top of build.py, or environment variables in the workflow)

- `MIN_OUTLETS` (5): outlets a story needs to appear. Raise it once you see live volume.
- `NAME_MIN` (10): differently worded reports needed before a person is named.
- `HEADLINES` (3): real headlines shown when a line is opened. `0` shows outlet links only.
- `LINES` (12): lines on the page.

## Check the rules

    python3 -m unittest test_build

## Status and known limits

- Tested on fixtures and at simulated volume, **not yet against the live GDELT feed**.
  Expect to tune the grouping thresholds after the first day; watch for merged or split stories.
- The program stops without publishing if GDELT's format changes or its own memory is unreadable,
  so a failed run leaves the last good page in place. The page then shows "stale".
- GitHub's timer can run late, and GitHub pauses timers on repositories with no activity for
  60 days. Press **Run workflow** to restart.
- Wording is built from English-language headlines only. Other languages count toward outlet and
  country totals through GDELT's machine translation of names. To exclude them, remove the
  `attach_translated` call in `main()`.
- A regularly updated news site may carry legal duties where you live (in Finland, the Act on the
  Exercise of Freedom of Expression in Mass Media: a named publisher and responsible editor).
  This has not been checked by a lawyer.

Data: The GDELT Project (https://www.gdeltproject.org/). Font: JetBrains Mono, SIL OFL 1.1.
