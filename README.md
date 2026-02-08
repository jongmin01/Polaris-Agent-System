# 🌟 Polaris Agent System

> *Your intelligent research automation platform*

[![Version](https://img.shields.io/badge/version-0.5%20(alpha)-blue.svg)](https://github.com/yourusername/Polaris-Agent-System)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Polaris** is a hierarchical AI agent system designed to automate PhD research workflows through intelligent task routing, natural language processing, and seamless integration with research tools. It provides automated email triage, academic paper management, and HPC job monitoring through a unified Telegram interface.

---

## 📖 Overview

Polaris automates research workflows using a hierarchical AI agent architecture with four core subsystems:

- **Email Agent**: Intelligent email classification with interactive feedback loop
- **PhD Agent**: Automated academic paper search and analysis
- **Physics Agent**: HPC job monitoring for computational research
- **Schedule Agent**: Multi-calendar integration with iCloud CalDAV (Phase 1.5)

All functionality is accessible through a mobile-friendly Telegram interface, enabling researchers to manage their workflows from anywhere.

---

## ✨ Features

### 📧 Email Agent (Phase 1.1 - Feedback Loop)

**Intelligent Email Triage**
- Binary classification: **ACTION** (requires reply/deadline/request) vs **FYI** (informational)
- Automatic reply draft generation for ACTION emails
- Mail.app integration via AppleScript with preflight diagnostics
- Gemini 2.5 Flash LLM classification

**Interactive Feedback Loop** (Phase 1.1)
- Hash-based email identification (`[#xxxx]`)
- Real-time classification correction via `/wrong` command
- Automatic category flipping (ACTION ↔ FYI)
- Audit trail in `corrections.jsonl` for continuous learning
- Race condition guards and atomic write order

**Storage**
- Local-first architecture (`data/emails/`)
- Markdown format with YAML frontmatter
- Gemini-powered summaries and reply drafts

### 📚 PhD Agent

**Paper Management**
- arXiv paper search and retrieval
- LLM-powered analysis (Gemini 2.5 Flash / Claude Sonnet 4.5)
- Obsidian PKM integration
- Citation formatting

### 🔬 Physics Agent (Phase 1.2 - HPC Monitoring)

**VASP Job Monitoring**
- Real-time job status tracking on HPC clusters
- SSH ControlMaster for persistent MFA authentication (12-hour sessions)
- Hierarchical monitoring pipeline:
  1. Job queue status (`qstat`)
  2. File modification time (`stat`)
  3. SCF iteration progress (`OSZICAR`)
  4. Convergence detection (`OUTCAR`)

**Features**
- Zombie guard (10s SSH timeout)
- MFA session detection and alerts
- Automatic hourly monitoring
- Manual status checks via Telegram
- Convergence notifications

**Supported Platforms**
- ALCF Polaris (tested)
- Other HPC systems with PBS/Torque (adaptable)

### 📅 Schedule Agent (Phase 1.5 - iCloud Calendar Integration)

**Multi-Calendar Management**
- Automatic discovery and search across all iCloud calendars
- Excludes Reminders calendar automatically
- CST timezone (America/Chicago) for accurate time calculations
- Today and tomorrow briefing in a single view

**Smart Display Features**
- Calendar source labels: `[Calendar Name] Event Title`
- Time-sorted events across all calendars
- All-day event indicators: `[종일]`
- Location display with 📍 icon
- Markdown-safe output (underscore escaping)

**User-Friendly Messages**
- Empty schedule: "☕ 예정된 일정이 없습니다."
- Clear time ranges: `09:00-10:00`
- CST timestamp: `(2026-02-07 16:30 CST)`

**Integration**
- iCloud CalDAV protocol
- Non-blocking async calls
- Natural language support: "내일 일정 알려줘"
- Command interface: `/schedule`

### 🤖 Orchestrator

- Intent-based routing with confidence scoring
- Natural language understanding
- Context-aware agent selection

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         Telegram Bot Interface          │
│            (@YourBotName)               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│       Orchestrator (Intent Router)       │
│  - Natural language classification       │
│  - Confidence scoring                    │
└──────┬───────────────────────────────────┘
       │
       ├─────► Email Agent (Phase 1.1) ✅
       │         ├─► Mail.app + AppleScript
       │         ├─► Gemini 2.5 Flash (ACTION/FYI)
       │         ├─► Feedback Loop (Hash IDs + /wrong)
       │         └─► Local Storage (data/emails/)
       │
       ├─────► PhD Agent ✅
       │         ├─► arXiv Search
       │         ├─► LLM Analysis
       │         └─► Obsidian Integration
       │
       ├─────► Physics Agent (Phase 1.2) ✅
       │         ├─► SSH ControlMaster (MFA persistence)
       │         ├─► Job Monitoring (qstat → stat → tail → grep)
       │         ├─► VASP Convergence Detection
       │         └─► Telegram Alerts
       │
       └─────► Schedule Agent (Phase 1.5) ✅
                 ├─► iCloud CalDAV Integration
                 ├─► Multi-Calendar Search (CST timezone)
                 ├─► Calendar Labels & Time Sorting
                 └─► Markdown-Safe Output
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+**
- **macOS** (for Mail.app integration) or **Linux** (for HPC monitoring only)
- **PM2** (for 24/7 operation): `npm install -g pm2`
- **Telegram Account**
- **API Keys**:
  - Gemini API (required) - Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
  - Claude API (optional) - Get from [Anthropic Console](https://console.anthropic.com/)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/Polaris-Agent-System.git
cd Polaris-Agent-System

# Install Python dependencies
pip3 install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your API keys and Telegram bot token
```

### Environment Configuration

Edit `.env` with your credentials:

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# LLM APIs
GEMINI_API_KEY=your_gemini_api_key
CLAUDE_API_KEY=your_claude_api_key  # Optional

# Paths (adjust to your system)
OBSIDIAN_PATH=~/Documents/Obsidian

# iCloud Calendar (Phase 1.5)
ICLOUD_USERNAME=your_apple_id@icloud.com
ICLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # Generate at appleid.apple.com
```

### SSH Configuration (For Physics Agent)

Create or edit `~/.ssh/config`:

```bash
Host your-hpc-cluster
    HostName your-cluster.example.com
    User <your_id>
    ControlMaster auto
    ControlPath ~/.ssh/%r@%h:%p
    ControlPersist 12h
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

**Initial Authentication** (required once per 12 hours):
```bash
ssh your-hpc-cluster
# Enter password + MFA token
# Connection will persist for 12 hours via ControlMaster
```

### Quick Start

**Option 1: Direct Run (Testing)**
```bash
python3 polaris_bot.py
```

**Option 2: PM2 (Recommended for 24/7)**
```bash
# Start with PM2
pm2 start polaris_bot.py --name "polaris-bot" --interpreter python3

# Save PM2 configuration
pm2 save

# Configure PM2 to start on boot
pm2 startup
# Follow the generated command
```

**Test the Bot**
1. Open Telegram and find your bot (`@YourBotName`)
2. Send `/start` to initialize
3. Try `/help` to see available commands

---

## 📖 Usage

### Telegram Commands

#### Basic Commands
| Command | Description |
|---------|-------------|
| `/start` | Welcome message and initialization |
| `/help` | Show all available commands |
| `/status` | System health and component status |

#### Email Agent
| Command | Description |
|---------|-------------|
| `/mail` | Check and classify unread emails (ACTION/FYI) |
| `/wrong <hash> [ACTION\|FYI]` | Correct email classification (Phase 1.1) |

**Email Feedback Examples:**
```
/wrong a3f2 ACTION     # Change email #a3f2 to ACTION
/wrong a3f2 FYI        # Change email #a3f2 to FYI
/wrong a3f2            # Auto-flip current classification
```

#### PhD Agent
| Command | Description |
|---------|-------------|
| `/search <query>` | Search papers on arXiv |
| `/download <number>` | Download selected paper |
| `/analyze` | Analyze paper with LLM |

#### Physics Agent (Phase 1.2)
| Command | Description |
|---------|-------------|
| `/physics <job_id> <path>` | Register VASP job for monitoring |
| `/physics_check <job_id>` | Manual status check |
| `/physics_list` | List all registered jobs |

**Physics Agent Examples:**
```
# Register a job for monitoring (checks every hour)
/physics 12345 /path/to/vasp/calculation

# Manual status check (immediate)
/physics_check 12345

# List all monitored jobs
/physics_list
```

#### Schedule Agent (Phase 1.5)
| Command | Description |
|---------|-------------|
| `/schedule` | View today and tomorrow's events from all calendars |

**Schedule Agent Examples:**
```
# Check today and tomorrow's schedule
/schedule

# Natural language (auto-routed to Schedule Agent)
"내일 일정 알려줘"
"오늘 일정 확인"
```

**Output Format:**
```
📅 일정 브리핑 (2026-02-07 16:30 CST)

📌 오늘
1. 09:00-10:00 - [Work] Daily Standup
   📍 Zoom
2. [종일] - [Personal] Team Workshop

📌 내일
☕ 예정된 일정이 없습니다.
```

### Natural Language

You can use natural language for various tasks:

**PhD Agent (Paper Search)**
```
"Search for MoS2 papers"
"Analyze this Janus TMDC paper"
"Find recent papers on valleytronics"
```

**Schedule Agent (Calendar)**
```
"내일 일정 알려줘"
"오늘 일정 확인"
"일정 알려줘"
```

**Note**: Email and Physics commands use explicit command syntax for precision.

---

## 📂 Project Structure

```
Polaris_Agent_System/
├── polaris_bot.py              # Main Telegram bot
├── orchestrator.py             # Intent classification & routing
├── phd_agent.py                # PhD workflow coordinator
├── email_analyzer.py           # Email classification (Gemini)
├── mail_reader.py              # Mail.app wrapper
├── read_mail.scpt              # AppleScript for Mail.app
├── physics_monitor.py          # HPC job monitoring (Phase 1.2)
├── schedule_agent.py           # iCloud Calendar integration (Phase 1.5)
├── paper_workflow.py           # arXiv integration
├── strings.py                  # Internationalization
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
├── prompts/
│   └── email_classify.txt      # Email classification prompt (Phase 1.1)
├── data/
│   ├── emails/                 # Local email storage
│   ├── feedback/               # Classification corrections (Phase 1.1)
│   │   └── corrections.jsonl   # Audit trail
│   └── physics/                # Physics monitoring data (Phase 1.2)
│       └── active_jobs.json    # Registered HPC jobs
├── logs/
│   ├── physics.log             # Physics agent logs
│   └── pm2_*.log               # PM2 process logs
└── docs/                       # Documentation
    ├── Polaris_System_Architecture.md
    └── PM2_MIGRATION.md
```

---

## 🔧 Configuration

### Email Classification Rules

**ACTION** 🔴 - Requires immediate attention
- Needs a reply (student questions, professor requests)
- Has a deadline (assignment due, meeting RSVP)
- Explicit request from supervisor or collaborator
- Grade disputes, clarifications, office hour requests
- Research task assignments

**FYI** ℹ️ - Informational only
- General announcements (optional seminars)
- Newsletters, department updates
- Automated notifications (Gradescope, system messages)
- Promotional emails
- Updates from professors (no action required)

**Decision Logic:**
- Question in email → ACTION
- Requires you to do something → ACTION
- Has deadline/RSVP → ACTION
- Purely informational → FYI
- When uncertain → ACTION (better to over-triage)

### Email Markdown Format

Emails are stored as markdown files with YAML frontmatter:

```markdown
---
category: ACTION
hash: a3f2                    # Phase 1.1: 4-char unique ID
user_corrected: false        # Phase 1.1: Feedback flag
importance: 4
sender: sender@example.com
date: Wed, 7 Feb 2026 10:30:00
account: Work
tags: [email, action]
---

# [Subject]

**Category**: ACTION
**Importance**: ⭐⭐⭐⭐

## 📧 Email Content
[Body]

## 🤖 AI Analysis
**Summary**: [Gemini summary in user's language]

## ✍️ Reply Draft
[Auto-generated reply for ACTION emails]
```

### Physics Agent Monitoring Hierarchy

The Physics Agent uses a four-step hierarchy to determine job status:

1. **Queue Check** (`qstat -u <user>`)
   - Verifies job is in PBS/Torque queue
   - Detects job state (Running, Queued, etc.)

2. **File Modification** (`stat -c %Y OUTCAR`)
   - Checks when OUTCAR was last modified
   - Detects stalled calculations (>10 min since update)

3. **Progress Parsing** (`tail -1 OSZICAR`)
   - Extracts current SCF step and energy
   - Format: `Step 150, E=-123.456789 eV`

4. **Convergence Check** (`grep "reached required accuracy" OUTCAR`)
   - Detects successful completion
   - Triggers completion notification

**Zombie Guard**: 10-second SSH timeout prevents hung connections

**MFA Detection**: Recognizes expired authentication sessions

---

## 📊 System Status

| Component | Status | Version | Notes |
|-----------|--------|---------|-------|
| Telegram Bot | ✅ Active | v0.5 | PM2: `polaris-bot` |
| Email Agent | ✅ Active | Phase 1.1 | Feedback Loop + Hash IDs |
| PhD Agent | ✅ Active | v0.2 | arXiv + Obsidian |
| Physics Agent | ✅ Active | Phase 1.2 | HPC Monitoring (VASP) |
| Schedule Agent | ✅ Active | Phase 1.5 | iCloud CalDAV (Multi-calendar, CST) |
| Orchestrator | ✅ Active | v0.2 | Intent routing |

**Last Update**: February 7, 2026

---

## 🐛 Troubleshooting

### Email Agent Issues

**Mail.app Not Reading Emails**
```bash
# Check logs
pm2 logs polaris-bot

# Grant permissions
# macOS: System Preferences → Security & Privacy → Automation
# Enable Mail.app access for Terminal/Python

# Verify Mail.app is running and synced
open -a Mail
```

**Email Files Not Saving**
```bash
# Verify data directory exists
ls -la data/emails/

# Create if missing
mkdir -p data/emails
```

### Physics Agent Issues

**SSH Connection Failed** (`💀 SSH 연결 실패`)
```bash
# Authenticate MFA (required once per 12 hours)
ssh your-hpc-cluster

# Test connection
ssh your-hpc-cluster "echo heartbeat"

# Check ControlMaster
ls -la ~/.ssh/*@*
```

**MFA Session Expired** (`🔐 MFA 세션 만료`)
```bash
# Kill existing ControlMaster
rm ~/.ssh/*@your-cluster*

# Re-authenticate
ssh your-hpc-cluster
```

**Job Not Found**
- Verify job ID: `ssh your-hpc-cluster "qstat -u <your_id>"`
- Check path is correct: `ssh your-hpc-cluster "ls -la /path/to/vasp"`

### General Issues

**PM2 Process Crashes**
```bash
# Check logs
pm2 logs polaris-bot --lines 50

# Restart
pm2 restart polaris-bot

# Monitor status
pm2 monit
```

**Gemini API Errors**
- Verify API key in `.env`
- Check quota: [Google AI Studio](https://makersuite.google.com/app/apikey)
- Use `gemini-2.5-flash` (not experimental versions)

---

## 🗺️ Roadmap

### Completed ✅

**Phase 0: Foundation**
- [x] Telegram bot interface
- [x] PhD-Agent (paper search and analysis)
- [x] Email-Agent (ACTION/FYI classification)
- [x] Mail.app integration with AppleScript
- [x] PM2 process management
- [x] Local email storage

**Phase 1.1: Feedback Loop**
- [x] Hash-based email identification
- [x] `/wrong` command for corrections
- [x] Audit trail (`corrections.jsonl`)
- [x] Atomic write order (crash-safe)
- [x] Race condition guards

**Phase 1.2: Physics Agent**
- [x] HPC job monitoring (VASP)
- [x] SSH ControlMaster (MFA persistence)
- [x] Hierarchical monitoring pipeline
- [x] Convergence detection
- [x] Telegram alerts

**Phase 1.5: Schedule Agent**
- [x] iCloud CalDAV integration
- [x] Multi-calendar automatic discovery
- [x] CST timezone support (America/Chicago)
- [x] Calendar source labels
- [x] Time-sorted event aggregation
- [x] Markdown-safe output (underscore escaping)
- [x] Natural language routing ("내일 일정 알려줘")

### In Progress 🚧
- [ ] Email classification prompt tuning (using feedback data)
- [ ] Physics Agent: Support for other DFT codes (ONETEP, Quantum ESPRESSO)
- [ ] Multi-cluster support (add NERSC, OLCF)
- [ ] Schedule Agent: Event creation via natural language

### Planned 📋

**Phase 1.3: Learning Pipeline**
- [ ] Gemini fine-tuning with `corrections.jsonl` data
- [ ] Classification accuracy metrics
- [ ] Weekly performance reports

**Phase 2: Advanced Features**
- [ ] Physics Agent: Automatic job submission
- [ ] Physics Agent: Result visualization
- [ ] Email Agent: Multi-category classification
- [ ] Email Agent: Scheduled checks
- [ ] Obsidian PARA integration

**Phase 3: Ecosystem**
- [ ] Life-Agent (calendar, reminders, daily planning)
- [ ] Personal-Agent (finance, health tracking)
- [ ] Local LLM support (Llama, Mistral)
- [ ] Web dashboard (monitoring and control)

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Commit your changes**: `git commit -m 'Add amazing feature'`
4. **Push to the branch**: `git push origin feature/amazing-feature`
5. **Open a Pull Request**

**Areas for Contribution:**
- Additional HPC platform support (NERSC, OLCF, etc.)
- Support for other DFT codes (Quantum ESPRESSO, CP2K, etc.)
- Email classification prompt improvements
- Documentation and tutorials
- Testing and bug reports

---

## 📚 Documentation

- **[System Architecture](docs/Polaris_System_Architecture.md)**: Complete technical documentation
- **[PM2 Migration Guide](docs/PM2_MIGRATION.md)**: PM2 setup and management
- **Phase 1.1 Spec**: Feedback Loop implementation details (see `outputs/`)
- **Phase 1.2 Spec**: Physics Agent implementation details (see `outputs/`)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

**Technologies**
- **Gemini 2.5 Flash** by Google - Fast and free LLM inference
- **Claude Sonnet 4.5** by Anthropic - High-quality analysis
- **Telegram Bot API** - Reliable messaging platform
- **PM2** - Production process manager

**Methodologies**
- **PARA Method** by Tiago Forte - Knowledge organization framework
- **Obsidian** - Personal knowledge management

**Inspiration**
- Research automation workflows from the computational physics community
- Academic productivity systems

---

## 📞 Contact

**Project Repository**: [GitHub](https://github.com/yourusername/Polaris-Agent-System)

**Issues & Feature Requests**: [GitHub Issues](https://github.com/yourusername/Polaris-Agent-System/issues)

**Telegram Bot**: `@YourBotName` (replace with your bot username)

---

<div align="center">

**Polaris v0.5 (Alpha)** - Built with ❤️ and AI

*"Your guiding star for research automation"* ⭐

**Empowering Researchers Worldwide**

---

Made for the research community | Open Source | MIT License

</div>
