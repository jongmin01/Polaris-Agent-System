# Polaris Agent System - Architecture Documentation

> **당신의 연구를 안내하는 북극성 ⭐**
>
> PhD 연구 자동화를 위한 계층적 AI 에이전트 시스템

**Version**: 0.3 (Email-Agent Phase 2 완료)
**Last Updated**: 2026-02-04
**Author**: 종민 (Jongmin Baek)

---

## 🎯 System Overview

Polaris는 PhD 학생의 연구 업무를 자동화하는 계층적 AI 에이전트 시스템입니다. Telegram 인터페이스를 통해 논문 검색, TA 메일 관리, DFT 계산 등을 통합 관리합니다.

### Core Architecture

```
┌─────────────────────────────────────────┐
│         Telegram Bot Interface          │
│        (@MyPolaris_bot)                 │
└──────────────┬──────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│       Orchestrator (Intent Router)       │
│  - Keyword-based classification          │
│  - Confidence scoring                    │
└──────┬───────────────────────────────────┘
       │
       ├─────► PhD-Agent (Paper Workflow)
       │         └─► arXiv API + Gemini/Claude
       │
       ├─────► Email-Agent (Phase 2) ✅
       │         ├─► Mail.app (AppleScript)
       │         ├─► Gemini 2.5 Flash (Classification)
       │         └─► Obsidian (PARA Integration)
       │
       ├─────► Physics-Agent (DFT/VASP/ONETEP) ⏸️
       │
       └─────► Life-Agent / Personal-Agent (Planned) ⏸️
```

---

## 🧠 Core AI Model

### Primary LLM Engine

**Model**: `gemini-2.5-flash`
**Provider**: Google Generative AI
**Usage**: Email classification, TA reply generation, paper analysis

**Why Gemini 2.5 Flash?**
- ✅ Latest stable model (as of Feb 2026)
- ✅ Free tier with generous quota
- ✅ Fast response time (~1-2s)
- ✅ Strong multilingual support (Korean/English)
- ✅ Excellent instruction following

**Fallback Models**:
- `claude-sonnet-4.5` (paid, for critical paper analysis)
- Future: Local LLM integration planned

### Model Selection History

| Version | Model | Status | Notes |
|---------|-------|--------|-------|
| 0.1 | `gemini-2.0-flash-exp` | ❌ 404 Error | Experimental, unstable |
| 0.2 | `gemini-1.5-flash` | ⚠️ Deprecated | Older generation |
| 0.3 | `gemini-2.5-flash` | ✅ **Active** | Latest stable |

---

## 📁 Directory Structure

### Root Directory

```
~/Desktop/Polaris_Agent_System/
├── polaris_bot.py              # Telegram bot main entry
├── orchestrator.py             # Intent classification & routing
├── phd_agent.py                # PhD workflow coordinator
├── email_analyzer.py           # ✅ Email classification + Gemini
├── mail_reader.py              # Mail.app AppleScript wrapper
├── read_mail.scpt              # AppleScript for Mail.app
├── paper_workflow.py           # arXiv + Obsidian integration
├── physics_agent.py            # DFT/VASP/ONETEP handler (준비중)
├── .env                        # API keys, Obsidian path
├── requirements.txt            # Python dependencies
├── logs/                       # PM2 logs
│   ├── pm2.log
│   └── pm2_error.log
└── docs/                       # 📄 Documentation
    ├── Polaris_System_Architecture.md  # This file
    ├── EMAIL_AGENT_ROADMAP.md
    └── PM2_MIGRATION.md
```

### Obsidian Vault (PARA Structure)

**Vault Name**: `My Second Brain`
**Base Path**: `/Users/jongmin/Library/Mobile Documents/iCloud~md~obsidian/Documents/`

```
My Second Brain/
├── 00_Inbox/                   # 🎯 Active Inbox (PARA)
│   └── Emails/                 # ✅ Email-Agent saves here
│       ├── 260204_Last_Days_to_Apply_ois.md
│       ├── 260204_PHYS_142_Homework_student123.md
│       └── ...
├── 01_Projects/                # Active research projects
├── 02_Areas/                   # Areas of responsibility
├── 03_Resources/               # Reference materials
└── 04_Archive/                 # Completed items
```

**Critical Path Configuration**:
```python
# email_analyzer.py (Line 62-63)
self.obsidian_path = Path(obsidian_base) / "My Second Brain"
self.emails_folder = self.obsidian_path / "00_Inbox" / "Emails"
```

⚠️ **Common Mistake**: Using `00. Inbox` (with space) instead of `00_Inbox` (with underscore)

---

## 📧 Email-Agent (Phase 2) - Detailed Logic

### Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  1. Mail.app (AppleScript)                      │
│     └─► read_mail.scpt                          │
│         - Account: "UIC"                        │
│         - Mailbox: "받은 편지함" (Korean)        │
│         - Limit: 5 unread emails                │
└──────────────┬──────────────────────────────────┘
               │ MailReader.get_unread_mails()
               ▼
┌─────────────────────────────────────────────────┐
│  2. Email Analyzer (Gemini 2.5 Flash)          │
│     └─► email_analyzer.py                       │
│         - Classification (4 categories)         │
│         - TA reply draft generation             │
│         - Importance scoring (1-5)              │
└──────────────┬──────────────────────────────────┘
               │ EmailAnalyzer.analyze_batch()
               ▼
┌─────────────────────────────────────────────────┐
│  3. Obsidian Integration                        │
│     └─► save_to_obsidian()                      │
│         - Filename: YYMMDD_제목_발신자.md       │
│         - Sanitize forbidden characters         │
│         - Markdown with YAML frontmatter        │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│  4. Telegram Output                             │
│     └─► format_categorized_summary()            │
│         - Category grouping                     │
│         - Importance stars (⭐)                  │
│         - TA reply preview                      │
└─────────────────────────────────────────────────┘
```

### Classification Rules

#### 1. [TA/수업] - Teaching Assistant & Class

**Must Classify Conditions** (Highest Priority):
```python
# Subject Keywords (Case Insensitive)
keywords = ["PHYS", "Lab", "Grade", "Homework", "Assignment", "Exam", "Quiz"]

# Student Question Patterns
patterns = [
    "Can you help?",
    "I have a question",
    "Could you explain?",
    "How do I...",
]

# Special Cases
- Gradescope notifications → [TA/수업] (during testing period)
- Student email tone detection → [TA/수업]
```

**Example Emails**:
- ✅ `Subject: PHYS 142 - Question about Homework 3`
- ✅ `Subject: Lab Report Submission` (from student@uic.edu)
- ✅ `Gradescope: New submission uploaded`

**Output Features**:
- Category tag: `[TA/수업]`
- Reply draft generated (Korean or English, auto-detected)
- Saved to Obsidian with `tags: [email, TA/수업]`

#### 2. [연구/교수님] - Research & Professors

**Classification Criteria**:
```python
# Sender Patterns
professor_domains = ["faculty.uic.edu", "known professor emails"]

# Research Keywords
research_keywords = [
    "DFT", "VASP", "ONETEP",
    "2D Materials", "TMDC", "MoS2", "WS2",
    "band structure", "DOS", "density of states",
    "calculation", "simulation", "relaxation"
]

# Context Patterns
- Calculation requests
- Research group discussions
- Thesis/paper feedback
- Collaboration proposals
```

**Example Emails**:
- ✅ `Subject: DFT calculation request for MoS2 bilayer`
- ✅ `Subject: Paper draft comments` (from professor@uic.edu)
- ✅ `Subject: VASP job submission status`

**Output Features**:
- Category tag: `[연구/교수님]`
- High importance score (usually 4-5 ⭐)
- Always saved to Obsidian

#### 3. [학과 공지] - Department Announcements

**Strict Classification Rules**:
```python
# Domain Check (Required)
required_domain = "@uic.edu"

# AND Keyword Matching
announcement_keywords = {
    "Seminar": ["colloquium", "seminar", "talk", "speaker", "lecture"],
    "Events": ["cookies", "coffee hour", "department meeting", "town hall"],
    "Admin": ["OIS", "International Services", "registration",
              "graduate college", "deadline", "policy"]
}

# Pattern: MUST be from @uic.edu AND contain at least one keyword
if sender.endswith("@uic.edu") and any(keyword in subject.lower()):
    return "[학과 공지]"
```

**Example Emails**:
- ✅ `Subject: Physics Colloquium - This Friday` (from physics@uic.edu)
- ✅ `Subject: Last Days to Apply! | Intercultural Connections` (from ois.uic.edu)
- ✅ `Subject: Cookies with the Department Chair` (from dept@uic.edu)

**Output Features**:
- Category tag: `[학과 공지]`
- Importance: 3-4 ⭐ (time-sensitive)
- Saved to Obsidian for reference

#### 4. [기타] - Other

**Fallback Category** (Only if none of above apply):
```python
# Examples of [기타]
- Commercial advertisements
- General newsletters (not research-related)
- Automated notifications (e.g., social media, services)
- Spam or promotional content
- Unrelated external emails
```

**Example Emails**:
- ✅ `Subject: February Physics Lab Specials` (from vendor@company.com)
- ✅ `Subject: LinkedIn: You have 5 new connections`
- ✅ `Subject: Black Friday Sale - 50% off!`

**Output Features**:
- Category tag: `[기타]`
- Low importance: 1-2 ⭐
- Still saved during testing period

### TA Reply Draft Generation

**Triggered**: Only for `[TA/수업]` emails

**Language Detection**:
```python
# Auto-detect from student email
if contains_korean(student_email):
    language = "Korean"
else:
    language = "English"
```

**Reply Style Guidelines**:
```
- Warm and encouraging tone
- Address student concerns directly
- Provide clear, concise answers
- Include office hours if relevant
- Sign with "종민" (Korean) or "Jongmin" (English)
```

**Example Output**:
```
Subject: PHYS 142 - Question about Homework 3

안녕하세요!

좋은 질문이에요. 숙제 3번 문제에서 [설명...]

더 궁금한 점이 있으면 언제든지 연락주세요.
오피스 아워: 화요일 2-4pm, SES 설명

종민
```

---

## 🔧 Key Processing Logic

### 1. Filename Sanitization

**Problem**: macOS filesystem forbids certain characters in filenames
**Solution**: Replace all forbidden characters with underscores

```python
# email_analyzer.py (Lines 216-223)
def sanitize_filename(filename: str) -> str:
    """
    Remove filesystem-forbidden characters
    Critical for UIC emails with colons (:) in subjects
    """
    forbidden_chars = [':', '/', '\\', '?', '*', '<', '>', '|', '"', "'"]

    for char in forbidden_chars:
        filename = filename.replace(char, '_')

    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')

    return filename
```

**Example Transformations**:
```
Original:  "PHYS 142: Homework 3 Due"
Sanitized: "PHYS 142_ Homework 3 Due"

Original:  "Last Days to Apply! | Intercultural Connections"
Sanitized: "Last Days to Apply_ _ Intercultural Connections"

Original:  "Re: Question about Lab <urgent>"
Sanitized: "Re_ Question about Lab _urgent_"
```

**Filename Format**:
```
YYMMDD_<sanitized_subject>_<sender_name>.md

Examples:
260204_PHYS_142__Homework_3_Due_student123.md
260204_Last_Days_to_Apply___ois.md
```

### 2. Forced Save During Testing

**Rationale**: Build training data for classification accuracy

```python
# email_analyzer.py (Line 156)
result = {
    'category': EmailCategory.OTHER,
    'importance': 1,
    'summary': '',
    'should_save': True  # 🔥 Always True during testing
}
```

**Prompt Enforcement**:
```
**Response Format (strictly follow):**
CATEGORY: [one of the 4 categories above]
IMPORTANCE: [1-5, where 5=urgent/important, 1=low priority]
SUMMARY: [one sentence summary in Korean]
SHOULD_SAVE: YES  ← Hardcoded during testing

Note: During testing period, SHOULD_SAVE is always YES to build training data.
```

**Future**: After sufficient training data (50+ emails per category), switch to importance-based saving:
```python
should_save = (importance >= 3) and (category in [TA_CLASS, RESEARCH])
```

### 3. Markdown File Format

**Generated File Structure**:

```markdown
---
category: [TA/수업]
importance: 4
sender: student@uic.edu
date: Wednesday, February 4, 2026 at 3:15:42 PM
account: UIC
tags: [email, TA/수업]
---

# PHYS 142 - Question about Homework 3

**Category**: [TA/수업]
**Importance**: ⭐⭐⭐⭐
**From**: student@uic.edu
**Date**: Wednesday, February 4, 2026 at 3:15:42 PM
**Account**: UIC

---

## 📧 Email Content

Hi Jongmin,

I have a question about problem 2 in homework 3.
Can you help me understand the concept of...

[Full email content here]

---

## 🤖 AI Analysis

**Summary**: 학생이 숙제 3번 2번 문제에 대해 질문하는 메일입니다.

---

## ✍️ Reply Draft (TA)

안녕하세요!

좋은 질문이에요. 숙제 3번 문제 2번에서...

[Generated reply draft here]

종민
```

### 4. Error Handling & Logging

**Gemini API Failure**:
```python
except Exception as e:
    error_msg = f"❌ Gemini API 오류: {type(e).__name__} - {str(e)}"
    print(error_msg)
    print(f"   Subject: {subject}")
    print(f"   Sender: {sender}")

    # Fallback classification
    return {
        'category': EmailCategory.OTHER,
        'importance': 1,
        'summary': f"[Gemini 분석 실패] {subject[:50]}",
        'reply_draft': None,
        'should_save': True  # Save for manual review
    }
```

**Obsidian Save Failure**:
```python
try:
    self.emails_folder.mkdir(parents=True, exist_ok=True)
    print(f"📁 Obsidian Emails 폴더 확인: {self.emails_folder}")
except Exception as e:
    print(f"❌ Obsidian 폴더 생성 실패: {e}")
    print(f"   경로: {self.emails_folder}")
    return None
```

**Debug Logging**:
```python
# List available models on startup
try:
    available_models = [m.name for m in genai.list_models()]
    print(f"🔍 Available Gemini models: {available_models[:5]}")
except Exception as e:
    print(f"⚠️  Could not list models: {e}")
```

---

## 🚀 Deployment & Operations

### PM2 Process Management

**Why PM2?**
- ✅ No macOS Full Disk Access permission required (unlike launchd)
- ✅ Easy process management (start/stop/restart/logs)
- ✅ Auto-restart on crashes
- ✅ Better logging and monitoring

**Installation**:
```bash
npm install -g pm2
```

**Start Polaris**:
```bash
cd ~/Desktop/Polaris_Agent_System
pm2 start polaris_bot.py --name "polaris-bot" --interpreter python3
```

**Common Commands**:
```bash
# Status check
pm2 status

# View logs (live)
pm2 logs polaris-bot

# Restart after code changes
pm2 restart polaris-bot

# Stop
pm2 stop polaris-bot

# Auto-start on system boot
pm2 startup launchd
pm2 save
```

**Log Locations**:
```
~/Desktop/Polaris_Agent_System/logs/
├── pm2.log          # Combined output
└── pm2_error.log    # Error messages only
```

**Monitoring**:
```bash
# Real-time dashboard
pm2 monit

# Process details
pm2 show polaris-bot
```

### Environment Configuration

**`.env` File** (Required):
```bash
# Telegram Bot Token
TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"

# Gemini API Key (Free tier)
GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"

# Optional: Claude API Key (for paper analysis)
ANTHROPIC_API_KEY=""

# Obsidian Base Path (without "My Second Brain")
OBSIDIAN_PATH="/Users/jongmin/Library/Mobile Documents/iCloud~md~obsidian/Documents"
```

**Python Dependencies** (`requirements.txt`):
```
python-telegram-bot==20.8
google-generativeai>=0.8.0
anthropic>=0.40.0
requests>=2.31.0
python-dotenv>=1.0.0
PyPDF2>=3.0.0
```

**Installation**:
```bash
pip3 install -r requirements.txt
```

### Telegram Bot Commands

**User Commands**:
```
/start         - Welcome message & system overview
/help          - Command reference
/status        - System health check
/check_mail    - Email analysis (Email-Agent Phase 2)
/search <query> - Paper search on arXiv
```

**Natural Language** (Recommended):
```
"MoS2 논문 검색해줘"
"TA 메일 확인"
"Janus TMDC 분석"
```

---

## 📊 System Status

### Active Components ✅

| Component | Status | Version | Notes |
|-----------|--------|---------|-------|
| Telegram Bot | ✅ Active | v0.3 | PM2: `polaris-bot` |
| Orchestrator | ✅ Active | v0.2 | Intent routing |
| PhD-Agent (Paper) | ✅ Active | v0.2 | arXiv + Obsidian |
| Email-Agent | ✅ Active | **v0.3** | Phase 2 완료 |
| Mail.app Bridge | ✅ Active | v3 | Korean mailbox support |
| Gemini API | ✅ Active | 2.5 Flash | Classification + Reply |
| Obsidian Integration | ✅ Active | PARA | 00_Inbox/Emails |

### In Development ⏸️

| Component | Status | Priority | ETA |
|-----------|--------|----------|-----|
| Physics-Agent | ⏸️ Planned | Medium | TBD |
| VASP/ONETEP Handler | ⏸️ Planned | Medium | TBD |
| Email-Agent Phase 3 | ⏸️ Planned | Low | TBD |
| Life-Agent | ⏸️ Planned | Low | TBD |
| Local LLM | ⏸️ Planned | Low | TBD |

### Recent Milestones

**2026-02-04**: Email-Agent Phase 2 완료 🎉
- ✅ Gemini 2.5 Flash 통합
- ✅ 4-category 분류 (TA/수업, 연구/교수님, 학과 공지, 기타)
- ✅ TA 답장 초안 자동 생성
- ✅ Obsidian PARA 구조 통합 (00_Inbox/Emails)
- ✅ 파일명 특수문자 처리 완료
- ✅ Telegram 카테고리별 요약 표시

**2026-02-03**: Email-Agent Phase 1 완료
- ✅ Mail.app AppleScript 연동
- ✅ Korean mailbox ("받은 편지함") 지원
- ✅ /check_mail 명령어 구현

**2026-02-02**: PM2 Migration
- ✅ launchd → PM2 전환 (권한 문제 해결)
- ✅ 24/7 안정 운영 체제 구축

**2026-02-01**: Mac Mini 마이그레이션
- ✅ MacBook Air → Mac Mini 시스템 이전
- ✅ 버그 수정 (Obsidian path, generate_citekey)
- ✅ Physics-Agent 구조 설계

---

## 🔍 Troubleshooting

### Common Issues

#### 1. Gemini API 404 Error

**Problem**: `gemini-2.0-flash-exp` model not found

**Solution**:
```python
# email_analyzer.py (Line 57)
self.model = genai.GenerativeModel('gemini-2.5-flash')  # ✅ Use stable model
```

**Debug**:
```python
# Check available models
import google.generativeai as genai
genai.configure(api_key="YOUR_KEY")
for m in genai.list_models():
    print(m.name)
```

#### 2. Obsidian Files Not Saving

**Problem**: Folder path incorrect or permissions

**Checklist**:
1. ✅ Verify `.env` has correct `OBSIDIAN_PATH`
2. ✅ Ensure `My Second Brain` vault exists
3. ✅ Check folder name: `00_Inbox` (not `00. Inbox`)
4. ✅ Run cleanup script: `./cleanup_obsidian_folders.sh`

**Manual Check**:
```bash
ls -la "/Users/jongmin/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Second Brain/00_Inbox/Emails"
```

#### 3. Mail.app Not Reading Emails

**Problem**: AppleScript permissions or account name

**Checklist**:
1. ✅ Mail.app is running
2. ✅ System Preferences → Security & Privacy → Automation
3. ✅ Grant Python/Terminal access to Mail.app
4. ✅ Verify account keyword: `MailReader(account_keyword="UIC")`

**Debug**:
```bash
# Check account names
osascript -e 'tell application "Mail" to get name of every account'

# Check mailbox names
osascript -e 'tell application "Mail" to get name of every mailbox of account "UIC"'
```

#### 4. PM2 Process Crashes

**Problem**: Python errors or missing dependencies

**Diagnosis**:
```bash
# Check logs
pm2 logs polaris-bot --lines 50

# Restart
pm2 restart polaris-bot

# Full reset
pm2 delete polaris-bot
pm2 start polaris_bot.py --name "polaris-bot" --interpreter python3
```

#### 5. Classification Accuracy Low

**Problem**: All emails classified as [기타]

**Solution**: Check prompt in `email_analyzer.py` (Lines 110-165)

**Training Data**: After 50+ emails per category, analyze misclassifications:
```bash
# Review saved emails
ls -l ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/My\ Second\ Brain/00_Inbox/Emails/

# Check YAML frontmatter for category distribution
grep -r "category:" *.md | sort | uniq -c
```

---

## 🔮 Future Roadmap

### Email-Agent Phase 3 (Planned)

**Features**:
- Scheduled email checks (every 30min via cron/launchd)
- Email action automation (mark as read, archive)
- Smart reply sending (with user approval)
- Context-aware classification (email threads)

### Physics-Agent Integration

**Capabilities**:
- DFT calculation job submission (VASP/ONETEP)
- HPC cluster status monitoring
- Result parsing and Obsidian integration
- Error detection and troubleshooting

### Local LLM Support

**Benefits**:
- Zero API costs
- Complete privacy
- Offline operation
- Custom fine-tuning

**Candidates**:
- Llama 3.1 70B (via Ollama)
- Mistral Large
- Qwen 2.5

---

## 📚 References

### Documentation

- **Email-Agent Roadmap**: `docs/EMAIL_AGENT_ROADMAP.md`
- **PM2 Migration Guide**: `docs/PM2_MIGRATION.md`
- **System Handoff**: `HANDOFF_TO_MACMINI.md` (Feb 2026)

### External Resources

- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)
- [Gemini API Reference](https://ai.google.dev/docs)
- [PM2 Documentation](https://pm2.keymetrics.io/)
- [Obsidian PARA Method](https://fortelabs.com/blog/para/)

### API Keys & Services

- **Telegram Bot**: @BotFather
- **Gemini API**: [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Claude API**: [Anthropic Console](https://console.anthropic.com/)

---

## ✅ System Health Checklist

**Daily**:
- [ ] Check PM2 status: `pm2 status`
- [ ] Review logs: `pm2 logs polaris-bot --lines 20`
- [ ] Test `/check_mail` on Telegram

**Weekly**:
- [ ] Review classification accuracy (Obsidian files)
- [ ] Check API usage (Gemini quota)
- [ ] Update Python dependencies: `pip3 install -r requirements.txt --upgrade`

**Monthly**:
- [ ] Backup `.env` and configuration files
- [ ] Archive old emails in Obsidian
- [ ] Review and update classification rules
- [ ] Check for Gemini API model updates

---

## 🎓 Lessons Learned

### Technical Decisions

1. **PM2 > launchd**: Avoided macOS Full Disk Access permission nightmare
2. **Gemini 2.5 Flash > Experimental models**: Stability > cutting-edge features
3. **PARA > Generic folders**: Obsidian integration follows proven methodology
4. **Filename sanitization**: Critical for Korean/special character handling

### Best Practices

1. **Always use stable model versions** in production
2. **Sanitize user input** before filesystem operations
3. **Test with edge cases** (Korean text, special characters, long subjects)
4. **Log everything** during development phase
5. **Document as you build** (this file!)

---

## 📞 Support & Maintenance

**Primary Developer**: 종민 (Jongmin Baek)
**Contact**: jbaek27@uic.edu
**GitHub**: (Private repository)

**System Location**: `~/Desktop/Polaris_Agent_System`
**Telegram Bot**: @MyPolaris_bot
**Process Name**: `polaris-bot` (PM2)

---

**Last Verified Working**: 2026-02-04 21:30 KST ✅
**System Status**: All green lights 🟢
**Ready for**: Production PhD workflow automation 🚀

---

*"당신의 연구를 안내하는 북극성 ⭐"*

**Polaris v0.3** - Built with ❤️ and AI
