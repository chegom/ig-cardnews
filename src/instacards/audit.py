"""Visual quality audit gate for composed carousel cards.

The composer draws Korean copy onto AI-generated backgrounds.  This module
inspects the *result* — the rendered card plus the layout manifest the composer
emits — and refuses to call a deck finished when text is unreadable, spills past
the safe area, crams too much copy onto one card, or places the brand furniture
inconsistently.

Findings are graded ``red`` / ``yellow`` / ``green``.  A single ``red`` finding
fails the gate (exit code 1), mirroring a build break.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

Rgb = tuple[int, int, int]

# Roles whose copy is dense enough to demand the stricter AA body threshold.
_BODY_ROLES = frozenset({"body"})
# Brand furniture that should sit at the same anchor on every card of a deck.
_FURNITURE_ROLES = ("brand", "page")


@dataclass(frozen=True)
class AuditRules:
    """Thresholds the audit measures a rendered card against."""

    min_contrast_large: float = 3.0
    min_contrast_body: float = 4.5
    contrast_yellow_band: float = 1.5
    body_lines_soft: int = 5
    body_lines_hard: int = 6
    furniture_tolerance: int = 14

    def required_contrast(self, role: str) -> float:
        return self.min_contrast_body if role in _BODY_ROLES else self.min_contrast_large


DEFAULT_RULES = AuditRules()


def load_rules(path: Path | None) -> AuditRules:
    """Load audit thresholds, overriding only the keys the file supplies."""
    if path is None:
        return DEFAULT_RULES
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("audit rules file must contain a JSON object")
    known = {f.name for f in fields(AuditRules)}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"unknown audit rule keys: {sorted(unknown)}")
    return AuditRules(**{**{f.name: getattr(DEFAULT_RULES, f.name) for f in fields(AuditRules)}, **raw})


@dataclass(frozen=True)
class Finding:
    """One graded problem the audit found on a card."""

    slide: int
    role: str
    code: str
    level: str  # "red" | "yellow"
    message: str


@dataclass(frozen=True)
class AuditReport:
    """The graded result of auditing a whole deck."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def worst_level(self) -> str:
        levels = {f.level for f in self.findings}
        if "red" in levels:
            return "red"
        if "yellow" in levels:
            return "yellow"
        return "green"

    @property
    def ok(self) -> bool:
        return self.worst_level != "red"

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    @property
    def counts(self) -> dict[str, int]:
        tally = {"red": 0, "yellow": 0}
        for finding in self.findings:
            tally[finding.level] = tally.get(finding.level, 0) + 1
        return tally

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "worst_level": self.worst_level,
            "exit_code": self.exit_code,
            "counts": self.counts,
            "findings": [
                {
                    "slide": f.slide,
                    "role": f.role,
                    "code": f.code,
                    "level": f.level,
                    "message": f.message,
                }
                for f in self.findings
            ],
        }

    def to_text(self) -> str:
        if not self.findings:
            return "audit: 모든 카드 통과 (green)"
        symbol = {"red": "●", "yellow": "○"}
        lines = [f"audit: {self.worst_level.upper()} — red {self.counts['red']}, yellow {self.counts['yellow']}"]
        for f in sorted(self.findings, key=lambda item: (item.level != "red", item.slide)):
            lines.append(f"  {symbol.get(f.level, '?')} s{f.slide:02d} [{f.code}] {f.message}")
        return "\n".join(lines)


def _channel_luminance(value: int) -> float:
    srgb = value / 255.0
    return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: Rgb) -> float:
    """WCAG 2.1 relative luminance of an sRGB colour."""
    red, green, blue = rgb
    return 0.2126 * _channel_luminance(red) + 0.7152 * _channel_luminance(green) + 0.0722 * _channel_luminance(blue)


def contrast_ratio(foreground: Rgb, background: Rgb) -> float:
    """WCAG 2.1 contrast ratio between two colours (1.0 .. 21.0)."""
    lighter = relative_luminance(foreground)
    darker = relative_luminance(background)
    if lighter < darker:
        lighter, darker = darker, lighter
    return (lighter + 0.05) / (darker + 0.05)


def hex_to_rgb(value: str) -> Rgb:
    text = value.lstrip("#")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def _check_contrast(slide: int, element: dict, rules: AuditRules) -> Finding | None:
    role = str(element["role"])
    ratio = contrast_ratio(hex_to_rgb(str(element["color"])), tuple(element["bg_rgb"]))
    required = rules.required_contrast(role)
    if ratio >= required + rules.contrast_yellow_band:
        return None
    level = "red" if ratio < required else "yellow"
    return Finding(
        slide=slide,
        role=role,
        code="contrast",
        level=level,
        message=f"{role} 대비 {ratio:.1f}:1 (최소 {required:.1f}:1 권장)",
    )


def _check_overflow(slide: int, element: dict, safe_area: list[int]) -> Finding | None:
    left, top, right, bottom = safe_area
    x0, y0, x1, y1 = element["bbox"]
    if x0 >= left and y0 >= top and x1 <= right and y1 <= bottom:
        return None
    return Finding(
        slide=slide,
        role=str(element["role"]),
        code="overflow",
        level="red",
        message=f"{element['role']}가 안전영역을 벗어남 (bbox {element['bbox']} / safe {safe_area})",
    )


def _check_density(slide: int, element: dict, rules: AuditRules) -> Finding | None:
    if element.get("role") not in _BODY_ROLES:
        return None
    lines = int(element.get("lines", 0))
    if lines <= rules.body_lines_soft:
        return None
    level = "red" if lines > rules.body_lines_hard else "yellow"
    return Finding(
        slide=slide,
        role=str(element["role"]),
        code="density",
        level=level,
        message=f"본문 {lines}줄 (권장 {rules.body_lines_soft}줄 이하)",
    )


def audit_card(manifest: dict, rules: AuditRules = DEFAULT_RULES) -> list[Finding]:
    """Grade one card from its layout manifest."""
    slide = int(manifest["slide"])
    safe_area = manifest["safe_area"]
    findings: list[Finding] = []
    for element in manifest["elements"]:
        for check in (
            _check_contrast(slide, element, rules),
            _check_overflow(slide, element, safe_area),
            _check_density(slide, element, rules),
        ):
            if check is not None:
                findings.append(check)
    return findings


def _find_role(manifest: dict, role: str) -> dict | None:
    for element in manifest["elements"]:
        if element.get("role") == role:
            return element
    return None


def _check_furniture_consistency(manifests: list[dict], rules: AuditRules) -> list[Finding]:
    findings: list[Finding] = []
    for role in _FURNITURE_ROLES:
        placed = [(int(m["slide"]), _find_role(m, role)) for m in manifests]
        placed = [(slide, element) for slide, element in placed if element is not None]
        if len(placed) < 2:
            continue
        tops = [element["bbox"][1] for _, element in placed]
        spread = max(tops) - min(tops)
        if spread <= rules.furniture_tolerance:
            continue
        median = sorted(tops)[len(tops) // 2]
        outlier = max(placed, key=lambda item: abs(item[1]["bbox"][1] - median))
        findings.append(
            Finding(
                slide=outlier[0],
                role=role,
                code="furniture",
                level="yellow",
                message=f"{role} 세로 위치가 장마다 다름 (편차 {spread}px, 허용 {rules.furniture_tolerance}px)",
            )
        )
    return findings


def audit_deck(manifests: list[dict], rules: AuditRules = DEFAULT_RULES) -> AuditReport:
    """Grade a whole deck: every card plus cross-card furniture consistency."""
    findings: list[Finding] = []
    for manifest in manifests:
        findings.extend(audit_card(manifest, rules))
    findings.extend(_check_furniture_consistency(manifests, rules))
    return AuditReport(findings=findings)


def load_manifests(directory: Path) -> list[dict]:
    """Load every ``NN.layout.json`` from a cards directory, sorted by slide."""
    paths = sorted(Path(directory).glob("*.layout.json"))
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return sorted(manifests, key=lambda item: int(item.get("slide", 0)))


def audit_directory(directory: Path, rules: AuditRules = DEFAULT_RULES) -> AuditReport:
    """Load the manifests from a cards directory and grade the deck."""
    manifests = load_manifests(directory)
    if not manifests:
        raise FileNotFoundError(f"no layout manifests found in {directory}")
    return audit_deck(manifests, rules)
