# Polaris Bot 실행 가이드

## 필수 조건

- Python 3.9+
- Ollama 실행 중 (`ollama serve`)
- 모델 준비 완료:
  ```bash
  ollama pull nomic-embed-text
  # 70B 모델은 Modelfile로 생성 (llama70b-lite)
  # 8B 모델: ollama pull llama3.1:8b
  ```
- `.env` 설정 완료 (`cp .env.example .env`)

---

## 실행

### 직접 실행 (테스트용)

```bash
python3 -m polaris.bot_v2
```

### PM2 (24/7 운영 권장)

```bash
./start_with_pm2.sh
```

---

## 성공 메시지

```
INFO - Polaris Bot v2 initialized
INFO - Polaris Bot v2 starting...
```

---

## 문제 해결

### Ollama 연결 실패
```bash
ollama serve          # Ollama 데몬 시작
ollama list           # 모델 목록 확인
```

### TELEGRAM_BOT_TOKEN 없음
```bash
cat .env | grep TELEGRAM
```

### 모듈 없음 오류
```bash
pip3 install -r requirements.txt
```

### 경고 메시지 (무시 가능)
- `FutureWarning: Python 3.9` — 작동에 문제 없음
- `NotOpenSSLWarning` — 작동에 문제 없음

---

## 다음 단계

- 24/7 launchd 설정: `./setup_launchd.sh`
- HPC 연결: `.env`에 `HPC_HOST`, `HPC_USERNAME`, `HPC_SCHEDULER` 설정
- Obsidian 연동: `OBSIDIAN_PATH` 설정 후 Telegram에서 `/index` 실행

---

> **레거시 안내**: `python3 polaris_bot.py` 는 deprecated입니다.
> 2026-04-15 이후 자동 실행 불가. `python3 -m polaris.bot_v2` 를 사용하세요.
