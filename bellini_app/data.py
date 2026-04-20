from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

import pandas as pd


SEMESTER_FILE_MAP = {
    "S25": "Bellini Classes S25.xlsx",
    "F25": "Bellini Classes F25.xlsx",
    "S26": "Bellini Classes S26.xlsx",
}

NEW_CLASSES_FILE = "Bellini Classes S26_NewClassesToBeAddedWhenSystemReady.xlsx"


STANDARD_COLUMN_MAP = {
    "TERM": "term",
    "CAMPUS": "campus",
    "CRSE_LEVL": "course_level",
    "CRSE LEVL": "course_level",
    "CRSE_SECTION": "course_section",
    "CRSE SECTION": "course_section",
    "CRN": "crn",
    "SUBJ": "subject",
    "CRSE_NUMB": "course_number",
    "CRSE NUMB": "course_number",
    "CRSE_TITLE": "course_title",
    "CRSE TITLE": "course_title",
    "Grad Hours": "grad_hours",
    "UG Hours": "ug_hours",
    "TA Hours": "ta_hours",
    "Graduate TA(s)": "grad_tas",
    "Grad TAS": "grad_tas",
    "Grad TAs": "grad_tas",
    "UGTA(s)": "ug_tas",
    "UGTAs": "ug_tas",
    "UGTA Emails": "ugta_emails",
    "Grad TA Emails": "grad_ta_emails",
    "ENROLLMENT": "enrollment",
    "PRIOR SECT ENRL": "prior_section_enrollment",
    "WAIT LIST ACTUAL": "wait_list_actual",
    "WAIT LIST MAX": "wait_list_max",
    "START DATE": "start_date",
    "END DATE": "end_date",
    "MULTIPLE SECTIONS": "multiple_sections",
    "MEETING_DAYS": "meeting_days",
    "MEETING DAYS": "meeting_days",
    "MEETING_TIMES": "meeting_times",
    "MEETING TIMES": "meeting_times",
    "MEETING TIMES1": "meeting_times",
    "MEETING_ROOM": "meeting_room",
    "MEETING ROOM": "meeting_room",
    "INSTRUCTOR": "instructor",
    "INSTRUCTOR EMAIL": "instructor_email",
}

DISPLAY_COLUMNS = [
    "semester",
    "crn",
    "subject",
    "course_number",
    "course_title",
    "meeting_days",
    "meeting_times",
    "meeting_room",
    "instructor",
    "enrollment",
    "room_capacity",
]


@dataclass
class BelliniRepository:
    base_dir: Path
    include_new_classes: bool = False

    def load_all(self) -> pd.DataFrame:
        frames: List[pd.DataFrame] = []
        for semester, filename in SEMESTER_FILE_MAP.items():
            frames.append(self._load_one(self.base_dir / filename, semester))
        if self.include_new_classes:
            frames.append(self._load_one(self.base_dir / NEW_CLASSES_FILE, "S26_NEW"))
        combined = pd.concat(frames, ignore_index=True)
        combined = self._post_process(combined)
        return combined

    def _load_one(self, path: Path, semester_label: str) -> pd.DataFrame:
        xls = pd.ExcelFile(path)
        df = pd.read_excel(path, sheet_name=xls.sheet_names[0])
        rename_map = {col: STANDARD_COLUMN_MAP.get(col, self._slug(col)) for col in df.columns}
        df = df.rename(columns=rename_map)
        df["semester"] = semester_label
        return df

    def _post_process(self, df: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "campus": "Tampa",
            "enrollment": 0,
            "meeting_days": "TBA",
            "meeting_times": "TBA",
            "meeting_room": "TBA",
            "instructor": "TBA",
        }
        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default
        # Ensure 'enrollment' column is properly handled
        enrollment_col = df.get("enrollment")
        if enrollment_col is not None:
            df["enrollment"] = pd.to_numeric(enrollment_col, errors="coerce").fillna(0).astype(int)
        else:
            df["enrollment"] = 0
        df["crn"] = pd.to_numeric(df.get("crn"), errors="coerce")
        df["course_section"] = pd.to_numeric(df.get("course_section"), errors="coerce")
        df["course_key"] = df["subject"].fillna("").astype(str).str.strip() + " " + df["course_number"].fillna("").astype(str).str.strip()
        df["section_key"] = df["course_key"] + "-" + df["course_section"].fillna("").astype("Int64").astype(str)
        df["meeting_days"] = df["meeting_days"].fillna("TBA").astype(str).str.strip()
        df["meeting_times"] = df["meeting_times"].fillna("TBA").astype(str).str.strip()
        df["meeting_room"] = df["meeting_room"].fillna("TBA").astype(str).str.strip()
        df["instructor"] = df["instructor"].fillna("TBA").astype(str).str.strip()
        df["course_title"] = df["course_title"].fillna("").astype(str).str.strip()
        df["subject"] = df["subject"].fillna("").astype(str).str.strip()
        df["course_number"] = df["course_number"].fillna("").astype(str).str.strip()

        start_end = df["meeting_times"].apply(parse_time_range)
        df["start_minutes"] = start_end.apply(lambda x: x[0])
        df["end_minutes"] = start_end.apply(lambda x: x[1])
        df["has_meeting"] = df["start_minutes"].notna() & df["end_minutes"].notna() & (df["meeting_days"] != "TBA")

        room_capacity = (
            df[df["meeting_room"].ne("TBA")]
            .groupby("meeting_room")["enrollment"]
            .max()
            .to_dict()
        )
        df["room_capacity"] = df["meeting_room"].map(room_capacity).fillna(df["enrollment"]).astype(int)
        return df

    @staticmethod
    def _slug(text: str) -> str:
        text = text.strip().lower()
        return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def parse_time_range(value: str) -> Tuple[Optional[int], Optional[int]]:
    if not isinstance(value, str) or "-" not in value:
        return None, None
    try:
        start_raw, end_raw = [x.strip() for x in value.split("-")]
        start = pd.to_datetime(start_raw).hour * 60 + pd.to_datetime(start_raw).minute
        end = pd.to_datetime(end_raw).hour * 60 + pd.to_datetime(end_raw).minute
        return int(start), int(end)
    except Exception:
        return None, None


def days_overlap(days_a: str, days_b: str) -> bool:
    set_a = set(str(days_a).replace(" ", ""))
    set_b = set(str(days_b).replace(" ", ""))
    return bool(set_a & set_b)


def time_overlap(start_a: Optional[int], end_a: Optional[int], start_b: Optional[int], end_b: Optional[int]) -> bool:
    if None in {start_a, end_a, start_b, end_b}:
        return False
    return max(start_a or 0, start_b or 0) < min(end_a or float('inf'), end_b or float('inf'))
