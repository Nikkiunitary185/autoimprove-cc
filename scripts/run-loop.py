#!/usr/bin/env python3
"""run-loop.py — Karpathy autoresearch 스타일 자율 개선 루프.

CLAUDE.md를 반복적으로 개선하고, 점수가 오르면 커밋, 내리면 롤백한다.
eval.json이 없으면 자동으로 gen-eval.py를 실행한다.

Usage:
    python run-loop.py --target /path/to/project [--max-iter 20] [--dry-run]
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "autoimprove.config.json"
SCRIPTS_DIR = Path(__file__).parent

# ANSI 컬러 코드
GREEN = "\033[92m"
RED = "\033[91m"
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


def get_eval_path(target_dir: Path, config: dict) -> Path:
    eval_dir_name: str = config.get("eval_dir", ".autoimprove")
    eval_filename: str = config.get("eval_filename", "eval.json")
    return target_dir / eval_dir_name / eval_filename


def ensure_eval_json(target_dir: Path, config: dict) -> Path:
    """eval.json이 없으면 gen-eval.py를 자동 실행한다."""
    eval_path = get_eval_path(target_dir, config)

    if eval_path.exists():
        return eval_path

    print(f"\n{YELLOW}eval.json이 없습니다. 자동 생성 중...{RESET}")
    gen_eval_script = SCRIPTS_DIR / "gen-eval.py"
    result = subprocess.run(
        [sys.executable, str(gen_eval_script), "--target", str(target_dir)],
        timeout=180,
    )
    if result.returncode != 0:
        print("오류: eval.json 자동 생성 실패", file=sys.stderr)
        sys.exit(1)

    if not eval_path.exists():
        print(
            f"오류: gen-eval.py 실행 후에도 eval.json이 없습니다: {eval_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"{GREEN}eval.json 자동 생성 완료{RESET}\n")
    return eval_path


def get_score(target_dir: Path, config: dict) -> float:
    """run-assertions.py를 실행하여 현재 점수를 반환한다."""
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "run-assertions.py"),
        "--target", str(target_dir),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(
            f"{RED}오류: assertion 실행 타임아웃 (300초){RESET}", file=sys.stderr
        )
        return 0.0

    results_path = get_eval_path(target_dir, config).parent / "results.json"

    if results_path.exists():
        with open(results_path) as f:
            data = json.load(f)
        return data.get("score", 0.0)
    return 0.0


def get_failed_assertions(target_dir: Path, config: dict) -> list[str]:
    """실패한 assertion 목록을 반환한다."""
    results_path = get_eval_path(target_dir, config).parent / "results.json"

    if not results_path.exists():
        return []

    with open(results_path) as f:
        data = json.load(f)

    return [
        r["assertion"]
        for r in data.get("results", [])
        if r["result"] == "fail"
    ]


def improve_claude_md(
    claude_md_path: Path,
    failed_assertions: list[str],
    llm_cmd: str,
    iteration: int,
) -> bool:
    """LLM을 사용하여 CLAUDE.md를 개선한다."""
    claude_md_content = claude_md_path.read_text(encoding="utf-8")

    failed_list = "\n".join(f"- {a}" for a in failed_assertions)
    prompt = f"""You are an expert at writing CLAUDE.md files for Claude Code projects.
The following CLAUDE.md needs improvement. Some assertions are failing.

<CURRENT_CLAUDE_MD>
{claude_md_content}
</CURRENT_CLAUDE_MD>

<FAILED_ASSERTIONS>
{failed_list}
</FAILED_ASSERTIONS>

Iteration: {iteration}

Rewrite the CLAUDE.md to pass all failed assertions while keeping the existing passing content intact.
Rules:
- Output ONLY the complete new CLAUDE.md content, nothing else
- Do not add markdown code fences around the output
- Preserve the project's core purpose and existing instructions
- Make minimal changes to fix the failing assertions
- Keep the same overall structure
- CLAUDE.md is read by Claude Code as project instructions"""

    try:
        result = subprocess.run(
            [*llm_cmd.split(), prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        new_content = result.stdout.strip()
        if not new_content or len(new_content) < 50:
            print(f"  {YELLOW}[경고] LLM 응답이 너무 짧음, 건너뜀{RESET}")
            return False

        claude_md_path.write_text(new_content + "\n", encoding="utf-8")
        return True
    except subprocess.TimeoutExpired:
        print(
            f"  {RED}[타임아웃] CLAUDE.md 개선 실패 (120초 초과){RESET}",
            file=sys.stderr,
        )
        return False
    except Exception as e:
        print(f"  {RED}[오류] LLM 개선 실패: {e}{RESET}", file=sys.stderr)
        return False


def git_commit(target_dir: Path, message: str) -> bool:
    """변경 사항을 커밋한다."""
    subprocess.run(
        ["git", "add", "CLAUDE.md"],
        cwd=str(target_dir),
        capture_output=True,
        check=True,
    )
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(target_dir),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def git_reset(target_dir: Path) -> None:
    """마지막 커밋으로 롤백한다."""
    subprocess.run(
        ["git", "checkout", "--", "CLAUDE.md"],
        cwd=str(target_dir),
        capture_output=True,
    )


def is_git_repo(path: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "true" in result.stdout.strip().lower()


def append_history(log_path: Path, entry: dict) -> None:
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_report(target_dir: Path) -> None:
    """report.py를 실행하여 최종 리포트를 출력한다."""
    report_script = SCRIPTS_DIR / "report.py"
    if report_script.exists():
        print(f"\n{CYAN}리포트 생성 중...{RESET}")
        subprocess.run(
            [sys.executable, str(report_script), "--target", str(target_dir)],
            timeout=30,
        )


def run_loop(
    target_dir: Path,
    claude_md_path: Path,
    max_iter: int,
    timeout: int,
    *,
    dry_run: bool = False,
) -> list[dict]:
    """메인 개선 루프."""
    config = load_config()
    llm_cmd: str = config.get(
        "llm_command", "claude --permission-mode bypassPermissions --print"
    )
    target_name = target_dir.name

    if not dry_run and not is_git_repo(target_dir):
        print(
            f"오류: {target_dir}은 git 저장소가 아닙니다.\n"
            "롤백을 위해 git 초기화가 필요합니다.",
            file=sys.stderr,
        )
        sys.exit(1)

    # eval.json 자동 확인/생성
    ensure_eval_json(target_dir, config)

    # 로그 디렉토리 설정 (타겟의 .autoimprove/ 내부)
    eval_dir_name: str = config.get("eval_dir", ".autoimprove")
    log_dir = target_dir / eval_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)
    history_path = log_dir / "history.jsonl"

    history: list[dict] = []
    start_time = time.time()

    mode_label = f"{YELLOW}[DRY-RUN]{RESET} " if dry_run else ""
    print(f"\n{'=' * 60}")
    print(f"  {mode_label}{BOLD}AutoImprove Loop: {target_name}{RESET}")
    print(f"  타겟: {target_dir}")
    print(f"  최대 반복: {max_iter} | 타임아웃: {timeout}초")
    if dry_run:
        print(f"  {YELLOW}DRY-RUN 모드: git commit/reset 없이 채점만 실행{RESET}")
    print(f"{'=' * 60}")

    # 초기 점수
    print(f"\n{CYAN}[초기] 채점 중...{RESET}")
    best_score = get_score(target_dir, config)
    print(f"초기 점수: {BOLD}{best_score:.2%}{RESET}")

    initial_entry = {
        "iteration": 0,
        "score": best_score,
        "action": "initial",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    history.append(initial_entry)
    append_history(history_path, initial_entry)

    if best_score >= 1.0:
        print(f"\n{GREEN}{BOLD}모든 assertion 통과! 개선할 것이 없습니다.{RESET}")
        run_report(target_dir)
        return history

    try:
        for i in range(1, max_iter + 1):
            elapsed = time.time() - start_time
            if elapsed > timeout:
                print(
                    f"\n{YELLOW}[타임아웃] {elapsed:.0f}초 경과, 종료합니다.{RESET}"
                )
                break

            print(f"\n{'─' * 60}")
            print(
                f"{BOLD}[반복 {i}/{max_iter}]{RESET} "
                f"경과: {elapsed:.0f}초 | 현재 최고: {best_score:.2%}"
            )

            failed = get_failed_assertions(target_dir, config)
            if not failed:
                print(f"{GREEN}모든 assertion 통과!{RESET}")
                break

            print(f"  실패한 assertions: {RED}{len(failed)}개{RESET}")

            print(f"  {CYAN}CLAUDE.md 개선 중...{RESET}")
            improved = improve_claude_md(claude_md_path, failed, llm_cmd, i)
            if not improved:
                entry = {
                    "iteration": i,
                    "score": best_score,
                    "action": "skip_llm_fail",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                history.append(entry)
                append_history(history_path, entry)
                continue

            print(f"  {CYAN}재채점 중...{RESET}")
            new_score = get_score(target_dir, config)

            if new_score > best_score:
                print(
                    f"  {GREEN}{BOLD}개선됨: "
                    f"{best_score:.2%} → {new_score:.2%}{RESET}"
                )
                action = "commit"
                if not dry_run:
                    git_commit(
                        target_dir,
                        f"autoimprove: {best_score:.2%} → {new_score:.2%} (iter {i})",
                    )
                best_score = new_score
            else:
                print(
                    f"  {RED}개선 없음: "
                    f"{best_score:.2%} → {new_score:.2%}, 롤백{RESET}"
                )
                action = "rollback"
                if not dry_run:
                    git_reset(target_dir)

            entry = {
                "iteration": i,
                "score": new_score,
                "best_score": best_score,
                "action": action,
                "failed_count": len(failed),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            history.append(entry)
            append_history(history_path, entry)

            if best_score >= 1.0:
                print(f"\n{GREEN}{BOLD}  100% 달성! 완벽한 점수입니다!{RESET}")
                break

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n\n{YELLOW}[중단] Ctrl+C 감지 — 안전 종료합니다.{RESET}")
        print(f"  현재 최고 점수: {BOLD}{best_score:.2%}{RESET}")
        print(f"  반복 횟수: {len(history) - 1}")
        print(f"  경과 시간: {elapsed:.0f}초")
        print(f"  히스토리: {history_path}")

        if not dry_run:
            git_reset(target_dir)
            print(f"  {DIM}진행 중인 변경 사항을 롤백했습니다.{RESET}")

        run_report(target_dir)
        return history

    # 루프 완료 요약
    elapsed = time.time() - start_time
    commits = sum(1 for h in history if h.get("action") == "commit")
    rollbacks = sum(1 for h in history if h.get("action") == "rollback")

    print(f"\n{'=' * 60}")
    print(f"  {BOLD}루프 완료{RESET}")
    print(f"  최종 점수: {BOLD}{best_score:.2%}{RESET}")
    print(f"  반복 횟수: {len(history) - 1}")
    print(f"  커밋: {GREEN}{commits}{RESET} | 롤백: {RED}{rollbacks}{RESET}")
    print(f"  소요 시간: {elapsed:.0f}초")
    print(f"  히스토리: {history_path}")
    print(f"{'=' * 60}")

    run_report(target_dir)

    return history


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLAUDE.md 자율 개선 루프 (Karpathy autoresearch 방식)",
        epilog="예시: python run-loop.py --target /path/to/project --max-iter 10",
    )
    parser.add_argument(
        "--target", "-t", required=True,
        help="프로젝트 디렉토리 또는 CLAUDE.md 경로",
    )
    parser.add_argument(
        "--max-iter", type=int, default=None,
        help="최대 반복 횟수 (기본: 설정 파일 참조)",
    )
    parser.add_argument(
        "--timeout", type=int, default=None,
        help="타임아웃 (초, 기본: 설정 파일 참조)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="git commit/reset 없이 채점만 반복 (테스트용)",
    )
    args = parser.parse_args()

    config = load_config()
    max_iter: int = args.max_iter or config.get("max_iterations", 20)
    timeout: int = args.timeout or config.get("timeout_seconds", 3600)

    target_dir, claude_md_path = resolve_target(args.target)

    run_loop(
        target_dir,
        claude_md_path,
        max_iter,
        timeout,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
