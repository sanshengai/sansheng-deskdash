# sansheng-deskdash · your agent as a desktop-dashboard crew

> **Tell it what you want to watch, and the agent turns it into a tile that lives on your Windows wallpaper — native, no browser, self-refreshing, and it asks to be fixed when it breaks.**

[中文](./README.md) | **English**

![License](https://img.shields.io/badge/License-MIT-green) ![Platform](https://img.shields.io/badge/Platform-Windows-blue) ![Rainmeter](https://img.shields.io/badge/Rainmeter-4.5%2B-lightgrey) ![Python](https://img.shields.io/badge/Python-3.10%2B-blue)

<p align="center">
  <img src="assets/board-preview.png" width="360" alt="Full board preview: clock & calendar + weather + todo">
  <br><sub>A board pinned to your wallpaper: clock & calendar + weather + todo (on the wall in 60 seconds)</sub>
</p>

---

## Not just another dashboard — three things nobody else occupies

Most "desktop dashboards" are a browser tab or an Electron window, locked to the data sources the author shipped. This skill is different:

1. **Native, pinned to the wallpaper** — a Rainmeter skin drawn straight onto the desktop, not a browser, not Electron; it comes back after a reboot, with no resident app hogging memory.
2. **On-the-spot collectors for long-tail sources** — if a source isn't in the library (your NAS, some small service with an API, a CSV you export), the agent **writes a read-only collector for it right there**. That's the layer nobody else automates: not "pick from a fixed list" but "if it has an API, it can be built."
3. **Self-healing loop** — a module that fails 3 times in a row greys out and prompts *"tell me to fix the board"*; one sentence from you and the agent reads the diagnostics and semi-automatically repairs it. It **never rewrites code unattended** (a safety red line — see below).

Designed for **non-programmers** (describe it in plain words; never touch Rainmeter INI or write scripts), friendly to programmers underneath. **Windows only.**

---

## Get started in 60 seconds

```bash
# 1. Clone
git clone https://github.com/sandypoli-boop/sansheng-deskdash.git

# 2. Install as a skill (symlink into ~/.claude/skills; Windows PowerShell, no admin needed)
#    ⚠ Run this from the directory you cloned INTO (the repo's parent), not inside the repo,
#      otherwise -Target points at the wrong path.
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\sansheng-deskdash" -Target "$(Get-Location)\sansheng-deskdash"
#    macOS / Linux:  ln -s "$(pwd)/sansheng-deskdash" ~/.claude/skills/sansheng-deskdash

# 3. Open Claude Code and say:
#    "help me build a desktop dashboard"
```

The agent runs an environment check (prompts `winget install Rainmeter.Rainmeter` if missing) → pins a clock to the wall first (**first-run failure rate designed to be zero**) → asks five questions (leave all blank = all defaults) → installs modules or builds one on the spot → keeps it refreshing.

> Or via the plugin marketplace: `claude plugin marketplace add sandypoli-boop/sansheng-deskdash` then `claude plugin install sansheng-deskdash`.

**Requirements**: Windows · Rainmeter 4.5+ · Python 3.10+ (stdlib only) · optional `gh` (GitHub rate limits), `Pillow` (calendar image).

---

## Official module gallery

Ships with 6 official modules + 3 starter boards (`templates/starter-boards/`); every screenshot is a real render.

<!-- GALLERY:START -->

> This table is generated from `registry/registry.json` by `scripts/gen_readme_gallery.py`; do not edit by hand.

| Preview | Module | Category | Tier | What it does |
|---|---|---|---|---|
| <a href="modules/clock-calendar/screenshot.png"><img src="modules/clock-calendar/screenshot.png" width="220" alt="screenshot"></a> | **Clock & Calendar**<br><sub>时钟日历</sub> | `time` | 🥉 Bronze | Clock plus a current-month calendar with today highlighted; no network, no keys — the rock-solid foundation tile. |
| <a href="modules/weather/screenshot.png"><img src="modules/weather/screenshot.png" width="220" alt="screenshot"></a> | **Weather**<br><sub>天气</sub> | `weather` | 🥉 Bronze | Current conditions plus a 7-day forecast with temperature curves; works keyless via open-meteo, optional Caiyun token. |
| <a href="modules/todo/screenshot.png"><img src="modules/todo/screenshot.png" width="220" alt="screenshot"></a> | **Todo**<br><sub>待办清单</sub> | `tasks` | 🥉 Bronze | Check off / add / edit / delete todos right on the wallpaper; the interactive flagship, no network, no keys. |
| <a href="modules/github/screenshot.png"><img src="modules/github/screenshot.png" width="220" alt="screenshot"></a> | **GitHub Activity**<br><sub>GitHub 动态</sub> | `dev` | 🥉 Bronze | Your stars / PR overview plus top-repo list; uses gh CLI when present, else falls back to anonymous REST. |
| <a href="modules/net-latency/screenshot.png"><img src="modules/net-latency/screenshot.png" width="220" alt="screenshot"></a> | **Network Latency**<br><sub>网络延迟</sub> | `network` | 🥉 Bronze | Latency to several targets (ping / TLS handshake) — see at a glance how fast your network is. |
| <a href="modules/server-status/screenshot.png"><img src="modules/server-status/screenshot.png" width="220" alt="screenshot"></a> | **Server Status**<br><sub>服务状态</sub> | `system` | 🥉 Bronze | Service health (HTTP status code + latency / ping) — watch whether your own sites are up. |

<!-- GALLERY:END -->

Before installing a module the agent **reads out which domains it contacts, which local paths it reads/writes, and which secret names it needs** — you approve before it installs (see Security model).

---

## Security model (an honest statement, not a fake sandbox)

The agent runs collector code it writes/installs on your desktop — that takes trust, so the boundary must be explicit.

**v1 has no runtime network sandbox** (no low-cost real user-mode sandbox exists on Windows). Instead there are **four layers of defense**:

| Layer | What it does |
|---|---|
| ① Declared privacy | Each module's `widget.json` explicitly declares a `network / local_read / local_write` triple; read out before install |
| ② AST static scan | `validate_module.py` scans collector source: banned calls (`eval`/`exec`/`shell=True`/`Invoke-Expression`), and the actually-requested domains must be ⊆ declared |
| ③ VALIDATE dry-run | After building/editing a collector, it runs once to show you the **real network targets + real output** before wiring it up |
| ④ User review | You approve before installing a module or registering the background refresh task (three review gates) |

**Hard bans**: collectors read external / write only their own & the board dir; no reading browser cookies or credential stores; no undeclared domains; skins may not `!Execute` arbitrary commands or remote-load.

**Dependency allowlist**: collectors are **stdlib-only** by default; the only exceptions are `requests` and `Pillow`. Nothing else, and no `pip install` inside a collector.

**Secrets** go only into git-ignored `config.json` — **never into code, logs, or error messages** (a secret-canary test injects a fake key and asserts no leak across failure paths).

**Real Windows friction**: all PowerShell scripts are invoked with `-ExecutionPolicy Bypass -File` — the system policy is never changed and nothing is downloaded and executed; the scheduled task fires 5 minutes after login (survives a not-yet-ready network).

---

## What it can build / what it won't touch

Before building a collector, the agent runs a **source traffic light**:

| Light | Source | Action |
|---|---|---|
| 🟢 Green | Public APIs / APIs with your own key / local files & LAN devices | Build it, may contribute upstream |
| 🟡 Yellow | Private services needing your own cookie (home NAS / router) | Build it, but **local-only, not contributed** |
| 🔴 Red | Anything needing login/anti-bot bypass, or ToS-forbidden (banks, brokers, social-platform private APIs) | **Refused** + a safe fallback |

**Won't-touch list**: banks / brokers / private APIs of WeChat, Weibo, Douyin and other social platforms / any source requiring simulated login to bypass controls, defeat anti-scraping, or violate ToS. The agent says so plainly and offers two safe paths instead (official public API / export a CSV and it reads the file).

> **Disclaimer**: this skill builds only **read-only** collectors that touch only the sources you/the module **explicitly declare**. You are responsible for the services a bespoke module reaches and the credentials you supply; do not use it to fetch data you are not entitled to or that a ToS forbids. Software provided "as is" under MIT, without warranty.

---

## Contributing

A good on-the-spot module can be sanitized and sent back so others can install it directly:

```bash
python scripts/new_module.py <id>              # scaffold the seven files
# edit collector.py / band.inc / widget.json ...
python scripts/validate_module.py modules/<id>   # local check (same as future CI), must pass first
# add one entry to registry/registry.json → open a PR
```

The gallery is driven single-source from `registry/registry.json`; run `python scripts/gen_readme_gallery.py` to idempotently refresh the tables. Full flow, the seven-file module contract, and quality tiers live in [`references/contribution.md`](references/contribution.md).

---

## Requirements

- **OS**: Windows (native desktop; skin deployment & scheduled task are Windows-only)
- **Rainmeter** 4.5+ (`winget install Rainmeter.Rainmeter`)
- **Python** 3.10+ (collectors are pure stdlib; allowlisted optional packages `requests` / `Pillow`)
- **Optional**: `gh` (GitHub CLI), `Pillow` (calendar rendering)
- **Host**: native to Claude Code; a root `AGENTS.md` bridges other AGENTS.md-reading agent hosts

---

## License

[MIT](./LICENSE)
