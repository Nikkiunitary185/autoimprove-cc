#!/usr/bin/env python3
"""gen-eval.py — CLAUDE.md를 분석하여 binary assertions를 자동 생성한다.

5개 테스트 그룹 (Claude Code 특화):
  1. 구조 — Architecture/파일구조 섹션 존재 여부
  2. 규칙 — Do NOT 또는 코딩 규칙 섹션
  3. 진입점 — 프로젝트 개요/목적 명확성
  4. 명령어 — 주요 CLI 명령어 예시
  5. 완성도 — 파일 경로 명시, 예시 코드

Usage:
    python gen-eval.py --target /path/to/project
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "autoimprove.config.json"

# ANSI 컬러 코드
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"오류: 설정 파일을 찾을 수 없습니다: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def resolve_target(target: str) -> tuple[Path, Path]:
    """--target 인자를 (프로젝트 디렉토리, CLAUDE.md 경로) 튜플로 변환한다."""
    p = Path(target).expanduser().resolve()
    if p.is_file() and p.name == "CLAUDE.md":
        return p.parent, p
    if p.is_dir():
        claude_md = p / "CLAUDE.md"
        if claude_md.exists():
            return p, claude_md
        print(f"오류: {p}에 CLAUDE.md가 없습니다.", file=sys.stderr)
        sys.exit(1)
    print(f"오류: 유효하지 않은 경로입니다: {target}", file=sys.stderr)
    sys.exit(1)


def backup_existing_eval(eval_path: Path) -> Path | None:
    """기존 eval.json이 있으면 .bak으로 백업한다."""
    if not eval_path.exists():
        return None
    bak_path = eval_path.with_suffix(".json.bak")
    shutil.copy2(eval_path, bak_path)
    print(f"  {YELLOW}기존 eval.json 백업 → {bak_path.name}{RESET}")
    return bak_path


def generate_assertions(
    claude_md_content: str,
    target_dir: Path,
    llm_cmd: str,
    config: dict,
) -> dict:
    """LLM을 사용하여 CLAUDE.md에 대한 assertions를 생성한다."""
    tests_target: int = config.get("total_tests_target", 5)
    assertions_per: int = config.get("assertions_per_test", 5)
    target_name = target_dir.name

    prompt = f"""You are an expert evaluator for Claude Code projects.
Analyze the following CLAUDE.md and generate binary assertions (TRUE/FALSE) to evaluate its quality as a Claude Code instruction file.

<CLAUDE_MD>
{claude_md_content}
</CLAUDE_MD>

Generate exactly {tests_target} test groups with exactly {assertions_per} assertions each.

The 5 test groups MUST be these categories (Claude Code specific) in this order:
1. "구조" (Structure) — Architecture/file structure section exists, heading hierarchy, project layout documented
2. "규칙" (Rules) — "Do NOT" or coding rules section exists, specific constraints defined, forbidden patterns listed
3. "진입점" (Entry Point) — Project overview/purpose clearly stated, target audience identified, what the project does
4. "명령어" (Commands) — Main CLI commands with examples, usage patterns documented, code blocks with runnable commands
5. "완성도" (Completeness) — Related file paths specified, example code included, edge cases covered, dependencies mentioned

Each assertion must be a clear TRUE/FALSE statement that can be verified by reading the CLAUDE.md.

Output ONLY valid JSON in this exact format (no markdown fences, no extra text):
{{
  "target_path": "{target_dir}",
  "claude_md_path": "{target_dir}/CLAUDE.md",
  "generated_at": "{datetime.now(timezone.utc).isoformat()}",
  "tests": [
    {{
      "id": "test-001",
      "description": "구조 — Architecture/파일구조 섹션 존재 여부",
      "assertions": [
        "Assertion text 1",
        "Assertion text 2",
        "Assertion text 3",
        "Assertion text 4",
        "Assertion text 5"
      ]
    }},
    {{
      "id": "test-002",
      "description": "규칙 — Do NOT 또는 코딩 규칙 섹션",
      "assertions": ["..."]
    }},
    {{
      "id": "test-003",
      "description": "진입점 — 프로젝트 개요/목적 명확성",
      "assertions": ["..."]
    }},
    {{
      "id": "test-004",
      "description": "명령어 — 주요 CLI 명령어 예시",
      "assertions": ["..."]
    }},
    {{
      "id": "test-005",
      "description": "완성도 — 파일 경로 명시, 예시 코드",
      "assertions": ["..."]
    }}
  ]
}}"""

    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            result = subprocess.run(
                [*llm_cmd.split(), prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout.strip()

            # JSON 파싱 시도 — 코드 블록 제거
            if output.startswith("```"):
                lines = output.split("\n")
                end_idx = len(lines)
                for i in range(len(lines) - 1, 0, -1):
                    if lines[i].startswith("```"):
                        end_idx = i
                        break
                output = "\n".join(lines[1:end_idx])

            data = json.loads(output)

            if "tests" not in data or not isinstance(data["tests"], list):
                raise ValueError("tests 필드가 없거나 올바르지 않습니다")
            if len(data["tests"]) == 0:
                raise ValueError("테스트 그룹이 비어 있습니다")

            # 경로 보정
            data["target_path"] = str(target_dir)
            data["claude_md_path"] = str(target_dir / "CLAUDE.md")
            data["generated_at"] = datetime.now(timezone.utc).isoformat()

            return data

        except json.JSONDecodeError as e:
            if attempt < max_attempts - 1:
                print(
                    f"  {YELLOW}JSON 파싱 실패, 재시도 중... ({attempt + 1}/{max_attempts}){RESET}"
                )
                continue
            print(
                f"오류: LLM 출력이 유효한 JSON이 아닙니다: {e}",
                file=sys.stderr,
            )
            print(f"원본 출력 (첫 500자):\n{result.stdout[:500]}", file=sys.stderr)
            sys.exit(1)
        except subprocess.TimeoutExpired:
            if attempt < max_attempts - 1:
                print(f"  {YELLOW}타임아웃, 재시도 중...{RESET}")
                continue
            print("오류: LLM 호출 타임아웃 (120초 초과)", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print(
                f"오류: LLM 명령어를 찾을 수 없습니다: {llm_cmd}",
                file=sys.stderr,
            )
            sys.exit(1)
        except ValueError as e:
            if attempt < max_attempts - 1:
                print(f"  {YELLOW}검증 실패 ({e}), 재시도 중...{RESET}")
                continue
            print(f"오류: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"오류: {e}", file=sys.stderr)
            sys.exit(1)

    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLAUDE.md를 분석하여 eval.json을 자동 생성합니다.",
        epilog="예시: python gen-eval.py --target /path/to/project",
    )
    parser.add_argument(
        "--target", "-t", required=True,
        help="프로젝트 디렉토리 또는 CLAUDE.md 경로",
    )
    args = parser.parse_args()

    config = load_config()
    target_dir, claude_md_path = resolve_target(args.target)

    claude_md_content = claude_md_path.read_text(encoding="utf-8")
    llm_cmd: str = config.get(
        "llm_command", "claude --permission-mode bypassPermissions --print"
    )

    print(f"{BOLD}eval.json 생성: {target_dir.name}{RESET}")
    print(f"  CLAUDE.md: {claude_md_path}")
    print(f"  크기: {len(claude_md_content):,}자")

    # 출력 경로 결정
    eval_dir_name: str = config.get("eval_dir", ".autoimprove")
    eval_dir = target_dir / eval_dir_name
    eval_dir.mkdir(parents=True, exist_ok=True)

    eval_filename: str = config.get("eval_filename", "eval.json")
    eval_path = eval_dir / eval_filename

    # 기존 eval.json 백업
    backup_existing_eval(eval_path)

    print(f"\n  {CYAN}LLM으로 assertions 생성 중...{RESET}")
    eval_data = generate_assertions(
        claude_md_content, target_dir, llm_cmd, config
    )

    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)

    total_assertions = sum(len(t["assertions"]) for t in eval_data["tests"])
    test_count = len(eval_data["tests"])

    print(f"\n{GREEN}{BOLD}생성 완료!{RESET}")
    print(f"  파일: {eval_path}")
    print(f"  테스트 그룹: {test_count}개")
    print(f"  전체 assertions: {total_assertions}개")

    print(f"\n{BOLD}테스트 그룹:{RESET}")
    for test in eval_data["tests"]:
        count = len(test["assertions"])
        print(f"  [{test['id']}] {test.get('description', '')} ({count}개)")

    print(f"\n{DIM}개선 루프 실행 전에 eval.json을 검토하세요.{RESET}")


if __name__ == "__main__":
    main()
