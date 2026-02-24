# Media Leverage Agent

> A self-hosted Telegram bot that turns raw ideas, conversation logs, and uploaded files
> into platform-ready content — powered by any OpenAI-compatible LLM.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-20%2B-blue)](https://python-telegram-bot.org/)

Send a rough idea, paste a conversation, or upload a file — the bot analyzes the content,
decides which platforms it suits, and generates a tailored version for each: X thread,
Medium article, Substack newsletter, or Reddit post.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Commands](#commands)
- [Usage Flows](#usage-flows)
- [LLM Providers](#llm-providers)
- [Deployment](#deployment)
- [Project Structure](#project-structure)
- [Development](#development)
- [Platform Publishing Guidelines](#platform-publishing-guidelines)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Content analysis** — evaluates idea type, novelty, clarity, and publishing risk via LLM
- **Multi-platform rewriting** — routes to best-fit platforms and generates a tailored version for each
- **Tag system** — mark a conversation point, then batch-analyze everything after it
- **File upload** — `.txt` / `.md` / `.json` / `.csv`, up to 20 MB
- **History** — retrieve any past record with `/show <id>`
- **Hot-reload allowlist** — add or remove users in `config/users.json` without restarting
- **Basic rate limiting** — per-user request caps for chat and processing flows
- **Multi-LLM** — Anthropic Claude, OpenAI, GitHub Copilot (unofficial), or any custom endpoint

---

## How It Works

```
User input (text / file / conversation)
         │
         ▼
  ┌─────────────┐
  │   Analyze   │  LLM call #1 — outputs global metrics + per-platform assessments
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │    Route    │  Pure function — picks candidate platforms via idea_type + novelty_score
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │   Filter    │  Keep only platforms marked publishable in platform assessments
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │   Rewrite   │  LLM call per platform — generates X thread / Medium / Substack / Reddit
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Save + Send│  Persisted to SQLite; results sent back as Telegram messages
  └─────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- A Telegram bot token — create one via [@BotFather](https://t.me/BotFather)
- An API key for at least one LLM provider

### Installation

```bash
git clone https://github.com/liuzhezhezhezhe/media_lavarage_agent.git
cd media_lavarage_agent

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .
```

### Setup

```bash
# 1. Environment variables
cp .env.example .env
# Edit .env — set TELEGRAM_BOT_TOKEN and one LLM provider key

# 2. Authorized users
cp config/users.json.example config/users.json
# Edit config/users.json — add your Telegram user ID
# (send any message to @userinfobot to get your ID)

# 3. Run
python main.py
```

---

## Configuration

### `.env` reference

```dotenv
# Required
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# LLM provider — choose one: anthropic | openai | copilot | custom
LLM_PROVIDER=anthropic

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-6

# OpenAI / custom endpoint
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1

# GitHub Copilot (unofficial)
GITHUB_TOKEN=gho_...
COPILOT_MODEL=gpt-4o

# Webhook — leave empty to use polling (default)
# WEBHOOK_URL=https://yourdomain.com/bot
# WEBHOOK_SECRET=your-random-secret
# WEBHOOK_PORT=8443

# Storage
DB_PATH=~/.media_agent/memory.db
USERS_CONFIG=config/users.json

# Rate limit (per user)
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_PIPELINE_PER_WINDOW=6
RATE_LIMIT_CHAT_PER_WINDOW=20
```

### `config/users.json`

> This file is gitignored and never committed — it may contain personal IDs.

```json
{
  "authorized_users": [
    {"id": 123456789, "name": "Alice", "note": "admin"},
    {"id": 987654321, "name": "Bob",   "note": "team member"}
  ]
}
```

Changes take effect immediately — no bot restart required.

---

## Commands

| Command | Access | Description |
|---------|--------|-------------|
| `/start` | Everyone | Welcome message |
| `/help` | Everyone | Show all commands |
| `/status` | Everyone | LLM config, record count, auth status |
| `/whoami` | Everyone | Your Telegram user ID |
| `/chat` | Authorized | Enter chat mode — explore ideas with AI |
| `/process` | Authorized | Enter process mode — paste text or upload a file |
| `/tag [label]` | Authorized | Place a marker; exits any active mode |
| `/style [text]` | Authorized | Set your personal rewrite style; `/style` to view, `/style clear` to remove |
| `/analyze` | Authorized | Analyze accumulated messages and exit mode; in `/chat`, analyzes the current session transcript |
| `/cancel` | Authorized | Exit any active mode and **discard** accumulated session data |
| `/history` | Authorized | Last 10 processed records |
| `/show <id>` | Authorized | Full analysis and platform outputs for a record |
| `/clear` | Authorized | Clear all your stored data (thoughts, outputs, messages, tags) |

### Mode behaviour

The bot has two interactive modes — **chat** (`/chat`) and **process** (`/process`). Inside
either mode, the following rules apply:

| Action | Result |
|--------|--------|
| `/analyze` | Runs the pipeline on accumulated messages, then exits the mode. In `/chat`, only the current session transcript (**user + assistant**) is analyzed. Session data is **kept** until analysis completes, then cleaned up. |
| `/cancel` | Exits the mode immediately. All unsaved session data is **discarded**. |
| `/tag` | Places a marker and exits the mode. Accumulated data since the last tag is **discarded**. |
| `/clear` | Clears all your stored data and exits the mode. |
| `/process` (in chat mode) | Switches directly to process mode. Chat session data is **discarded**. |
| `/chat` (in process mode) | Switches directly to chat mode. |

---

## Usage Flows

### Flow 1 — Process mode

Paste content or upload a file for immediate analysis.

```
You:  /process
Bot:  Send the content you want to analyze...

You:  [paste text]
Bot:  🔍 Analyzing, please wait…
Bot:  📊 Analysis Results
      Type: opinion | Novelty: 8/10 | Clarity: 7/10 | Risk: low | Publishable: ✅
      💡 Summary: ...
      📌 Recommended platforms: X → Medium
       🧭 Platform Assessments:
       - X ✅ | N:8/10 | C:8/10 | Risk: low
       - Medium ✅ | N:7/10 | C:7/10 | Risk: low
       - Substack ❌ | N:5/10 | C:5/10 | Risk: medium
       - Reddit ✅ | N:7/10 | C:6/10 | Risk: low
Bot:  🐦 X  [tweet content]
Bot:  📝 Medium  [article]
```

### Flow 2 — Tag system

Accumulate messages, then analyze everything between two markers.

```
You:  /tag my AI writing discussion
You:  [chat normally — messages are stored silently]
You:  /analyze
Bot:  🔍 Reading 5 message(s) after marker "my AI writing discussion"…
Bot:  [analysis + platform assessments + platform versions]
```

### Flow 3 — Chat mode

Have a back-and-forth with the AI to develop an idea, then convert it.

```
You:  /chat
Bot:  💬 Chat mode active. Explore your ideas freely.
      Use /analyze when done — it processes the conversation and exits.
      Use /tag to mark and exit. Use /cancel to discard and exit.

You:  [multi-turn conversation]

You:  /analyze   ← processes this chat session transcript (user + assistant), saves results, exits chat mode
Bot:  🔍 Analyzing conversation…
Bot:  [analysis + platform assessments + platform versions]
```

> `/analyze` in chat mode analyzes only messages generated in that chat session.
> `/cancel` exits chat mode and **discards** all messages from the session.
> Switching to `/process` mid-chat also discards the chat session.

### File upload

Supported in `/process` mode: `.txt`, `.md`, `.json` (extracts `content`/`text`/`message`
fields — compatible with ChatGPT and Claude export formats), `.csv`. Max 20 MB; output
truncated at 100 KB.

---

## LLM Providers

| Provider | `LLM_PROVIDER` value | Notes |
|----------|----------------------|-------|
| Anthropic Claude | `anthropic` | Recommended |
| OpenAI | `openai` | Any GPT model |
| Custom endpoint | `custom` | Any OpenAI-compatible API (Ollama, vLLM, etc.) |
| GitHub Copilot | `copilot` | Unofficial — ToS gray area, use at your own risk |

**Copilot device flow** — if `GITHUB_TOKEN` is not set, the bot runs a terminal-based
device authorization on first startup and writes the token back to `.env` automatically.

---

## Deployment

Recommended: a VPS with **webhook mode** enabled.

```bash
# On the server
git clone https://github.com/liuzhezhezhezhe/media_lavarage_agent.git
cd media_lavarage_agent
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env && cp config/users.json.example config/users.json
# Edit both files, then set WEBHOOK_URL in .env

# systemd service
sudo tee /etc/systemd/system/media-agent.service > /dev/null << 'EOF'
[Unit]
Description=Media Leverage Agent
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/media_lavarage_agent
ExecStart=/home/ubuntu/media_lavarage_agent/.venv/bin/python main.py
Restart=always
RestartSec=5
EnvironmentFile=/home/ubuntu/media_lavarage_agent/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload && sudo systemctl enable --now media-agent
```

**HTTPS with Caddy** (auto TLS):

```bash
sudo apt install caddy -y
# /etc/caddy/Caddyfile:
# yourdomain.com { reverse_proxy localhost:8443 }
sudo systemctl restart caddy
# Then set WEBHOOK_URL=https://yourdomain.com/bot in .env
```

---

## Project Structure

```
media_lavarage_agent/
├── main.py                    # Entry point (production)
├── dev.py                     # Entry point (hot reload)
├── config.py                  # pydantic-settings (reads .env)
├── db.py                      # SQLite data layer
├── config/
│   ├── users.json             # Allowlist (gitignored)
│   └── users.json.example     # Allowlist template
├── bot/
│   ├── auth.py                # Per-request authorization
│   ├── formatter.py           # Telegram MarkdownV2 helpers
│   ├── file_parser.py         # File → plain text extraction
│   └── handlers.py            # All command and message handlers
└── agent/
    ├── llm/                   # LLM client implementations + factory
    ├── modules/               # analyze.py · route.py · rewrite.py
    └── prompts/               # Prompt templates (analyze · rewrite · chat)
```

**Database schema** (`~/.media_agent/memory.db`):

| Table | Description |
|-------|-------------|
| `thoughts` | One row per processed item; all analysis fields |
| `outputs` | Platform-specific content, linked to `thoughts` |
| `chat_messages` | Stored chat transcript messages (user + assistant, used by `/analyze`) |
| `tags` | Marker records |

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Hot-reload mode (restarts on any .py change)
python dev.py
```

### Extending the bot

**Add a new LLM provider**

1. Create `agent/llm/your_provider.py` — inherit `LLMClient`, implement `complete()` and `chat()`
2. Register it in `agent/llm/factory.py`

**Add a new output platform**

1. Add platform instructions to `PLATFORM_INSTRUCTIONS` in `agent/prompts/rewrite.py`
2. Add the platform to `_TYPE_TO_PLATFORMS` in `agent/modules/route.py`
3. Add an icon to `_PLATFORM_ICONS` in `bot/formatter.py`

**Modify the analysis logic**

- Scoring criteria and field definitions: `agent/prompts/analyze.py`
- Routing rules: `agent/modules/route.py`
- Rewrite instructions per platform: `agent/prompts/rewrite.py`

---

## Platform Publishing Guidelines

The bot embeds platform rules directly into the rewrite prompts. The section below
documents the reasoning behind those rules.

<details>
<summary>X (formerly Twitter)</summary>

**Algorithm weights** (source: open-sourced 2024 ranking code)

- Retweet **20×** · Reply **13.5×** · Bookmark **10×** · Like **1×**
- Write for retweet-worthiness, not just likability

**Penalties to avoid**

| Issue | Penalty |
|-------|---------|
| Multiple hashtags | −40% distribution |
| External link in main tweet | −30–50% distribution |
| Spelling/grammar errors | −95% distribution |

**Engagement bait** (penalized since 2024): "RT if you agree", "Like for A / RT for B",
"Comment YES", "Follow me for more", "Link in bio".

**External links**: put them in the first reply, not the main tweet.

</details>

<details>
<summary>Medium</summary>

**Distribution tiers**

| Tier | Requirement |
|------|-------------|
| Network Only | Default |
| General Distribution | Original insight, clear voice, no violations |
| Boost | First-hand expertise, strong narrative, factual grounding |

**AI content policy (May 1, 2024)**: primarily AI-written content is ineligible for the
Partner Program and receives Network Only distribution if undisclosed.

</details>

<details>
<summary>Substack</summary>

Subject line rules (email deliverability):
- 6–10 words, sentence case, max 1 emoji at the end
- Banned words: `Free`, `Click here`, `Buy now`, `Limited time`, `Special offer`, `Sale`

Body: max 3–5 external links; no "click here" anchor text; no `unsubscribe` outside the footer.

</details>

<details>
<summary>Reddit</summary>

- Titles cannot be edited after posting — get them right
- Vote solicitation is a site-wide ban trigger: "Upvote if you agree", "Help this reach the top", etc.
- 90/10 self-promotion rule: no "follow me", "subscribe", or affiliate links
- Disclose AI assistance at the end of the post — ~17% of large subreddits actively enforce this

</details>

---

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes with a clear message
4. Open a pull request — describe what you changed and why

For significant changes, open an issue first to discuss the approach.

**Areas where contributions are especially welcome:**
- New LLM provider integrations
- New output platforms
- Improved prompt quality
- Bug fixes and edge-case handling

Please keep pull requests focused — one feature or fix per PR.

---

## License

MIT © [liuzhezhezhezhe](https://github.com/liuzhezhezhezhe)

See [LICENSE](LICENSE) for the full text.
