# Polaris Agent System - Development Guide

## Project Overview

Polaris is a hierarchical AI agent system for PhD research workflow automation.
Telegram bot interface with multi-agent architecture (Email, PhD, Physics, Schedule agents).

- **Language**: Python 3.9+
- **Primary LLM**: Gemini 2.5 Flash
- **Fallback LLM**: Claude Sonnet 4.5 (optional)
- **Interface**: Telegram Bot API
- **Process Manager**: PM2
- **Knowledge Base**: Obsidian (PARA method)
- **Platform**: macOS (Mac mini, 24/7)

## Architecture

```
Telegram Bot → Orchestrator (Intent Router)
  ├── Email Agent    (Phase 1.1) - Mail.app + AppleScript + Gemini
  ├── PhD Agent      (v0.2)     - arXiv + Semantic Scholar + Obsidian
  ├── Physics Agent  (Phase 1.2) - HPC/VASP monitoring + SSH ControlMaster
  └── Schedule Agent (Phase 1.5) - iCloud CalDAV multi-calendar
```

## Key Files

| File | Description |
|------|-------------|
| `polaris_bot.py` | Main Telegram bot handler (entry point) |
| `orchestrator.py` | Intent classification & agent routing |
| `email_analyzer.py` | Gemini email classification (ACTION/FYI/UNCERTAIN) |
| `mail_reader.py` | Mail.app AppleScript wrapper |
| `physics_monitor.py` | HPC job monitoring pipeline |
| `physics_agent.py` | DFT/VASP handler |
| `schedule_agent.py` | iCloud Calendar integration |
| `phd_agent.py` | Paper search & analysis coordinator |
| `paper_workflow.py` | arXiv + Semantic Scholar integration |
| `rlm_wrapper.py` | Phase 1.3 RLM ensemble voting |
| `strings.py` | Internationalization (Korean/English) |
| `prompts/email_classify.txt` | Email classification prompt |

## Data Storage

All runtime data is in `data/` (gitignored):

```
data/
├── emails/                  # Email markdown files (YAML frontmatter)
├── feedback/
│   └── corrections.jsonl    # Email classification audit trail
├── physics/
│   └── active_jobs.json     # Registered HPC jobs
└── master_prompt.md         # System prompt source (MASTER_PROMPT_PATH)
```

## Environment Variables

See `.env.example`. Key variables:

- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `GEMINI_API_KEY` - Google Gemini API key
- `ANTHROPIC_API_KEY` - Claude API key (optional)
- `OBSIDIAN_PATH` - Obsidian vault root path
- `MASTER_PROMPT_PATH` - master_prompt.md location (default: `data/master_prompt.md`)
- `RLM_ENABLED` - Phase 1.3 ensemble voting toggle
- `ICLOUD_USERNAME` / `ICLOUD_APP_PASSWORD` - Calendar integration

## Coding Conventions

- Korean comments and user-facing strings (strings.py for i18n)
- Async/await throughout (Telegram bot is async)
- File-based storage (Markdown + JSON/JSONL, no traditional DB)
- Hash IDs: 4-char MD5 for email identification
- Race condition guards: 5s file modification guard, 30s double-logging guard
- Atomic write order: .md first, corrections.jsonl second

## Testing

```bash
pytest                    # Run all tests
pytest test_*.py          # Test files are gitignored but exist locally
```

## Deployment

```bash
pm2 start polaris_bot.py --name "polaris-bot" --interpreter python3
pm2 save && pm2 startup
```

---

## Development Progress

### Phase 0: Foundation ✅
- [x] Telegram bot interface
- [x] PhD-Agent (paper search and analysis)
- [x] Email-Agent (ACTION/FYI classification)
- [x] Mail.app integration with AppleScript
- [x] PM2 process management
- [x] Local email storage (data/emails/)

### Phase 1.1: Email Feedback Loop ✅
- [x] Hash-based email identification ([#xxxx])
- [x] `/wrong` command for corrections
- [x] Audit trail (corrections.jsonl)
- [x] Atomic write order (crash-safe)
- [x] Race condition guards

### Phase 1.2: Physics Agent ✅
- [x] HPC job monitoring (VASP)
- [x] SSH ControlMaster (MFA persistence, 12h sessions)
- [x] Hierarchical monitoring (qstat → stat → OSZICAR → OUTCAR)
- [x] Convergence detection
- [x] Telegram alerts
- [x] Zombie guard (10s SSH timeout)

### Phase 1.3: RLM Ensemble ✅
- [x] Ensemble voting (parallel inferences)
- [x] Confidence threshold → UNCERTAIN category
- [x] Audit logging (logs/rlm_audit.log)
- [x] SSHStealth (daily connection limits + jitter)

### Phase 1.5: Schedule Agent ✅
- [x] iCloud CalDAV integration
- [x] Multi-calendar auto-discovery
- [x] CST timezone (America/Chicago)
- [x] Calendar source labels & time sorting
- [x] Markdown-safe output (underscore escaping)
- [x] Natural language routing

### Phase 2: Advanced Features ✅
- [x] SQLite memory storage (conversation DB)
- [x] Semantic search (nomic-embed-text via Ollama)
- [x] Obsidian vault path update (iCloud~md~obsidian)
- [x] master_prompt.md integration (00_CORE → system prompt injection)
- [x] 99_CURRENT_CONTEXT auto-update (first call auto-generates section)
- [x] MASTER_PROMPT_PATH configuration (data/master_prompt.md)
- [x] 93 tests passing

### Phase 3: Planned
- [ ] Life-Agent (calendar, reminders, daily planning)
- [ ] Personal-Agent (finance, health tracking)
- [ ] Local LLM support (Llama, Mistral)
- [ ] Web dashboard (monitoring and control)
- [ ] Physics Agent: automatic job submission
- [ ] Physics Agent: result visualization
- [ ] Multi-cluster support (NERSC, OLCF)
