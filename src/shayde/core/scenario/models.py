"""Data models for scenario execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class StepStatus(str, Enum):
    """Step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Priority(str, Enum):
    """Scenario priority."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CoverageStatus(str, Enum):
    """Coverage status."""
    COMPLETE = "complete"
    PARTIAL = "partial"


@dataclass
class AssertionResult:
    """Result of a single assertion."""
    type: str
    expected: Any
    actual: Any
    passed: bool
    message: Optional[str] = None


@dataclass
class StepResult:
    """Result of a single step execution."""
    step_id: str
    desc: str
    status: StepStatus
    screenshot: Optional[Path] = None
    duration_ms: int = 0
    assertions: list[AssertionResult] = field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.step_id,
            "desc": self.desc,
            "status": self.status.value,
            "screenshot": str(self.screenshot) if self.screenshot else None,
            "duration_ms": self.duration_ms,
            "assertions": [
                {
                    "type": a.type,
                    "expected": a.expected,
                    "actual": a.actual,
                    "passed": a.passed,
                    "message": a.message,
                }
                for a in self.assertions
            ],
            "error": self.error,
        }


@dataclass
class PartResult:
    """Result of a part execution."""
    part: int
    title: str
    status: StepStatus
    steps: list[StepResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.PASSED)

    @property
    def failed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "part": self.part,
            "title": self.title,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class ScenarioResult:
    """Result of a scenario execution."""
    scenario_id: str
    title: str
    status: StepStatus
    parts: list[PartResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_dir: Optional[Path] = None
    video_path: Optional[Path] = None

    @property
    def total_steps(self) -> int:
        return sum(len(p.steps) for p in self.parts)

    @property
    def passed_count(self) -> int:
        return sum(p.passed_count for p in self.parts)

    @property
    def failed_count(self) -> int:
        return sum(p.failed_count for p in self.parts)

    @property
    def skipped_count(self) -> int:
        return sum(
            1 for p in self.parts for s in p.steps if s.status == StepStatus.SKIPPED
        )

    @property
    def duration_ms(self) -> int:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return sum(s.duration_ms for p in self.parts for s in p.steps)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "video_path": str(self.video_path) if self.video_path else None,
            "parts": [p.to_dict() for p in self.parts],
            "summary": {
                "total_steps": self.total_steps,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "skipped": self.skipped_count,
                "duration_ms": self.duration_ms,
            },
        }
