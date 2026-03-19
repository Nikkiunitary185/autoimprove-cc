---
name: autoimprove
description: SKILL.md 자동개선 루프 실행
allowed-tools:
  - Agent
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
---

# /autoimprove — SKILL.md 자동개선

Karpathy autoresearch 루프로 SKILL.md를 자동 개선합니다.

## 사용법

```
/autoimprove <skill-path>
/autoimprove <skill-path> --gen-eval-only
/autoimprove <skill-path> --max-loops 30
/autoimprove <skill-path> --dry-run
```

## 인자 파싱

`$ARGUMENTS`를 파싱하세요:

1. **첫 번째 인자** = `skill_path` (필수)
   - 디렉토리 경로: `skills/example-skill` 또는 절대 경로
   - SKILL.md 직접 경로도 가능: `skills/example-skill/SKILL.md`
   - 경로가 없으면 현재 디렉토리의 SKILL.md를 사용

2. **옵션 플래그**:
   - `--gen-eval-only`: eval.json만 생성하고 루프 실행 안 함
   - `--max-loops N`: 최대 반복 횟수 (기본: 20)
   - `--dry-run`: git commit/reset 없이 채점만 실행

## 실행 흐름

### 1. 경로 검증

```
skill_path를 resolve:
  - 디렉토리면 → SKILL.md가 있는지 확인
  - 파일이면 → SKILL.md인지 확인
  - eval/ 디렉토리가 있는지 확인, 없으면 생성
```

SKILL.md가 없으면 오류 메시지와 함께 종료:
> "SKILL.md를 찾을 수 없습니다: <경로>"

### 2. eval.json 확인

`<skill_path>/eval/eval.json`이 있는지 확인.

**없으면**: skill-optimizer 에이전트의 "eval.json 자동 생성" 로직을 실행.
- SKILL.md를 분석하여 assertions 자동 생성
- `<skill_path>/eval/eval.json`으로 저장
- 생성된 eval.json 요약 출력:
  ```
  eval.json 생성 완료
    테스트: 5개 그룹
    Assertions: 23개
    저장: skills/example-skill/eval/eval.json
  ```

**`--gen-eval-only`이면** 여기서 종료.

### 3. Git 상태 확인

`--dry-run`이 아니면:
- `skill_path`가 git 저장소 내부인지 확인
- 아니면 오류: "git 저장소가 아닙니다. 롤백을 위해 git init이 필요합니다."
- uncommitted changes가 있으면 경고: "커밋되지 않은 변경이 있습니다. 먼저 커밋하세요."

### 4. 루프 실행

skill-optimizer 에이전트를 실행:

```
Agent: skill-optimizer
  skill_dir: <resolved_path>
  max_loops: <N 또는 20>
  dry_run: <true/false>
```

### 5. 결과 출력

루프 완료 후 요약:

```
AutoImprove 완료: <스킬명>
  초기 점수: 60%
  최종 점수: 92%
  반복: 15회 (커밋 8 / 롤백 7)
  로그: <skill_path>/eval/improve-log.md
```

## 예시

```bash
# 기본 사용
/autoimprove skills/example-skill

# eval.json만 생성
/autoimprove skills/example-skill --gen-eval-only

# 최대 50회 반복
/autoimprove skills/example-skill --max-loops 50

# Git 없이 테스트
/autoimprove skills/example-skill --dry-run

# 절대 경로
/autoimprove ~/.openclaw/skills/comet-agent

# SKILL.md 직접 지정
/autoimprove ./SKILL.md
```
