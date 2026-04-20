from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Optional


@dataclass
class CourseSection:
    semester: str
    term: str
    campus: str
    course_level: str
    course_section: str
    crn: str
    subject: str
    course_number: str
    course_title: str
    enrollment: int
    meeting_days: str
    meeting_times: str
    meeting_room: str
    instructor: str
    instructor_email: str
    graduate_tas: str = ""
    ugtas: str = ""
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @property
    def course_code(self) -> str:
        return f"{self.subject}{self.course_number}"


@dataclass
class AuditViolation:
    violation_type: str
    semester: str
    crn_1: str
    crn_2: str = ""
    details: str = ""


@dataclass
class SeasonalCourse:
    course_code: str
    course_title: str
    pattern: str
    graduation_risk: str
    semesters_present: list[str] = field(default_factory=list)
