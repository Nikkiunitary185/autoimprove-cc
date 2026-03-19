# CLAUDE.md — autoimprove-cc

> Claude Code 전용 autoimprove 시스템.
> 이 파일을 읽고 작업 시작할 것.

## 프로젝트 개요

**autoimprove-cc**는 OpenClaw `skill-autoimprove`의 Claude Code 전용 버전.
SKILL.md 대신 **CLAUDE.md**를 타겟으로 자동 개선하는 Karpathy autoresearch 루프.

- OpenClaw 의존성 없음
- `claude --permission-mode bypassPermissions --print` 로 직접 실행
- 어떤 Claude Code 프로젝트의 CLAUDE.md도 개선 가능

**GitHub:** https://github.com/VoidLight00/autoimprove-cc (Public)
**Python:** 3.10+

---

## OpenClaw 버전과의 차이

| | skill-autoimprove (OpenClaw) | autoimprove-cc (Claude Code) |
|---|---|---|
| 진입점 | SKILL.md `/autoimprove` 트리거 | `claude -p` 직접 실행 |
| 타겟 | `~/.openclaw/skills/*/SKILL.md` | 어떤 프로젝트의 `CLAUDE.md`도 가능 |
| LLM | `claude -p` subprocess | Claude Code 자체 (hooks) |
| git 대상 | 스킬 디렉토리 | 프로젝트 디렉토리 |

---

## 파일 구조

```
autoimprove-cc/
├── CLAUDE.md                  이 파일 (Claude Code 진입점)
├── README.md
├── autoimprove.config.json    설정
├── scripts/
│   ├── run-assertions.py      eval.json → 채점 → results.json
│   ├── run-loop.py            Karpathy 루프 (commit/reset)
│   ├── gen-eval.py            CLAUDE.md 분석 → eval.json 생성
│   └── report.py              개선 이력 리포트
└── templates/
    └── eval-template.json
```

---

## 사용법

```bash
# 1. 타겟 프로젝트의 CLAUDE.md eval.json 생성
python scripts/gen-eval.py --target /path/to/project

# 2. 현재 점수 확인
python scripts/run-assertions.py --target /path/to/project

# 3. 자율 개선 루프
python scripts/run-loop.py --target /path/to/project --max-iter 20

# 4. 리포트
python scripts/report.py --target /path/to/project
```

---

## 코딩 규칙

- `--target` 플래그로 어떤 경로도 지정 가능 (CLAUDE.md 또는 SKILL.md 모두)
- git 조작 시 항상 `cwd=target_dir` 명시
- LLM 호출: `claude --permission-mode bypassPermissions --print`
- 점수 동일 시 롤백 (개선 없으면 커밋 X)

---

*Maintained by Hyeon · Powered by Kraken 🐙*
