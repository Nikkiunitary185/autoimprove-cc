# autoimprove-cc

Karpathy autoresearch 루프를 CLAUDE.md에 적용하는 Claude Code 전용 자동개선 시스템.

어떤 Claude Code 프로젝트의 `CLAUDE.md`도 자동으로 분석하고, assertions를 생성하고, 반복적으로 개선합니다.

## OpenClaw 버전과의 차이

| | skill-autoimprove (OpenClaw) | **autoimprove-cc** (Claude Code) |
|---|---|---|
| 타겟 | `~/.openclaw/skills/*/SKILL.md` | **어떤 프로젝트의 `CLAUDE.md`도 가능** |
| 진입점 | `/autoimprove` 스킬 트리거 | `python scripts/*.py --target <path>` |
| LLM 호출 | `claude -p` | `claude --permission-mode bypassPermissions --print` |
| eval 저장 | `skills/<name>/eval/eval.json` | `<target>/.autoimprove/eval.json` |
| 의존성 | OpenClaw 필수 | **없음** (Python 3.10+ only) |

## Quick Start

```bash
# 1. eval.json 생성 — CLAUDE.md를 분석해 assertions 자동 생성
python scripts/gen-eval.py --target /path/to/your/project

# 2. 현재 점수 확인
python scripts/run-assertions.py --target /path/to/your/project

# 3. 자율 개선 루프 실행
python scripts/run-loop.py --target /path/to/your/project --max-iter 20

# 4. 리포트 확인
python scripts/report.py --target /path/to/your/project
```

## --target 플래그

모든 스크립트에서 `--target` (또는 `-t`)로 프로젝트 경로를 지정합니다.

```bash
# 디렉토리 지정 — 내부의 CLAUDE.md를 자동 탐지
python scripts/gen-eval.py --target ~/projects/my-app

# CLAUDE.md 직접 지정도 가능
python scripts/gen-eval.py --target ~/projects/my-app/CLAUDE.md
```

## 작동 원리

```
1. CLAUDE.md 읽기
2. eval.json의 binary assertions 실행 (LLM 판단)
3. 점수 계산 (pass 수 / 전체 수)
4. 점수 개선 → git commit
   점수 동일/하락 → git reset (롤백)
5. 반복
```

## Assertions 유형 (Claude Code 특화)

| 카테고리 | 검증 대상 |
|----------|-----------|
| **구조** | Architecture/파일구조 섹션, 헤딩 계층 |
| **규칙** | Do NOT / 코딩 규칙 섹션, 금지 패턴 |
| **진입점** | 프로젝트 개요/목적 명확성 |
| **명령어** | CLI 명령어 예시, 코드 블록 |
| **완성도** | 파일 경로 명시, 예시 코드, 의존성 |

## 파일 구조

```
autoimprove-cc/
├── CLAUDE.md                  Claude Code 진입점
├── README.md                  이 파일
├── autoimprove.config.json    설정
├── scripts/
│   ├── gen-eval.py            CLAUDE.md 분석 → eval.json 생성
│   ├── run-assertions.py      eval.json → 채점 → results.json
│   ├── run-loop.py            Karpathy 루프 (commit/reset)
│   └── report.py              개선 이력 리포트
└── templates/
    └── eval-template.json     eval.json 기본 템플릿
```

타겟 프로젝트에 생성되는 파일:

```
<target-project>/
├── CLAUDE.md                  개선 대상
└── .autoimprove/
    ├── eval.json              assertions 정의
    ├── results.json           최근 채점 결과
    ├── history.jsonl          루프 이력 (JSONL)
    └── report.txt             최종 리포트
```

## 설정 (autoimprove.config.json)

| 키 | 기본값 | 설명 |
|----|--------|------|
| `max_iterations` | `20` | 루프 최대 반복 횟수 |
| `timeout_seconds` | `3600` | 루프 타임아웃 (초) |
| `llm_command` | `claude --permission-mode bypassPermissions --print` | LLM 호출 명령어 |
| `git_auto_commit` | `true` | 개선 시 자동 커밋 |
| `eval_dir` | `.autoimprove` | eval.json 저장 디렉토리 |
| `eval_filename` | `eval.json` | eval 파일명 |
| `assertions_per_test` | `5` | 테스트 그룹당 assertion 수 |
| `total_tests_target` | `5` | 테스트 그룹 수 |

## 사용 시나리오

### 새 프로젝트의 CLAUDE.md 품질 점검

```bash
python scripts/gen-eval.py --target ~/projects/new-app
python scripts/run-assertions.py --target ~/projects/new-app
# → 현재 점수와 실패한 항목 확인
```

### 밤새 자동 개선

```bash
python scripts/run-loop.py --target ~/projects/my-app --max-iter 50 --timeout 7200
# → 아침에 개선된 CLAUDE.md + 리포트 확인
```

### Dry-run (git 변경 없이 테스트)

```bash
python scripts/run-loop.py --target ~/projects/my-app --dry-run
```

## 요구사항

- Python 3.10+
- Claude Code CLI (`claude` 명령어)
- 타겟 프로젝트가 git 저장소일 것 (롤백 기능에 필요)

---

*Maintained by Hyeon · Powered by Kraken*
