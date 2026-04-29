# chae-bot 사용 가이드

연세대 Intelligence Networking Lab 논문 30편 위에서 동작하는 RAG 봇 3종(`general` / `fas` / `trihybrid`)의 일상 사용·개발 가이드.

## TL;DR

- 빠른 질문 → **Claude Code 슬래시 커맨드** (`/fas`, `/general`, `/trihybrid`)
- 외부 논문(arXiv/S2)도 같이 → **웹 UI** (`research-bot serve`)
- 코드 손볼 때 → **개발 모드** (Claude Code + 코드 수정)

---

## 0. 사전 준비 (한 번만)

```bash
cd C:\Users\Yoontae\Desktop\research_bot
.venv\Scripts\activate
```

`.venv`가 없으면:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[ingest,web]"
```

새 논문 추가했거나 PDF만 받아 놓고 인덱스 안 만든 상태면:
```bash
research-bot ingest
research-bot status
```

---

## 1. 개발 모드 — 코드 바꿀 때

### 1-1. Claude Code 진입

```bash
cd C:\Users\Yoontae\Desktop\research_bot
claude
```

자동으로 메모리(`~/.claude/projects/.../memory/`)와 `CLAUDE.md` 슬래시 커맨드 인식. 작업 의뢰는 평소처럼 자연어로:

> "FAS 봇 답변에 references 표 자동으로 붙게 해줘"
> "BM25 검색 추가해서 RIS 같은 정확 용어 매칭 강화해줘"
> "PDF 추출 PyMuPDF로 fallback 넣어줘"

### 1-2. 변경 후 sanity check

```bash
research-bot status                              # 인덱스/PDF 상태
research-bot query "fluid antenna" -k 3          # 검색 결과
research-bot prompt fas "FAS oversampling"       # 프롬프트 어셈블리
research-bot serve                               # 웹 UI 띄워서 직접 확인
```

### 1-3. 논문 추가

```bash
# 1) corpus/<id>.pdf 떨궈놓고
# 2) data/seed_papers.yaml 에 metadata entry 추가
research-bot ingest    # 새 PDF만 자동 감지·인덱싱
```

### 1-4. Git 커밋·푸시

```bash
git add .
git commit -m "feat: <설명>"
git push
```

> 이 repo는 `git config --local`로 identity 박혀있음 (`Yoontae Kim <kyt0410@yonsei.ac.kr>`). 다른 머신에서 작업하면 다시 설정 필요.

---

## 2. 일상 사용 — 질문하기

### 방법 A. Claude Code 슬래시 커맨드 (가장 빠름, 권장)

```bash
cd C:\Users\Yoontae\Desktop\research_bot
claude
```

안에서:
```
/fas FAS Part I/II/III의 기여를 한 문단씩 비교해줘
/general 최근 lab의 ISAC 관련 논문 어떤 게 있어?
/trihybrid RF lens와 phase shifter 기반 hybrid BF의 trade-off 정리
```

| 항목 | 내용 |
|---|---|
| 동작 | 슬래시 커맨드가 자동으로 로컬 검색 → 페르소나 조립 → Claude Code(=Max 플랜)가 답변 |
| 비용 | Max 플랜 한도만 사용 (API 호출 0회) |
| 외부 검색 | ❌ 로컬 인덱스 30편만 |
| 답변 자동? | ✅ |

**언제 쓰나**: 우리 lab 논문 안에서 답이 나올 만한 질문, 빠른 사실 확인.

### 방법 B. 웹 UI (Chrome)

별도 터미널 1개 열어서:
```bash
cd C:\Users\Yoontae\Desktop\research_bot
.venv\Scripts\python -m research_bot.cli serve
```

→ 그 터미널은 그대로 두고 Chrome에서:
```
http://127.0.0.1:8000
```

흐름:
1. 봇 선택 (general / fas / trihybrid)
2. 질문 입력 (`Ctrl+Enter`로 제출 가능)
3. **build prompt** 클릭 → 로컬 검색 + 외부 검색(arXiv/S2) → 통합 프롬프트
4. **copy prompt** 클릭 → 클립보드 복사
5. **open claude.ai →** 또는 Claude Code 창에 붙여넣기 → 답변
6. 다 쓰면 터미널 `Ctrl+C`로 서버 종료

| 항목 | 내용 |
|---|---|
| 동작 | 로컬 + arXiv + Semantic Scholar 검색 통합 → 프롬프트 생성 → 사용자가 수동으로 Claude에 붙여넣기 |
| 비용 | Max 플랜 한도 (Claude.ai 또는 Claude Code 어디 쓰든) |
| 외부 검색 | ✅ arXiv + S2 |
| 답변 자동? | ❌ 복붙 필요 |

**언제 쓰나**: 외부 최신 논문까지 같이 보고 싶을 때, 페이퍼 쓰면서 광범위하게 서베이할 때.

---

## 두 방법 차이 요약

| | A. 슬래시 커맨드 | B. 웹 UI |
|---|---|---|
| 시작 | `claude` 한 번 | 별도 터미널 + Chrome |
| 답변 자동 | ✅ | ❌ (복붙) |
| 외부 검색 | ❌ | ✅ arXiv + S2 |
| 추천 용도 | 일상 빠른 질문 | 페이퍼 작성, 외부 비교 |

> 둘 다 Anthropic API 키 **불필요**. Max 플랜만 있으면 됨.

---

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| Chrome에서 `ERR_CONNECTION_REFUSED` | `research-bot serve` 안 띄움. 터미널 다시 띄우고 살아있는지 확인 |
| 포트 8000 busy | `research-bot serve --port 8765` 같이 다른 포트로 |
| 슬래시 커맨드가 메뉴에 안 뜸 | `claude`를 **이 폴더**(`research_bot/`)에서 실행했는지 확인. `.claude/commands/` 인식하려면 그 폴더 안이어야 함 |
| 검색이 엉뚱한 논문만 짚음 | `research-bot query "..." -k 5 --topic fas`로 토픽 필터 적용 |
| 새 논문 인덱스에 안 들어감 | `data/seed_papers.yaml` metadata 누락. 추가 후 `research-bot ingest` |
| `ANTHROPIC_API_KEY missing` | API 경로(`research-bot ask`) 쓸 때만 필요. Max 플랜으로 운영하면 무시해도 됨 |

---

## 추후 확장 후보 (메모리에도 기록됨)

1. **BM25 hybrid retrieval** — `STAR-RIS`, `OFDM` 같은 정확 용어 매칭 보강
2. **섹션 인식 청킹** — Abstract/Method/Conclusion 라벨, FAS 봇 페이퍼 라이팅 정확도 ↑
3. **답변 references 표 자동 부착** — 어느 paper_id를 인용했는지 시각화
4. **PyMuPDF fallback** — Sayeed CAP-MIMO 같은 옛날 PDF 추출 품질 개선
