from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from .utils import normalize_numeric_string, normalize_text, parse_enrollment, parse_time_range


COLUMN_ALIASES = {
    "CRSE LEVL": "CRSE_LEVL",
    "CRSE SECTION": "CRSE_SECTION",
    "CRSE NUMB": "CRSE_NUMB",
    "CRSE TITLE": "CRSE_TITLE",
    "MEETING DAYS": "MEETING_DAYS",
    "MEETING TIMES1": "MEETING_TIMES",
    "MEETING ROOM": "MEETING_ROOM",
    "TA Hours": "TA_HOURS",
    "PRIOR SECT ENRL": "PRIOR_SECT_ENRL",
    "WAIT LIST ACTUAL": "WAIT_LIST_ACTUAL",
    "WAIT LIST MAX": "WAIT_LIST_MAX",
    "Grad TAs": "GRAD_TAS",
    "Grad TAS": "GRAD_TAS",
    "Graduate TA(s)": "GRAD_TAS",
    "UGTA(s)": "UGTAS",
}

SEMESTER_PATHS = {
    "S25": "Bellini Classes S25.xlsx",
    "F25": "Bellini Classes F25.xlsx",
    "S26": "Bellini Classes S26.xlsx",
    "S26_NEW": "Bellini Classes S26_NewClassesToBeAddedWhenSystemReady.xlsx",
}


class BelliniDataLoader:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load_all(self, include_new_classes: bool = True) -> pd.DataFrame:
        frames = []
        for semester, filename in SEMESTER_PATHS.items():
            if semester == "S26_NEW" and not include_new_classes:
                continue
            frames.append(self.load_semester(semester, filename))
        return pd.concat(frames, ignore_index=True)

    def load_base_semesters(self) -> Dict[str, pd.DataFrame]:
        return {
            semester: self.load_semester(semester, filename)
            for semester, filename in SEMESTER_PATHS.items()
            if semester != "S26_NEW"
        }

    def load_semester(self, semester: str, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        xl = pd.ExcelFile(path)
        df = xl.parse(xl.sheet_names[0])
        df = self._normalize_dataframe(df, semester)
        return df

    def _normalize_dataframe(self, df: pd.DataFrame, semester: str) -> pd.DataFrame:
        renamed = {}
        for col in df.columns:
            key = normalize_text(col)
            key = COLUMN_ALIASES.get(key, key)
            key = key.upper().replace(" ", "_")
            renamed[col] = key
        df = df.rename(columns=renamed)

        for required in [
            "TERM", "CAMPUS", "CRSE_LEVL", "CRSE_SECTION", "CRN", "SUBJ", "CRSE_NUMB", "CRSE_TITLE",
            "ENROLLMENT", "MEETING_DAYS", "MEETING_TIMES", "MEETING_ROOM", "INSTRUCTOR", "INSTRUCTOR_EMAIL",
            "GRAD_TAS", "UGTAS",
        ]:
            if required not in df.columns:
                df[required] = ""

        records = []
        for _, row in df.iterrows():
            start_time, end_time = parse_time_range(row.get("MEETING_TIMES", ""))
            subject = normalize_text(row.get("SUBJ", ""))
            course_number = normalize_numeric_string(row.get("CRSE_NUMB", ""))
            course_code = f"{subject}{course_number}"
            records.append({
                "semester": semester,
                "term": normalize_numeric_string(row.get("TERM", "")),
                "campus": normalize_text(row.get("CAMPUS", "Tampa")) or "Tampa",
                "course_level": normalize_text(row.get("CRSE_LEVL", "")),
                "course_section": normalize_numeric_string(row.get("CRSE_SECTION", "")),
                "crn": normalize_numeric_string(row.get("CRN", "")),
                "subject": subject,
                "course_number": course_number,
                "course_code": course_code,
                "course_title": normalize_text(row.get("CRSE_TITLE", "")),
                "enrollment": parse_enrollment(row.get("ENROLLMENT", 0)),
                "meeting_days": normalize_text(row.get("MEETING_DAYS", "")),
                "meeting_times": normalize_text(row.get("MEETING_TIMES", "")),
                "meeting_room": normalize_text(row.get("MEETING_ROOM", "")),
                "instructor": normalize_text(row.get("INSTRUCTOR", "")),
                "instructor_email": normalize_text(row.get("INSTRUCTOR_EMAIL", "")),
                "grad_tas": normalize_text(row.get("GRAD_TAS", "")),
                "ugtas": normalize_text(row.get("UGTAS", "")),
                "start_time": start_time,
                "end_time": end_time,
            })
        return pd.DataFrame.from_records(records)
