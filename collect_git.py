#!/usr/bin/env python3
"""주간 git 활동 수집기.

홈 디렉토리 바로 아래의 git 리포지토리들에서 최근 7일 커밋을 수집해
옵시디언 볼트 빌드로그/Inputs/에 마크다운으로 저장한다.
"""
import subprocess
from datetime import datetime
from pathlib import Path

HOME = Path.home()
VAULT = HOME / "Library/Mobile Documents/com~apple~CloudDocs/Obsidian/Investing"
INPUT_DIR = VAULT / "빌드로그" / "Inputs"
SINCE = "7 days ago"


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True, timeout=30)
    return r.stdout.strip() if r.returncode == 0 else ""


def main():
    repos = sorted(p for p in HOME.iterdir() if (p / ".git").is_dir())
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# 주간 git 활동 {today}", "", "#buildlog", "",
             f"수집 범위: 최근 7일, 리포 {len(repos)}개 스캔.", ""]
    active = 0
    for repo in repos:
        log = git(repo, "log", f"--since={SINCE}", "--date=short",
                  "--pretty=format:- %ad %h %s")
        if not log:
            continue
        active += 1
        stat = git(repo, "diff", "--shortstat", f"HEAD@{{{SINCE}}}", "HEAD") or "변경 통계 없음"
        remote = git(repo, "remote", "get-url", "origin") or "(원격 없음)"
        lines += [f"## {repo.name}", f"- 원격: {remote}", f"- 주간 변경량: {stat}",
                  "", "### 커밋", log, ""]
    if active == 0:
        lines.append("이번 주 커밋이 있는 리포지토리가 없음.")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = INPUT_DIR / f"주간활동_{today}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[done] 활동 리포 {active}개 → {out}")


if __name__ == "__main__":
    main()
