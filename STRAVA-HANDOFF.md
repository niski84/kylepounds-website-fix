# Strava Login Handoff — resume after Claude restart

**Goal:** Log into Strava via the Chrome DevTools MCP (browser automation) so the
"Where is Kyle" feature on the Kyle Pounds website can pull Strava data.

## What we're doing
The MCP browser couldn't reach Strava because it kept launching a *clean* automation
profile (no login). We're switching it to drive Kyle/Nick's **real Brave profile**,
which already has the Strava session — so login should be automatic.

## Setup already done (no need to redo)
- **MCP server fixed to use Brave.** `chrome-devtools` MCP defaulted to Google Chrome,
  which isn't installed. Two fixes applied:
  - Symlink so the *running* server finds Brave: `/opt/google/chrome/chrome -> /opt/brave.com/brave/brave` (via `sudo ln -sf`).
  - Config in `~/.claude.json` → `mcpServers.chrome-devtools.args` now:
    ```
    chrome-devtools-mcp@latest
    --executablePath /opt/brave.com/brave/brave
    --userDataDir /home/nick/.config/BraveSoftware/Brave-Browser
    ```
- Brave binary: `/opt/brave.com/brave/brave`. Real profile: `~/.config/BraveSoftware/Brave-Browser/Default`.

## Why a restart was needed
MCP config changes only load on Claude Code startup, AND the real Brave profile must be
**fully closed** when automation launches it (Chromium locks the profile dir — only one
instance allowed). User quit Brave + restarted Claude before this resumes.

## Next steps after restart
1. Confirm the MCP picked up the new config: call `mcp__chrome-devtools__list_pages`
   (load schemas via ToolSearch first — these are deferred tools).
   - If it errors that Brave is already running / profile locked → tell user to fully
     quit Brave, then retry.
2. Navigate to `https://www.strava.com/dashboard` (or `/login`) and `take_snapshot`.
   - If already logged in (their real profile) → great, proceed to the Strava data work.
   - If NOT logged in → user logs in manually in the visible Brave window; session persists.
3. Then return to the actual task: wiring Strava data into the "Where is Kyle" feature
   on the Kyle Pounds website (`/home/nick/goprojects/kylepounds-website-fix`).

## Cleanup note (do when Strava work is done)
The `--userDataDir` setting means automation and the user's everyday Brave share ONE
instance (can't run a second Brave). When finished, offer to revert
`~/.claude.json` mcpServers.chrome-devtools.args back to the clean automation profile
(drop `--userDataDir`) so they decouple again.
