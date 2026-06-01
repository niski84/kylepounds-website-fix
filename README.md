# kylepounds-website-fix

**Mission:** preserve [kylepounds.com](https://kylepounds.com) for the long term — fix the technical defects that prevent visitors from experiencing it, mirror the content daily, surface issues so they can be addressed, and provide a clean reading layer on top.

The live mirror runs at **[kylepounds.org](https://kylepounds.org)** and the operator dashboard is at **[kylepounds.org/patrol/](https://kylepounds.org/patrol/)**.

---

## What's wrong with kylepounds.com

Kyle's site is a sprawling personal universe — philosophy, education, history, cycling — built in late-2000s Dreamweaver. The content is genuinely remarkable; the markup is not. Site-patrol scans surface around **900 distinct findings per pass**, broken down roughly as:

| Defect | Per-scan count | What it means |
|---|---:|---|
| `missing-nav-element` | ~270 | No `<nav>` semantic tag — relies on table layout |
| `missing-viewport` | ~270 | No `<meta name="viewport">` — broken on mobile |
| `recursive-nav-link` | ~100 | Section nav links pointing back to themselves |
| `missing-base-href` | ~95 | Relative links resolving against unstable bases |
| `broken-link` | ~135 | Mostly Flickr URLs with literal spaces (`5 087783 8_..jpg`) |

Plus structural issues: every page is wrapped in 100+ nested layout tables, fonts are declared by family name with no `@font-face` loader, scripts inject trackers from defunct services.

## What this repo does

`scripts/mirror-and-deploy.sh` runs nightly on the VPS via GitHub Actions. Four phases:

1. **Mirror** — parallel `wget` of 6 top-level sections (`About Me`, `Education`, `News`, `Sports`, `Travel`, `index.html`) into `/var/www/kylepounds.org/kylepounds.com/`. `--timestamping` so only changed pages re-download.
2. **Process** — eight Python passes that patch the mirror in place:
   - `inject_noflash.py` — sets `color-scheme: light` + white bg before external CSS loads
   - `fix_mixed_content.py` — rewrites `http:` resource URLs to `https:`
   - `inject_basehref.py` — adds `<base href="https://kylepounds.org/">` so relative links work
   - `inject_viewport.py` — adds responsive viewport meta (fixes ~270 findings)
   - `wrap_nav.py` — wraps Kyle's section table in `<nav role="navigation">` (fixes ~90 findings)
   - `strip_trackers.py` — removes dead analytics scripts
   - `inject_banner.py` — stamps the rainbow "Mirrored from kylepounds.com" strip
   - `inject_fonts.py` — links `/fonts/fonts.css`
   - `build_fonts_css.py` — regenerates the `@font-face` rules from the actual `.otf` files on disk
3. **Re-ingest the Library** — `kp-ingest` walks all 2,700+ mirrored pages, classifies each into one of 8 page types, extracts clean reader HTML where possible. Stored in SQLite FTS5.
4. **Scan** — triggers a fresh site-patrol crawl so the dashboard's findings list and Compare tab stay current.

## The Library (v3)

`/patrol/library.html` is a clean-reader + full-text-search layer over Kyle's HTML. Classifier dispatches each page to one of:

- **essay** (43%) — extract to flowing paragraphs (Aristotle, Funding, About Me, etc.)
- **timeline / index / gallery / fallback** (49%) — iframe the original in our dark chrome (the content is too navigation-heavy to flatten cleanly without losing meaning)
- **genealogy / trip / data** (8%) — type-specific extraction that flattens Kyle's table data into readable form

Around 43% of pages render in our clean reader; 57% fall back to iframe with a banner explaining why. Full search via SQLite FTS5 works across **all** pages regardless of render mode.

## The Newsletter

A Site Health digest emails the latest scan's findings (subject line: "Kyle Pounce — Site Health Report · N findings"). Recipients live in `NEWSLETTER_RECIPIENTS` in the VPS `.env` (never committed). Configurable interval (weekly/monthly) + manual Send Now button in the admin Settings tab.

## Architecture

```
GitHub Actions (daily 7am UTC)
  └─ ssh to VPS, rsync scripts/, run mirror-and-deploy.sh
       └─ wget (parallel) → process HTML → ingest library → trigger scan
                                                              └─ writes SQLite at /opt/site-patrol/data/

nginx on 96.126.96.40
  ├─ /                → /var/www/kylepounds.org/  (mirrored Kyle content)
  ├─ /patrol/         → proxy to localhost:8211 (Go site-patrol service)
  ├─ /fonts/fonts.css → @font-face declarations for 40 hosted Adobe fonts
  └─ /patrol/kyle-pounds.mp3 → "Evaluating Kyle Pounds' Website" podcast

Go service at /opt/site-patrol/
  ├─ site-patrol binary
  ├─ kp-ingest binary
  └─ data/{site-patrol,archive}.db (SQLite)
```

## Repo layout

```
kylepounds-website-fix/
├─ scripts/                          # Mirror + processing pipeline (runs on VPS)
│  ├─ mirror-and-deploy.sh           # Entry point — invoked by GitHub Actions
│  ├─ inject_*.py                    # HTML patchers (run on every mirrored file)
│  ├─ wrap_nav.py                    # Wraps Kyle's nav table in <nav> tag
│  ├─ strip_trackers.py              # Removes dead analytics
│  ├─ build_fonts_css.py             # Regenerates @font-face from .otf files on disk
│  └─ fix_mixed_content.py           # http: → https: rewrites
├─ .github/workflows/                # Daily cron + manual dispatch
└─ .gitignore                        # site/, docs/, __pycache__
```

Site-patrol's source (Go dashboard, library, newsletter, classifier, scanner) lives in a separate `niski84/site-patrol` repo and is deployed manually.

## Operating

- **Daily mirror schedule:** 7am UTC (`.github/workflows/daily-mirror.yml`)
- **Manual trigger:** ssh to the VPS and run `/opt/kp-mirror/scripts/mirror-and-deploy.sh`
- **Site-patrol scan schedule:** every 24h (configurable in the Settings tab)
- **Newsletter schedule:** every 720h / 30 days (configurable; recipients via `NEWSLETTER_RECIPIENTS` env var)
- **Admin password:** stored in `/opt/site-patrol/.env` as `ADMIN_PASSWORD`

## Why kylepounds.org and not a fork of .com?

We don't want to fork or rewrite Kyle's site. He's the author; his structure is his expression. Our role is to be the technical custodians — keep the site reachable, readable, mobile-friendly, and searchable, while preserving everything he created.

---

*This README is rendered as the "Full Audit" tab on the [/patrol/](https://kylepounds.org/patrol/) dashboard.*
