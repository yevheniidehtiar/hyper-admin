#!/usr/bin/env python3
"""OSS Triage Auditor — scan GitHub issues/PRs for spam, ego-PRs, duplicates, and staleness.

All GitHub interactions go through the `gh` CLI with list-style subprocess args
(never shell=True). Untrusted content from issue/PR bodies is treated as data only.

Usage:
    uv run scripts/triage_audit.py [dry-run|live] [--repo owner/repo]
    poe triage:audit
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import date, datetime

import typer

# ---------------------------------------------------------------------------
# Constants — all thresholds, weights, and patterns are hardcoded here
# ---------------------------------------------------------------------------

SUSPICIOUS_THRESHOLD = 60
EGO_PR_THRESHOLD = 50
DUPLICATE_JACCARD_THRESHOLD = 0.6
STALE_IDEA_DAYS = 30
STALE_PR_DAYS = 21
STALE_NEEDS_HUMAN_DAYS = 14
MAX_AUTHOR_LOOKUPS = 20
LIVE_MODE_PAUSE_SECONDS = 1

DESC_CODE_RATIO_THRESHOLD = 10
DESC_CODE_RATIO_WEIGHT = 25
BOILERPLATE_WEIGHT = 20
NO_ISSUE_LINK_WEIGHT = 15
UNSOLICITED_REFACTOR_WEIGHT = 15
ZERO_MERGED_WEIGHT = 10
LLM_MARKERS_WEIGHT = 10
NO_CONVERSATION_WEIGHT = 10
BULK_SUBMISSIONS_WEIGHT = 10

EGO_WHITESPACE_WEIGHT = 30
EGO_TYPO_WEIGHT = 25
EGO_NO_ISSUE_WEIGHT = 20
EGO_KEYWORD_WEIGHT = 15
EGO_NO_SRC_WEIGHT = 10

BOILERPLATE_PATTERNS = [
    re.compile(r"\bi noticed that\b", re.IGNORECASE),
    re.compile(r"\bthis pr improves\b", re.IGNORECASE),
    re.compile(r"\bas a developer\b", re.IGNORECASE),
    re.compile(r"\bthis change enhances\b", re.IGNORECASE),
    re.compile(r"\bthis pr enhances\b", re.IGNORECASE),
    re.compile(r"\bthis pr adds\b", re.IGNORECASE),
]

LLM_MARKER_PATTERNS = [
    re.compile(r"\bas an ai\b", re.IGNORECASE),
    re.compile(r"\bi'd be happy to\b", re.IGNORECASE),
    re.compile(r"\bhere's a\b", re.IGNORECASE),
]

ISSUE_LINK_PATTERN = re.compile(
    r"(#\d+|closes\s+#?\d+|fixes\s+#?\d+|resolves\s+#?\d+)", re.IGNORECASE
)

ISSUE_REF_EXTRACT_PATTERN = re.compile(r"(?:closes|fixes|resolves)\s+#?(\d+)|#(\d+)", re.IGNORECASE)

EGO_KEYWORDS = [
    "typo",
    "minor fix",
    "cosmetic",
    "whitespace",
    "formatting",
    "grammar",
    "capitalize",
]

# Includes "fix syntax" type patterns that indicate a functional docs fix
FUNCTIONAL_DOCS_PATTERNS = [
    re.compile(r"include\s+directive", re.IGNORECASE),
    re.compile(r"broken\s+(link|syntax|render)", re.IGNORECASE),
    re.compile(r"fix\w*\s+(syntax|render|build)", re.IGNORECASE),
    re.compile(r"\{\!>.*\!\}", re.IGNORECASE),
]

STOP_WORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "is",
        "in",
        "for",
        "to",
        "of",
        "and",
        "or",
        "with",
        "this",
        "that",
        "it",
        "be",
        "as",
        "at",
        "by",
        "on",
        "not",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "can",
        "may",
        "its",
        "from",
    ]
)

LIFECYCLE_LABELS = [
    "idea",
    "researched",
    "planned",
    "approved",
    "in-progress",
    "review",
    "qa-passed",
    "released",
]

LOGIN_SANITIZE = re.compile(r"[^a-zA-Z0-9_-]")

# Comment marker for idempotency
AUDIT_COMMENT_MARKER = "<!-- oss-triage-audit"

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Item:
    number: int
    title: str
    body: str
    labels: list[str]
    author: str
    created_at: str
    updated_at: str
    comments: list[dict[str, object]]
    is_pr: bool = False
    # PR-specific
    files: list[dict[str, object]] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    commits: int = 0
    head_ref: str = ""


@dataclass
class ScoredItem:
    item: Item
    score: int
    signals: list[str]


@dataclass
class DuplicatePair:
    item_a: int
    title_a: str
    item_b: int
    title_b: str
    similarity: float
    recommendation: str


@dataclass
class LifecycleViolation:
    number: int
    title: str
    had: str
    applied: str


@dataclass
class StaleItem:
    number: int
    item_type: str
    title: str
    last_activity: str
    days_stale: int
    reason: str


@dataclass
class Findings:
    suspicious: list[ScoredItem] = field(default_factory=list)
    ego_prs: list[ScoredItem] = field(default_factory=list)
    duplicates: list[DuplicatePair] = field(default_factory=list)
    lifecycle_violations: list[LifecycleViolation] = field(default_factory=list)
    stale: list[StaleItem] = field(default_factory=list)
    total_issues: int = 0
    total_prs: int = 0


# ---------------------------------------------------------------------------
# GitHub CLI helpers — always list args, never shell=True
# ---------------------------------------------------------------------------

# Patterns that indicate a transient error worth retrying
_RATE_LIMIT_PATTERN = re.compile(r"rate.?limit", re.IGNORECASE)
# GitHub often embeds "retry after N seconds" in rate-limit messages
_RETRY_AFTER_PATTERN = re.compile(r"retry.?after\D+(\d+)", re.IGNORECASE)
# GraphQL node-count limit — NOT transient; retrying will not help
_NODE_LIMIT_PATTERN = re.compile(r"requesting up to.*nodes.*exceeds", re.IGNORECASE)

_GH_RETRIES = 3
_GH_BACKOFF_BASE = 5  # seconds; doubles each attempt: 5 → 10 → 20


def _retry_delay(attempt: int, stderr: str) -> int:
    """Return seconds to wait before the next attempt.

    Prefer the server-supplied 'retry after N seconds' value when present;
    fall back to exponential backoff (5 → 10 → 20 s).
    """
    m = _RETRY_AFTER_PATTERN.search(stderr)
    if m:
        return int(m.group(1))
    return _GH_BACKOFF_BASE * (2 ** (attempt - 1))


def _is_retryable(stderr: str) -> bool:
    """True for transient GitHub errors (rate limits, 5xx).  False for hard failures."""
    if _NODE_LIMIT_PATTERN.search(stderr):
        return False
    return bool(_RATE_LIMIT_PATTERN.search(stderr)) or "502" in stderr or "503" in stderr


def gh_json(args: list[str]) -> list[dict[str, object]] | dict[str, object]:
    """Run a gh command and parse JSON output.

    Retries up to ``_GH_RETRIES`` times on transient errors (rate limits,
    5xx).  Respects the 'retry after N seconds' hint in the error message when
    present; otherwise uses exponential back-off starting at 5 s.
    """
    for attempt in range(1, _GH_RETRIES + 1):
        result = subprocess.run(  # noqa: S603
            ["gh", *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return json.loads(result.stdout) if result.stdout.strip() else []

        stderr = result.stderr or ""
        if attempt < _GH_RETRIES and _is_retryable(stderr):
            delay = _retry_delay(attempt, stderr)
            typer.echo(
                f"  [rate-limit] gh {' '.join(args[:3])}... — waiting {delay}s "
                f"(attempt {attempt}/{_GH_RETRIES})",
                err=True,
            )
            time.sleep(delay)
            continue

        typer.echo(f"Error running gh {' '.join(args[:3])}...: {stderr}", err=True)
        return []

    return []  # unreachable, but satisfies the type checker


def gh_run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a gh command without JSON parsing.

    Retries on transient errors using the same back-off strategy as
    ``gh_json``.  Returns the last ``CompletedProcess`` regardless of outcome
    so callers can inspect ``returncode`` / ``stderr``.
    """
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, _GH_RETRIES + 1):
        last = subprocess.run(  # noqa: S603
            ["gh", *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
        )
        if last.returncode == 0:
            return last

        stderr = last.stderr or ""
        if attempt < _GH_RETRIES and _is_retryable(stderr):
            delay = _retry_delay(attempt, stderr)
            typer.echo(
                f"  [rate-limit] gh {' '.join(args[:3])}... — waiting {delay}s "
                f"(attempt {attempt}/{_GH_RETRIES})",
                err=True,
            )
            time.sleep(delay)
            continue
        break

    return last  # type: ignore[return-value]


def sanitize_login(login: str) -> str:
    return LOGIN_SANITIZE.sub("", login)


# ---------------------------------------------------------------------------
# Phase 1: Data collection
# ---------------------------------------------------------------------------


def fetch_data(repo: str) -> tuple[list[Item], list[Item], list[str]]:
    """Fetch issues, PRs, and labels from the target repo."""
    typer.echo(f"Fetching data from {repo}...")

    raw_issues = gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "500",
            "--json",
            "number,title,body,labels,assignees,createdAt,updatedAt,author,comments",
        ]
    )

    # Note: PR list excludes 'comments' and 'files' to avoid GraphQL node limit
    # on large repos (e.g. fastapi with 500+ PRs). File details are fetched
    # on-demand per-PR only when needed for ego-PR scoring.
    raw_prs = gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,body,labels,author,createdAt,updatedAt,additions,deletions,headRefName",
        ]
    )

    raw_labels = gh_json(
        [
            "label",
            "list",
            "--repo",
            repo,
            "--json",
            "name",
            "--limit",
            "200",
        ]
    )

    issues = (
        [_parse_item(r, is_pr=False) for r in raw_issues] if isinstance(raw_issues, list) else []
    )
    prs = [_parse_item(r, is_pr=True) for r in raw_prs] if isinstance(raw_prs, list) else []
    labels = [str(lb.get("name", "")) for lb in raw_labels] if isinstance(raw_labels, list) else []

    typer.echo(f"  Found {len(issues)} open issues, {len(prs)} open PRs, {len(labels)} labels")
    return issues, prs, labels


def _parse_item(raw: dict[str, object], *, is_pr: bool) -> Item:
    author_obj = raw.get("author", {})
    author_login = str(author_obj.get("login", "")) if isinstance(author_obj, dict) else ""
    labels_raw = raw.get("labels", [])
    label_names = (
        [str(lb.get("name", "")) for lb in labels_raw] if isinstance(labels_raw, list) else []
    )
    comments_raw = raw.get("comments", [])
    comments = list(comments_raw) if isinstance(comments_raw, list) else []
    files_raw = raw.get("files", [])
    files = list(files_raw) if isinstance(files_raw, list) else []
    commits_raw = raw.get("commits", [])
    commits_count = len(commits_raw) if isinstance(commits_raw, list) else 0

    return Item(
        number=int(raw.get("number", 0)),
        title=str(raw.get("title", "")),
        body=str(raw.get("body", "")),
        labels=label_names,
        author=author_login,
        created_at=str(raw.get("createdAt", "")),
        updated_at=str(raw.get("updatedAt", "")),
        comments=comments,
        is_pr=is_pr,
        files=files,
        additions=int(raw.get("additions", 0)),
        deletions=int(raw.get("deletions", 0)),
        commits=commits_count,
        head_ref=str(raw.get("headRefName", "")),
    )


# ---------------------------------------------------------------------------
# Phase 2: Suspicious content scoring (AI-slop)
# ---------------------------------------------------------------------------


def score_suspicious(
    item: Item,
    author_counts: dict[str, int],
    merged_cache: dict[str, bool],
    repo: str,
) -> ScoredItem:
    score = 0
    signals: list[str] = []
    body = item.body or ""
    body_words = len(body.split())

    # Signal: description-to-code ratio
    if item.is_pr:
        total_changes = item.additions + item.deletions
        if total_changes > 0:
            ratio = body_words / total_changes
            if ratio > DESC_CODE_RATIO_THRESHOLD:
                score += DESC_CODE_RATIO_WEIGHT
                signals.append(f"desc:code ratio {ratio:.1f}:1 (+{DESC_CODE_RATIO_WEIGHT})")
    else:
        has_code_refs = "`" in body or "src/" in body or ".py" in body
        if body_words > 500 and not has_code_refs:
            score += DESC_CODE_RATIO_WEIGHT
            signals.append(
                f"verbose body ({body_words} words, no code refs) (+{DESC_CODE_RATIO_WEIGHT})"
            )

    # Signal: generic boilerplate
    has_specific_refs = bool(re.search(r"[\w/]+\.py|`\w+`|def |class |function ", body))
    if any(p.search(body) for p in BOILERPLATE_PATTERNS) and not has_specific_refs:
        score += BOILERPLATE_WEIGHT
        signals.append(f"boilerplate language (+{BOILERPLATE_WEIGHT})")

    # Signal: no issue link (PRs only)
    if item.is_pr and not ISSUE_LINK_PATTERN.search(body):
        score += NO_ISSUE_LINK_WEIGHT
        signals.append(f"no issue link (+{NO_ISSUE_LINK_WEIGHT})")

    # Signal: unsolicited large refactor
    if item.is_pr:
        total_changes = item.additions + item.deletions
        if (
            total_changes > 1000
            and not ISSUE_LINK_PATTERN.search(body)
            and _check_zero_merged(item.author, merged_cache, repo)
        ):
            score += UNSOLICITED_REFACTOR_WEIGHT
            signals.append(
                f"unsolicited large refactor ({total_changes} LOC) (+{UNSOLICITED_REFACTOR_WEIGHT})"
            )

    # Signal: zero merged PRs
    if _check_zero_merged(item.author, merged_cache, repo):
        score += ZERO_MERGED_WEIGHT
        signals.append(f"zero merged PRs (+{ZERO_MERGED_WEIGHT})")

    # Signal: LLM markers
    heading_count = body.count("## ")
    total_changes = (item.additions + item.deletions) if item.is_pr else 0
    has_llm_markers = any(p.search(body) for p in LLM_MARKER_PATTERNS)
    has_excessive_headings = heading_count >= 3 and total_changes < 20
    if has_llm_markers or has_excessive_headings:
        score += LLM_MARKERS_WEIGHT
        signals.append(f"LLM markers (+{LLM_MARKERS_WEIGHT})")

    # Signal: no conversation
    # Note: PR comments are not fetched in bulk (GraphQL node limit), so PRs
    # will always trigger this signal. This is an acceptable false-positive bias
    # because PRs without any other red flags won't cross the threshold from +10 alone.
    if item.comments:
        human_comments = [
            c
            for c in item.comments
            if isinstance(c, dict)
            and isinstance(c.get("author", {}), dict)
            and not str(c.get("author", {}).get("login", "")).endswith("[bot]")  # type: ignore[union-attr]
        ]
        if not human_comments:
            score += NO_CONVERSATION_WEIGHT
            signals.append(f"no conversation (+{NO_CONVERSATION_WEIGHT})")
    elif item.is_pr:
        # Comments not available for PRs (not fetched to avoid GraphQL limits)
        pass
    else:
        score += NO_CONVERSATION_WEIGHT
        signals.append(f"no conversation (+{NO_CONVERSATION_WEIGHT})")

    # Signal: bulk submissions
    if author_counts.get(item.author, 0) > 3:
        score += BULK_SUBMISSIONS_WEIGHT
        signals.append(
            f"bulk submissions ({author_counts[item.author]} items) (+{BULK_SUBMISSIONS_WEIGHT})"
        )

    return ScoredItem(item=item, score=score, signals=signals)


def _check_zero_merged(author: str, cache: dict[str, bool], repo: str) -> bool:
    if not author:
        return False
    safe_login = sanitize_login(author)
    if safe_login in cache:
        return cache[safe_login]
    if len(cache) >= MAX_AUTHOR_LOOKUPS:
        return False  # skip to avoid rate limiting
    result = gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--author",
            safe_login,
            "--state",
            "merged",
            "--limit",
            "1",
            "--json",
            "number",
        ]
    )
    is_zero = not result or (isinstance(result, list) and len(result) == 0)
    cache[safe_login] = is_zero
    return is_zero


# ---------------------------------------------------------------------------
# Phase 3: Ego-PR scoring
# ---------------------------------------------------------------------------


def _fetch_pr_files(pr_number: int, repo: str) -> list[str]:
    """Fetch file paths for a single PR on-demand."""
    result = gh_json(["pr", "view", str(pr_number), "--repo", repo, "--json", "files"])
    if isinstance(result, dict):
        files = result.get("files", [])
        if isinstance(files, list):
            return [str(f.get("path", "")) for f in files if isinstance(f, dict)]
    return []


def score_ego_pr(item: Item, repo: str) -> ScoredItem:
    if not item.is_pr:
        return ScoredItem(item=item, score=0, signals=[])

    score = 0
    signals: list[str] = []
    body = item.body or ""
    title_lower = item.title.lower()
    total_changes = item.additions + item.deletions

    # Quick pre-check: only fetch files if this PR could be an ego-PR
    # (small changes or has ego keywords in title)
    needs_file_check = total_changes < 10 or any(kw in title_lower for kw in EGO_KEYWORDS)
    if needs_file_check:
        file_paths = _fetch_pr_files(item.number, repo)
    else:
        file_paths = (
            item.files and [str(f.get("path", "")) for f in item.files if isinstance(f, dict)]
        ) or []
    touches_src = any(p.startswith("src/") or "/src/" in p for p in file_paths)

    # Signal: whitespace/formatting only
    all_non_source = not touches_src and len(file_paths) > 0
    if total_changes < 10 and all_non_source:
        # Check escape hatch: is this a functional docs fix?
        is_functional_fix = any(
            p.search(body) or p.search(item.title) for p in FUNCTIONAL_DOCS_PATTERNS
        )
        if is_functional_fix:
            weight = 10  # reduced
            score += weight
            signals.append(f"small non-source change (functional fix, reduced) (+{weight})")
        else:
            score += EGO_WHITESPACE_WEIGHT
            signals.append(
                f"small non-source change ({total_changes} LOC) (+{EGO_WHITESPACE_WEIGHT})"
            )

    # Signal: typo-only fix
    if "typo" in title_lower and total_changes <= 5:
        score += EGO_TYPO_WEIGHT
        signals.append(f"typo-only fix (+{EGO_TYPO_WEIGHT})")

    # Signal: no issue link
    if not ISSUE_LINK_PATTERN.search(body):
        score += EGO_NO_ISSUE_WEIGHT
        signals.append(f"no issue link (+{EGO_NO_ISSUE_WEIGHT})")

    # Signal: low-impact keywords in title
    if any(kw in title_lower for kw in EGO_KEYWORDS):
        score += EGO_KEYWORD_WEIGHT
        signals.append(f"low-impact keyword in title (+{EGO_KEYWORD_WEIGHT})")

    # Signal: doesn't touch src/
    if not touches_src and len(file_paths) > 0:
        score += EGO_NO_SRC_WEIGHT
        signals.append(f"no src/ changes (+{EGO_NO_SRC_WEIGHT})")

    return ScoredItem(item=item, score=score, signals=signals)


# ---------------------------------------------------------------------------
# Phase 4: Duplicate detection
# ---------------------------------------------------------------------------


def _tokenize(title: str) -> set[str]:
    words = re.sub(r"[^\w\s]", "", title.lower()).split()
    return {w for w in words if w not in STOP_WORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def detect_duplicates(issues: list[Item]) -> list[DuplicatePair]:
    pairs: list[DuplicatePair] = []
    tokens = [(issue, _tokenize(issue.title)) for issue in issues]

    for i in range(len(tokens)):
        for j in range(i + 1, len(tokens)):
            issue_a, tok_a = tokens[i]
            issue_b, tok_b = tokens[j]
            sim = _jaccard(tok_a, tok_b)
            if sim >= DUPLICATE_JACCARD_THRESHOLD:
                newer = issue_b if issue_b.number > issue_a.number else issue_a
                older = issue_a if newer is issue_b else issue_b
                pairs.append(
                    DuplicatePair(
                        item_a=older.number,
                        title_a=older.title,
                        item_b=newer.number,
                        title_b=newer.title,
                        similarity=sim,
                        recommendation=f"Close #{newer.number} (newer)",
                    )
                )
    return pairs


def detect_competing_prs(prs: list[Item]) -> list[DuplicatePair]:
    """Find PRs that reference the same issue — competing implementations."""
    issue_to_prs: dict[int, list[Item]] = {}
    for pr in prs:
        body = pr.body or ""
        for match in ISSUE_REF_EXTRACT_PATTERN.finditer(body):
            ref = match.group(1) or match.group(2)
            if ref:
                issue_num = int(ref)
                issue_to_prs.setdefault(issue_num, []).append(pr)

    pairs: list[DuplicatePair] = []
    for issue_num, competing in issue_to_prs.items():
        if len(competing) < 2:
            continue
        # report all pairs
        for i in range(len(competing)):
            for j in range(i + 1, len(competing)):
                pairs.append(
                    DuplicatePair(
                        item_a=competing[i].number,
                        title_a=competing[i].title,
                        item_b=competing[j].number,
                        title_b=competing[j].title,
                        similarity=0.0,
                        recommendation=f"Competing PRs for #{issue_num} — only one should merge",
                    )
                )
    return pairs


# ---------------------------------------------------------------------------
# Phase 5: Lifecycle enforcement
# ---------------------------------------------------------------------------


def check_lifecycle(issues: list[Item], prs: list[Item]) -> list[LifecycleViolation]:
    violations: list[LifecycleViolation] = []
    issues_with_prs = {
        int(ref)
        for pr in prs
        for match in ISSUE_REF_EXTRACT_PATTERN.finditer(pr.body or "")
        if (ref := match.group(1) or match.group(2))
    }

    for issue in issues:
        if "suspicious" in issue.labels:
            continue
        state_labels = [lb for lb in issue.labels if lb in LIFECYCLE_LABELS]

        if len(state_labels) == 0:
            if issue.number in issues_with_prs:
                inferred = "in-progress"
            else:
                inferred = "idea"
            violations.append(
                LifecycleViolation(
                    number=issue.number,
                    title=issue.title,
                    had="(none)",
                    applied=inferred,
                )
            )
        elif len(state_labels) > 1:
            # keep most advanced
            best = max(state_labels, key=lambda lb: LIFECYCLE_LABELS.index(lb))
            removed = [lb for lb in state_labels if lb != best]
            violations.append(
                LifecycleViolation(
                    number=issue.number,
                    title=issue.title,
                    had=", ".join(state_labels),
                    applied=best,
                )
            )

    return violations


# ---------------------------------------------------------------------------
# Phase 6: TTL / staleness
# ---------------------------------------------------------------------------


def check_ttl(issues: list[Item], prs: list[Item], today: date) -> list[StaleItem]:
    stale: list[StaleItem] = []

    for issue in issues:
        days = _days_since(issue.updated_at, today)
        if "needs-human" in issue.labels and days >= STALE_NEEDS_HUMAN_DAYS:
            stale.append(
                StaleItem(
                    number=issue.number,
                    item_type="Issue",
                    title=issue.title,
                    last_activity=issue.updated_at[:10],
                    days_stale=days,
                    reason="needs-human TTL (14d)",
                )
            )
        elif "idea" in issue.labels and days >= STALE_IDEA_DAYS:
            stale.append(
                StaleItem(
                    number=issue.number,
                    item_type="Issue",
                    title=issue.title,
                    last_activity=issue.updated_at[:10],
                    days_stale=days,
                    reason="stale idea (30d)",
                )
            )
        elif days >= STALE_IDEA_DAYS:
            stale.append(
                StaleItem(
                    number=issue.number,
                    item_type="Issue",
                    title=issue.title,
                    last_activity=issue.updated_at[:10],
                    days_stale=days,
                    reason=f"no activity ({days}d)",
                )
            )

    for pr in prs:
        days = _days_since(pr.updated_at, today)
        if days >= STALE_PR_DAYS:
            stale.append(
                StaleItem(
                    number=pr.number,
                    item_type="PR",
                    title=pr.title,
                    last_activity=pr.updated_at[:10],
                    days_stale=days,
                    reason="stale PR (21d)",
                )
            )

    stale.sort(key=lambda s: s.days_stale, reverse=True)
    return stale


def _days_since(iso_str: str, today: date) -> int:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (today - dt.date()).days
    except (ValueError, AttributeError):
        return 0


# ---------------------------------------------------------------------------
# Phase 7: Live-mode actions
# ---------------------------------------------------------------------------

SUSPICIOUS_COMMENT_TEMPLATE = """\
{marker}
## Triage Audit: Flagged as Suspicious

This item was flagged by the automated OSS Triage Auditor.

**Score:** {score}/100 (threshold: {threshold})

**Signals detected:**
{signals_list}

**What this means:** This item needs human review before proceeding.
If this is a legitimate contribution, a maintainer will remove the
`suspicious` label and restore the appropriate lifecycle label.

If you are the author: please respond explaining your intent and the
specific changes you're proposing.
"""

EGO_COMMENT_TEMPLATE = """\
{marker}
## Triage Audit: Flagged as Low-Impact Contribution

This PR was flagged because it appears to be a low-impact contribution
that does not address any tracked issue or provide meaningful functional change.

**Score:** {score}/100 (threshold: {threshold})

**Signals detected:**
{signals_list}

This is not a permanent rejection. If this PR addresses a real need,
please link to the relevant issue or explain the motivation.
"""


def apply_actions(findings: Findings, repo: str) -> None:
    """Apply mutations in live mode. Only uses integer issue numbers."""
    # Ensure suspicious label exists
    gh_run(
        [
            "label",
            "create",
            "suspicious",
            "--repo",
            repo,
            "--color",
            "D93F0B",
            "--description",
            "Flagged by triage audit — needs human review",
        ]
    )

    actions_taken = 0

    for scored in findings.suspicious:
        if _already_audited(scored.item, repo):
            continue
        _flag_item(scored, repo, SUSPICIOUS_COMMENT_TEMPLATE, SUSPICIOUS_THRESHOLD)
        actions_taken += 1
        if actions_taken % 20 == 0:
            time.sleep(LIVE_MODE_PAUSE_SECONDS)

    for scored in findings.ego_prs:
        if _already_audited(scored.item, repo):
            continue
        _flag_item(scored, repo, EGO_COMMENT_TEMPLATE, EGO_PR_THRESHOLD)
        actions_taken += 1
        if actions_taken % 20 == 0:
            time.sleep(LIVE_MODE_PAUSE_SECONDS)

    for stale_item in findings.stale:
        _close_stale(stale_item, repo)
        actions_taken += 1
        if actions_taken % 20 == 0:
            time.sleep(LIVE_MODE_PAUSE_SECONDS)

    typer.echo(f"  Applied {actions_taken} actions")


def _already_audited(item: Item, repo: str) -> bool:
    """Check if item already has suspicious label or audit comment."""
    if "suspicious" in item.labels:
        return True
    for comment in item.comments:
        if isinstance(comment, dict):
            body = str(comment.get("body", ""))
            if AUDIT_COMMENT_MARKER in body:
                return True
    return False


def _flag_item(scored: ScoredItem, repo: str, template: str, threshold: int) -> None:
    item = scored.item
    number = item.number
    signals_md = "\n".join(f"- {s}" for s in scored.signals)
    marker = f"{AUDIT_COMMENT_MARKER}-{date.today().isoformat()} -->"

    comment_body = template.format(
        marker=marker,
        score=scored.score,
        threshold=threshold,
        signals_list=signals_md,
    )

    cmd_prefix = "pr" if item.is_pr else "issue"

    # Remove lifecycle labels, add suspicious
    gh_run([cmd_prefix, "edit", str(number), "--repo", repo, "--add-label", "suspicious"])

    # Post comment
    gh_run([cmd_prefix, "comment", str(number), "--repo", repo, "--body", comment_body])


def _close_stale(stale: StaleItem, repo: str) -> None:
    marker = f"{AUDIT_COMMENT_MARKER}-{date.today().isoformat()} -->"
    close_body = (
        f"{marker}\n"
        f"Closing due to inactivity ({stale.days_stale} days with no updates).\n\n"
        f"**Reason:** {stale.reason}\n\n"
        "This is not permanent — reopen this issue if it's still relevant."
    )
    cmd_prefix = "pr" if stale.item_type == "PR" else "issue"
    gh_run([cmd_prefix, "close", str(stale.number), "--repo", repo, "--comment", close_body])


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(findings: Findings, mode: str, repo: str) -> str:
    today_str = date.today().isoformat()
    lines: list[str] = []

    lines.append(f"# OSS Triage Audit Report — {today_str}")
    lines.append("")
    lines.append(f"## Mode: {mode}")
    lines.append(f"## Target: {repo}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total open issues scanned: {findings.total_issues}")
    lines.append(f"- Total open PRs scanned: {findings.total_prs}")
    lines.append(f"- Suspicious items flagged: {len(findings.suspicious)}")
    lines.append(f"- Ego-PRs flagged: {len(findings.ego_prs)}")
    lines.append(f"- Duplicate pairs found: {len(findings.duplicates)}")
    lines.append(f"- Lifecycle violations: {len(findings.lifecycle_violations)}")
    lines.append(f"- Stale items: {len(findings.stale)}")

    # Suspicious
    lines.append("")
    lines.append("## Suspicious Items")
    if findings.suspicious:
        lines.append("| # | Title | Author | Score | Top Signals |")
        lines.append("|---|-------|--------|-------|-------------|")
        for s in sorted(findings.suspicious, key=lambda x: x.score, reverse=True):
            top = ", ".join(s.signals[:3])
            title_short = s.item.title[:60]
            lines.append(
                f"| #{s.item.number} | {title_short} | {s.item.author} | {s.score}/100 | {top} |"
            )
    else:
        lines.append("None found.")

    # Ego-PRs
    lines.append("")
    lines.append("## Ego-PRs")
    if findings.ego_prs:
        lines.append("| # | Title | Author | Score | Top Signals |")
        lines.append("|---|-------|--------|-------|-------------|")
        for s in sorted(findings.ego_prs, key=lambda x: x.score, reverse=True):
            top = ", ".join(s.signals[:3])
            title_short = s.item.title[:60]
            lines.append(
                f"| #{s.item.number} | {title_short} | {s.item.author} | {s.score}/100 | {top} |"
            )
    else:
        lines.append("None found.")

    # Duplicates
    lines.append("")
    lines.append("## Potential Duplicates")
    if findings.duplicates:
        lines.append("| Item A | Item B | Similarity | Recommendation |")
        lines.append("|--------|--------|------------|----------------|")
        for d in findings.duplicates:
            sim = f"{d.similarity:.2f}" if d.similarity > 0 else "—"
            lines.append(f"| #{d.item_a} | #{d.item_b} | {sim} | {d.recommendation} |")
    else:
        lines.append("None found.")

    # Lifecycle
    lines.append("")
    lines.append("## Lifecycle Violations")
    if findings.lifecycle_violations:
        lines.append("| # | Title | Had | Applied |")
        lines.append("|---|-------|-----|---------|")
        for v in findings.lifecycle_violations:
            title_short = v.title[:60]
            lines.append(f"| #{v.number} | {title_short} | {v.had} | {v.applied} |")
    else:
        lines.append("None found.")

    # Stale
    lines.append("")
    lines.append("## Stale Items")
    if findings.stale:
        lines.append("| # | Type | Title | Last Activity | Days Stale | Reason |")
        lines.append("|---|------|-------|--------------|------------|--------|")
        for s in findings.stale:
            title_short = s.title[:50]
            lines.append(
                f"| #{s.number} | {s.item_type} | {title_short} "
                f"| {s.last_activity} | {s.days_stale} | {s.reason} |"
            )
    else:
        lines.append("None found.")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

app = typer.Typer(help="OSS Triage Auditor — scan GitHub issues/PRs for spam and hygiene issues.")


@app.command()
def main(
    mode: str = typer.Argument(
        "dry-run", help="Audit mode: 'dry-run' (report only) or 'live' (apply actions)"
    ),
    repo: str = typer.Option(
        "", help="Target repo as owner/repo. Defaults to current repo from gh CLI."
    ),
) -> None:
    """Run the OSS Triage Audit against a GitHub repository."""
    if mode not in ("dry-run", "live"):
        typer.echo(f"Invalid mode: {mode}. Use 'dry-run' or 'live'.", err=True)
        raise typer.Exit(code=1)

    # Resolve repo
    if not repo:
        result = gh_run(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
        repo = result.stdout.strip()
        if not repo:
            typer.echo("Could not detect current repo. Use --repo owner/repo.", err=True)
            raise typer.Exit(code=1)

    typer.echo(f"OSS Triage Audit — mode: {mode}, repo: {repo}")
    typer.echo("=" * 60)

    # Phase 1: Data collection
    issues, prs, labels = fetch_data(repo)
    all_items = issues + prs

    # Build author counts for bulk submission detection
    author_counts: dict[str, int] = {}
    for item in all_items:
        if item.author:
            author_counts[item.author] = author_counts.get(item.author, 0) + 1

    merged_cache: dict[str, bool] = {}
    findings = Findings(total_issues=len(issues), total_prs=len(prs))

    # Phase 2: Suspicious content
    typer.echo("Scoring suspicious content...")
    for item in all_items:
        scored = score_suspicious(item, author_counts, merged_cache, repo)
        if scored.score >= SUSPICIOUS_THRESHOLD:
            findings.suspicious.append(scored)

    # Phase 3: Ego-PR detection
    typer.echo("Scoring ego-PRs...")
    for pr in prs:
        scored = score_ego_pr(pr, repo)
        if scored.score >= EGO_PR_THRESHOLD:
            findings.ego_prs.append(scored)

    # Phase 4: Duplicate detection
    typer.echo("Detecting duplicates...")
    findings.duplicates = detect_duplicates(issues) + detect_competing_prs(prs)

    # Phase 5: Lifecycle enforcement
    typer.echo("Checking lifecycle labels...")
    findings.lifecycle_violations = check_lifecycle(issues, prs)

    # Phase 6: TTL / staleness
    typer.echo("Checking staleness...")
    findings.stale = check_ttl(issues, prs, date.today())

    # Phase 7: Apply actions (live mode only)
    if mode == "live":
        typer.echo("Applying actions...")
        apply_actions(findings, repo)

    # Generate and output report
    report = generate_report(findings, mode, repo)
    typer.echo("")
    typer.echo(report)


if __name__ == "__main__":
    app()
