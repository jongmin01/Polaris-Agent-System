# Polaris — 연구자를 위한 개인 AI 비서 (Personal AI Assistant for Researchers)

[![Version](https://img.shields.io/badge/version-0.7%20(beta)-blue.svg)](https://github.com/yourusername/Polaris-Agent-System)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Polaris** is a personal AI assistant for researchers and scientists. It connects your HPC cluster, email, calendar, and research papers into a single conversational interface via Telegram — running entirely on local hardware with no mandatory cloud API costs.

---

## Architecture

```
Telegram Bot Interface (bot_v2.py)
         |
         v
  PolarisRouter (router.py)
  - Ollama ReAct loop (free, local)       <- default
  - Anthropic opt-in (claude-sonnet-4-6)  <- requires POLARIS_ALLOW_PAID_API=true
  - Dual-model routing:
      llama3.1:8b   (~14s)  for casual conversation
      llama70b-lite (~3min) for tool calls
         |
    +----+----+----+----+----+
    |    |    |    |    |    |
   HPC  arXiv Mail Cal  PhD  MailOps   (polaris/tools/)
         |
  ApprovalGate (approval_gate.py)
  AUTO | CONFIRM | CRITICAL
         |
  TraceLogger  -> data/trace.db
  Memory       -> data/polaris_memory.db
  MailOps      -> data/mailops.db
```

### Core Modules

| Module | Description |
|--------|-------------|
| `polaris/router.py` | LLM ReAct loop — Ollama default, Anthropic optional. Injects memory + skill context into system prompt. |
| `polaris/tools/` | 13 tools across 5 modules (hpc, arxiv, email, calendar, phd) + MailOps tools. Auto-discovery registry. |
| `polaris/approval_gate.py` | 3-tier risk gate: AUTO (safe reads), CONFIRM (Telegram inline keyboard), CRITICAL (blocked). |
| `polaris/trace_logger.py` | SQLite audit trail — every tool execution recorded to `data/trace.db`. |
| `polaris/memory/` | Second Brain: semantic search, feedback loop, fact extractor, Obsidian vault indexer. |
| `polaris/mailops/` | Apple Mail integration via AppleScript. Multi-account, 4-category classifier, local SQLite storage. |
| `polaris/skills/` | Markdown-based skill registry. Trigger matching injects skill prompts into the ReAct context. |
| `polaris/bot_v2.py` | Telegram bot entry point. Wraps PolarisRouter with all command handlers. |
| `hpc_monitor.py` | HPCMonitor class — SSH connection checks, PBS/Slurm queue parser. |
| `schedule_agent.py` | iCloud CalDAV integration, multi-calendar, CST timezone. |

### Memory / Second Brain

- **Conversations**: every route() call is persisted to SQLite with session_id.
- **Semantic search**: Ollama `nomic-embed-text` embeddings (local, free). Falls back to keyword search if embedder is unavailable.
- **Feedback loop**: `FeedbackManager` detects correction phrases ("아니", "그게 아니라", "틀렸어"), saves to `feedback` table, re-injects as caution blocks in subsequent prompts.
- **Fact extractor**: `FactExtractor` — rule-based regex (no LLM call). Extracts research/career/life facts from conversation and updates `data/master_prompt.md` automatically.
- **Obsidian vault indexer**: `VaultReader` — read-only, incremental (tracks changes via `vault_index.json`). Indexes `.md` files into the knowledge table; results injected into system prompt at query time.

### Skill System

Skills are Markdown files in `skills/` with YAML frontmatter. The router matches incoming messages against skill triggers and injects up to 2 matched skill prompts into the LLM context.

Current skills (9):

| Skill | Purpose |
|-------|---------|
| `vasp_convergence.md` | VASP convergence check (OSZICAR, Janus TMDC) |
| `arxiv_analysis.md` | Paper analysis (5 perspectives) |
| `paper_to_obsidian.md` | Paper to Obsidian note conversion |
| `email_triage.md` | Email URGENT/NORMAL/FYI classification |
| `hpc_monitor.md` | HPC job monitoring + VASP error diagnosis |
| `daily_briefing.md` | Daily briefing (schedule/HPC/mail/papers) |
| `mail_digest.md` | Unified mail digest skill |
| `mail_triage.md` | Mail triage skill |
| `promo_tracker.md` | Promotion/deal tracker |

All skills include `requires_tool: true` and `strict_mode: true` — the router enforces actual tool calls and blocks hallucinated answers when a skill is matched.

---

## Getting Started

### Prerequisites

- **Python 3.9+**
- **macOS** (required for Apple Mail / AppleScript integration)
- **Ollama** installed locally: https://ollama.ai
- **Telegram account** and a bot token from [@BotFather](https://t.me/botfather)
- **PM2** (optional, for 24/7 operation): `npm install -g pm2`

### 1. Install Ollama and Pull Models

```bash
# Install Ollama from https://ollama.ai, then:
ollama pull llama3.1:8b          # Fast model for casual conversation (~14s)
ollama pull nomic-embed-text     # Local embeddings for memory/semantic search

# For the 70B model, either pull directly or use a Modelfile:
ollama pull llama3.3:70b         # ~48GB RAM required

# Recommended Modelfile (llama70b-lite) — sets num_ctx=32768, no system prompt:
# See: https://ollama.ai/library/llama3.3
```

Verify Ollama is running:
```bash
ollama list
curl http://localhost:11434/api/tags  # should return model list
```

### 2. Clone and Install Python Dependencies

```bash
git clone https://github.com/yourusername/Polaris-Agent-System.git
cd Polaris-Agent-System
pip3 install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials (see Environment Variables section below)
```

### 4. SSH Setup for HPC (ControlMaster)

Create or edit `~/.ssh/config`:

```
Host polaris
    HostName polaris.alcf.anl.gov
    User your_username
    ControlMaster auto
    ControlPath ~/.ssh/%r@%h:%p
    ControlPersist 12h
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

Authenticate once to establish the ControlMaster session:
```bash
ssh polaris
# Enter password + MFA token
# The connection persists for 12 hours — no further re-auth needed
```

**SSH / HPC Security Policy:**
- SSH authentication (password, MFA, OTP) must be performed by the user directly.
- Polaris's role is limited to: connection status checks, failure detection, and re-authentication alerts.
- OTP relay via Telegram is explicitly disabled (security policy).

### 5. Run the Bot

**Direct (development/testing):**
```bash
python -m polaris.bot_v2
```

**PM2 (recommended for 24/7 operation):**
```bash
pm2 start "python -m polaris.bot_v2" --name "polaris-bot"
pm2 save
pm2 startup  # follow the printed command to enable on boot
```

**Verify:**
1. Open Telegram and find your bot.
2. Send `/start`.
3. Send `/status` to confirm all components are initialized.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

```bash
# --- Telegram ---
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# --- LLM Backend ---
# Default: ollama (free, local). Set to "anthropic" to use Claude.
POLARIS_LLM_BACKEND=ollama
POLARIS_ALLOW_PAID_API=false       # Must be "true" to enable Anthropic calls

# Ollama settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama70b-lite         # 70B model for tool calls
OLLAMA_MODEL_FAST=llama3.1:8b     # 8B model for casual conversation

# Anthropic (optional — only used if POLARIS_ALLOW_PAID_API=true)
ANTHROPIC_API_KEY=your_claude_api_key_here

# --- Obsidian ---
OBSIDIAN_VAULT_PATH=~/Library/Mobile Documents/iCloud~md~obsidian/Documents
MASTER_PROMPT_PATH=data/master_prompt.md

# --- Apple Mail ---
# Comma-separated keywords to select accounts. Use * or ALL for every account.
# To find your account names: osascript -e 'tell application "Mail" to get name of every account'
MAIL_ACCOUNT_KEYWORDS=UIC,Google

# MailOps polling interval in seconds (default: 300)
POLARIS_MAILOPS_POLL_INTERVAL=300

# --- HPC: Single Cluster ---
HPC_HOST=polaris.alcf.anl.gov
HPC_USERNAME=your_username
HPC_SCHEDULER=pbs                  # pbs | slurm
HPC_REMOTE_PATH=/opt/pbs/bin:/usr/bin:/bin
PBS_QSTAT_PATH=/opt/pbs/bin/qstat
SLURM_SQUEUE_PATH=/usr/bin/squeue

# --- HPC: Multi-Cluster (optional — overrides single-cluster settings above) ---
# HPC_ACTIVE_PROFILE=polaris
# HPC_PROFILES_JSON={"polaris":{"host":"polaris.alcf.anl.gov","scheduler":"pbs","username":"your_username","remote_path":"/opt/pbs/bin:/usr/bin:/bin"},"carbon":{"host":"carbon.example.com","scheduler":"slurm","username":"your_username","remote_path":"/usr/bin:/bin"}}

# --- iCloud Calendar ---
ICLOUD_USERNAME=your_apple_id@icloud.com
ICLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # Generate at appleid.apple.com > App-Specific Passwords

# --- Hot Reload ---
POLARIS_AUTO_RELOAD=true
POLARIS_AUTO_RESTART_ON_CODE_CHANGE=false  # Set true to auto-restart on .py changes
POLARIS_RELOAD_CHECK_INTERVAL=2.0          # Seconds between change checks
```

**HPC Scheduler Notes:**
- `HPC_SCHEDULER=pbs` — uses `qstat`, `qsub` (PBS/Torque style).
- `HPC_SCHEDULER=slurm` — uses `squeue`, `sbatch` (Slurm style).
- In non-interactive SSH sessions the PATH is minimal. Set `HPC_REMOTE_PATH` so scheduler binaries resolve correctly.

Validate your setup:
```bash
# PBS
ssh polaris "PATH=/opt/pbs/bin:/usr/bin:/bin:$PATH; qstat -u your_username"

# Slurm
ssh your-cluster "squeue -u your_username"
```

---

## Telegram Commands

### System
| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | List all commands |
| `/status` | System health and component status |
| `/tools` | List all registered tools |
| `/skills` | List registered skills (with enforcement tags) |
| `/trace` | Recent action audit trail |
| `/reload` | Reload skills and prompt files without restarting |

### Mail (Apple Mail)
| Command | Description |
|---------|-------------|
| `/mail` | Check primary mail account (unread summary) |
| `/mail_accounts` | List Apple Mail account names (for MAIL_ACCOUNT_KEYWORDS config) |
| `/mail_digest` | Unified digest across all tracked accounts |
| `/mail_urgent` | Urgent mails only |
| `/mail_promo` | Promotion and deal mails |
| `/mail_actions` | Propose safe mail actions (archive, label, mark read) |

Mail categories: `urgent` / `action` / `info` / `promo`

### Research
| Command | Description |
|---------|-------------|
| `/search <query>` | Search arXiv for papers |

### HPC
| Command | Description |
|---------|-------------|
| `/hpc` | Check active cluster connection status |
| `/hpc status [cluster]` | SSH connection check for named cluster |
| `/hpc jobs [cluster]` | List current queue jobs (`jobid-state` summary) |

Examples:
```
/hpc                    # active profile status
/hpc status polaris     # explicit connection check
/hpc jobs polaris       # queue jobs on polaris
```

### Calendar
| Command | Description |
|---------|-------------|
| `/schedule` | Today and tomorrow's events from all iCloud calendars |

### Memory and Learning
| Command | Description |
|---------|-------------|
| `/wrong` | Mark the last response as incorrect (triggers correction loop) |
| `/feedback` | Show recent feedback / correction history |
| `/index` | Index Obsidian vault in background |
| `/vault` | Vault indexing stats |
| `/vault search <query>` | Semantic search across indexed vault notes |

### Natural Language

All commands also accept natural language routed through the ReAct loop:

```
"Search for Janus TMDC papers on valleytronics"
"내일 일정 알려줘"
"How many jobs are running on Polaris?"
"Summarize my urgent emails"
```

---

## Project Structure

```
Polaris-Agent-System/
├── polaris/                       # Core package (v2 architecture)
│   ├── bot_v2.py                 # Telegram bot — entry point
│   ├── router.py                 # LLM ReAct loop (Ollama + Anthropic)
│   ├── approval_gate.py          # Risk-based approval gate
│   ├── trace_logger.py           # SQLite audit trail
│   ├── tools/                    # 13 tools in 5 modules + MailOps
│   │   ├── hpc_tools.py
│   │   ├── arxiv_tools.py
│   │   ├── email_tools.py
│   │   ├── calendar_tools.py
│   │   ├── phd_tools.py
│   │   └── mailops_tools.py
│   ├── memory/                   # Second Brain
│   │   ├── memory.py             # PolarisMemory (semantic + keyword search)
│   │   ├── embedder.py           # OllamaEmbedder (nomic-embed-text)
│   │   ├── feedback_manager.py   # Correction detection and storage
│   │   ├── fact_extractor.py     # Rule-based fact extraction (no LLM)
│   │   ├── vault_reader.py       # Obsidian vault indexer (read-only)
│   │   ├── obsidian_writer.py    # Obsidian vault writer
│   │   └── schema.sql            # SQLite schema (4 tables)
│   ├── mailops/                  # Apple Mail integration
│   │   ├── store.py              # data/mailops.db schema and storage
│   │   ├── classifier.py         # 4-category rule-based classifier
│   │   ├── ingest.py             # AppleScript-based multi-account collector
│   │   └── service.py            # sync / digest / urgent / promo orchestration
│   └── skills/                   # Markdown skill loader and registry
│       ├── skill_loader.py
│       └── registry.py
├── skills/                       # Skill Markdown files (9 skills + README)
│   ├── vasp_convergence.md
│   ├── arxiv_analysis.md
│   ├── paper_to_obsidian.md
│   ├── email_triage.md
│   ├── hpc_monitor.md
│   ├── daily_briefing.md
│   ├── mail_digest.md
│   ├── mail_triage.md
│   └── promo_tracker.md
├── hpc_monitor.py                # HPCMonitor class (PBS/Slurm parser)
├── schedule_agent.py             # iCloud CalDAV integration
├── mail_reader.py                # Apple Mail reader wrapper
├── read_mail.scpt                # AppleScript (single + all-account modes)
├── data/                         # Runtime data (not committed)
│   ├── polaris_memory.db         # Memory: conversations, knowledge, feedback
│   ├── mailops.db                # MailOps: messages, classifications, alerts
│   ├── trace.db                  # Audit trail
│   ├── master_prompt.md          # Persona and context (auto-updated)
│   └── vault_index.json          # Obsidian incremental index tracker
├── tests/                        # 260+ tests (all pass without API keys)
├── requirements.txt
├── .env.example
└── CLAUDE.md                     # Development notes and architecture log
```

---

## Running Tests

All tests run without API keys — every external call is mocked.

```bash
python -m pytest tests/ -v
```

Current test count: 260+ across 11 test modules.

---

## Security

- **ApprovalGate** enforces 3-tier risk classification on every tool call:
  - `AUTO` — safe read-only operations, executed immediately.
  - `CONFIRM` — Telegram inline keyboard prompt sent to user before execution.
  - `CRITICAL` — blocked unconditionally.
- **Audit trail** — every executed tool call is recorded to `data/trace.db` (SQLite).
- **No OTP relay** — SSH authentication (password / MFA / OTP) must be performed by the user directly. Polaris only reports connection status and alerts when re-authentication is needed.
- **Local-first** — Ollama runs entirely on your machine. No conversation data leaves your network unless you opt in to Anthropic.

---

## Troubleshooting

### Ollama not responding

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve

# Verify model is available
ollama list
```

### Apple Mail / AppleScript permission error

```bash
# Grant Automation permission in System Settings:
# System Settings > Privacy & Security > Automation
# Enable "Terminal" (or your Python runner) to control "Mail"

# Verify the script manually:
osascript read_mail.scpt
```

### Find Apple Mail account names

```bash
osascript -e 'tell application "Mail" to get name of every account'
# Copy the names and set MAIL_ACCOUNT_KEYWORDS=Name1,Name2
# Or use MAIL_ACCOUNT_KEYWORDS=* to collect from all accounts
```

### HPC connection failed

```bash
# Authenticate to create ControlMaster session
ssh polaris

# Test the connection
ssh polaris "echo heartbeat"

# Check existing ControlMaster socket
ls -la ~/.ssh/*@*

# Remove stale socket and re-authenticate
rm ~/.ssh/*@polaris*
ssh polaris
```

### PM2 process crashes

```bash
pm2 logs polaris-bot --lines 50
pm2 restart polaris-bot
pm2 monit
```

### Hot reload not picking up skill changes

Use `/reload` in Telegram to force an immediate reload of skills and prompt files without restarting the bot.

---

## Roadmap

### Completed

- Core ReAct router (Ollama local, Anthropic opt-in, dual-model routing)
- 13 tools across 5 modules with auto-discovery registry
- 3-tier ApprovalGate with Telegram inline keyboard
- SQLite audit trail (TraceLogger)
- Second Brain: semantic memory, feedback loop, fact extractor, Obsidian vault indexer
- Markdown-based skill system (9 skills, trigger matching, tool enforcement)
- Apple Mail integration (MailOps) — multi-account, 4-category classifier
- MailOps urgent polling and Telegram push alerts
- HPC monitoring: SSH status, PBS/Slurm queue parser, multi-cluster profiles
- iCloud CalDAV calendar integration
- Bot runtime hot reload (skills and prompt files, no restart)
- External skill support (POLARIS_EXTERNAL_SKILLS path scanning)
- 260+ automated tests, all pass without API keys

### In Progress

- Hallucination reduction in `requires_tool=false` paths and general conversation routing
- Automatic follow-up questions when required tool arguments are missing (currently returns a block response)
- Tool failure retry and fallback path policy

### Planned

- Prompt self-improvement (Judge LLM evaluates few-shot quality, updates `99_SYSTEM` section)
- Knowledge graph for long-term research memory (semantic retrieval of past discussions)
- Multi-cluster live job dashboard
- Schedule Agent: event creation via natural language

---

## Deprecated

The following files are scheduled for removal on **2026-04-15**. They remain in the repository for reference only and should not be used for new development.

| File | Replaced By | Notes |
|------|-------------|-------|
| `polaris_bot.py` | `polaris/bot_v2.py` | Legacy keyword-based bot |
| `orchestrator.py` | `polaris/router.py` | Legacy intent router |

Do not modify these files. See `CLAUDE.md` for the policy on root-level `.py` files.

---

## Acknowledgments

- **Ollama** — local LLM inference (https://ollama.ai)
- **llama3.3:70b / llama3.1:8b** — Meta's open models
- **nomic-embed-text** — local embeddings
- **Claude (Anthropic)** — optional high-quality backend
- **python-telegram-bot** — Telegram integration
- **PM2** — production process manager
- **Obsidian** — personal knowledge management vault

---

## Contact

**Maintainer**: jongmin6301@gmail.com

**Issues**: [GitHub Issues](https://github.com/yourusername/Polaris-Agent-System/issues)

---

*Polaris v0.7 (beta) — Built for the research community*
