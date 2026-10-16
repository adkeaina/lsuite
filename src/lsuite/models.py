"""Stable, transport-independent result contracts."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, List, Optional


class LSuiteError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 1):
        super().__init__(message)
        self.code, self.message, self.exit_code = code, message, exit_code


@dataclass
class SectionResult:
    status: str
    data: Any
    sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    complete: bool = True
    reason: Optional[dict] = None
    transport: str = 'http'


def envelope(command: str, course: Optional[str], result: SectionResult, transport: str) -> dict:
    return dict(schema_version='1.0', command=command, course=course,
                retrieved_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                **dict(asdict(result), transport=transport))
