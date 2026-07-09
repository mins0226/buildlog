#!/usr/bin/env python3
"""커밋 직전 비밀정보 검문소 (deterministic gate).

buildlog는 공개 리포이고, 주간 글은 무인 에이전트가 자동으로 커밋·푸시한다.
LLM의 판단에 의존하지 않고, git이 물리적으로 커밋을 막는다.

스테이징된 내용만 검사한다 (작업트리가 아니라 실제로 커밋될 바이트).
발견 시 종료코드 1 → pre-commit 훅이 커밋을 중단시킨다.

수동 실행:
  python3 gate_secrets.py            # 스테이징된 변경 검사
  python3 gate_secrets.py --all      # 리포의 추적 파일 전부 검사
"""
import re
import subprocess
import sys

# (이름, 정규식) — 오탐이 적은 확정적 패턴만.
PATTERNS = [
    ("GitHub 토큰", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("Anthropic 키", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI 키", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("AWS 액세스 키", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("개인키 블록", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Slack 토큰", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("Bearer 토큰", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{24,}")),
    # 옵시디언 Local REST API 키 등 긴 16진수. git SHA-1(40자)과 겹치지 않게 48자 이상.
    ("긴 16진수 시크릿", re.compile(r"\b[0-9a-f]{48,}\b")),
    # key = "값" 형태의 하드코딩
    ("하드코딩된 자격증명", re.compile(
        r"(?i)\b(api[_-]?key|apikey|secret|token|password|passwd|access[_-]?key)\b"
        r"\s*[:=]\s*['\"][A-Za-z0-9_\-./+]{16,}['\"]")),
]

# 이 마커가 있는 줄은 건너뛴다 (예시 코드·문서용)
ALLOW_MARKER = "gate-secrets: allow"


def sh(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def staged_files() -> list[str]:
    out = sh("diff", "--cached", "--name-only", "--diff-filter=ACM")
    return [f for f in out.splitlines() if f.strip()]


def content(path: str, from_index: bool) -> str:
    if from_index:
        return sh("show", f":{path}")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def scan(path: str, text: str) -> list[tuple[int, str, str]]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARKER in line:
            continue
        for name, pat in PATTERNS:
            m = pat.search(line)
            if m:
                found = m.group(0)
                redacted = found[:6] + "…" + found[-4:] if len(found) > 12 else "…"
                hits.append((lineno, name, redacted))
    return hits


def main() -> int:
    scan_all = "--all" in sys.argv
    files = sh("ls-files").splitlines() if scan_all else staged_files()
    files = [f for f in files if f != "gate_secrets.py"]  # 패턴 정의 자신은 제외

    findings = []
    for f in files:
        for lineno, name, redacted in scan(f, content(f, from_index=not scan_all)):
            findings.append((f, lineno, name, redacted))

    if not findings:
        print(f"✅ 검문소 통과 — 파일 {len(files)}개에서 비밀정보 없음")
        return 0

    print("🚫 커밋 차단 — 비밀정보로 보이는 내용이 발견됐습니다:\n", file=sys.stderr)
    for f, lineno, name, redacted in findings:
        print(f"  {f}:{lineno}  [{name}]  {redacted}", file=sys.stderr)
    print(
        "\n해당 줄을 제거하고 다시 커밋하세요."
        f"\n의도적인 예시라면 그 줄 끝에 '{ALLOW_MARKER}' 주석을 다세요."
        "\n(--no-verify로 우회하지 마세요 — 이 리포는 공개됩니다)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
