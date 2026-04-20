from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

import pandas as pd

from .utils import DAY_MAP, meeting_day_letters, overlap, safe_contains_any, shared_days


DEFAULT_ROOM_CAPACITY = {
    "CHE 111": 120,
    "CHE 103": 80,
    "CHE 100": 80,
    "CMC 141": 100,
    "CPR 103": 80,
    "CPR 115": 60,
    "CWY 107": 150,
    "ENB 118": 70,
    "ISA 1061": 70,
    "ULH 101": 130,
    "EDU 347": 45,
    "BEH 104": 100,
    "SOC 150": 70,
    "TBAT TBA": 0,
}

DEFAULT_PREREQUISITES = {
    "CGS1540": ["COP3515", "CIS3433"],
    "COP3515": ["COP4400", "COP4530"],
    "COP4530": ["COP4930"],
    "CAI4105": ["CAI5205", "CAP4773"],
    "CAI5005": ["CAI5107", "CAI5307"],
    "CEN4020": ["CIS4910"],
}


class BelliniRepository:
    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe.copy()

    def semesters(self) -> list[str]:
        return sorted(self.df["semester"].dropna().unique().tolist())

    def by_semester(self, semester: str) -> pd.DataFrame:
        return self.df[self.df["semester"] == semester].copy()

    def all_data(self) -> pd.DataFrame:
        return self.df.copy()

    def add_class(self, class_data: dict) -> None:
        self.df = pd.concat([self.df, pd.DataFrame([class_data])], ignore_index=True)

    def update_class(self, crn: str, updated_data: dict) -> bool:
        idx = self.df.index[self.df["crn"] == crn]
        if len(idx) == 0:
            return False
        for key, value in updated_data.items():
            self.df.loc[idx[0], key] = value
        return True

    def delete_class(self, crn: str) -> bool:
        before = len(self.df)
        self.df = self.df[self.df["crn"] != crn].copy()
        return len(self.df) < before


class AuditService:
    def __init__(self, room_capacity: dict[str, int] | None = None):
        self.room_capacity = room_capacity or DEFAULT_ROOM_CAPACITY

    def audit_integrity(self, df: pd.DataFrame) -> pd.DataFrame:
        violations: list[dict] = []

        duplicates = df[df["crn"].duplicated(keep=False) & (df["crn"] != "")]
        for crn, group in duplicates.groupby("crn"):
            violations.append({
                "type": "Duplicate CRN",
                "semester": ", ".join(sorted(group["semester"].unique())),
                "crn_1": crn,
                "crn_2": "",
                "details": f"CRN {crn} appears {len(group)} times.",
            })

        rows = df.reset_index(drop=True)
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = rows.loc[i]
                b = rows.loc[j]
                if a["semester"] != b["semester"]:
                    continue
                if not shared_days(a["meeting_days"], b["meeting_days"]):
                    continue
                if not overlap(a["start_time"], a["end_time"], b["start_time"], b["end_time"]):
                    continue
                if a["meeting_room"] and a["meeting_room"] == b["meeting_room"]:
                    violations.append({
                        "type": "Room Conflict",
                        "semester": a["semester"],
                        "crn_1": a["crn"],
                        "crn_2": b["crn"],
                        "details": f"Both meet in {a['meeting_room']} at overlapping times.",
                    })
                if a["instructor"] and a["instructor"] == b["instructor"]:
                    violations.append({
                        "type": "Instructor Conflict",
                        "semester": a["semester"],
                        "crn_1": a["crn"],
                        "crn_2": b["crn"],
                        "details": f"Instructor {a['instructor']} teaches both sections at overlapping times.",
                    })

        incomplete = df[(df["crn"] == "") | (df["meeting_room"] == "") | (df["meeting_times"] == "")]
        for _, row in incomplete.iterrows():
            violations.append({
                "type": "Incomplete Data",
                "semester": row["semester"],
                "crn_1": row["crn"],
                "crn_2": "",
                "details": "Missing CRN, meeting room, or meeting times.",
            })
        return pd.DataFrame(violations)

    def low_capacity_rooms(self, df: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
        rows = []
        for _, row in df.iterrows():
            room = row["meeting_room"]
            capacity = self.room_capacity.get(room, 0)
            utilization = (row["enrollment"] / capacity) if capacity else 0
            if capacity and utilization < threshold:
                rows.append({
                    "semester": row["semester"],
                    "crn": row["crn"],
                    "course_code": row["course_code"],
                    "course_title": row["course_title"],
                    "room": room,
                    "enrollment": row["enrollment"],
                    "capacity": capacity,
                    "utilization_pct": round(utilization * 100, 1),
                })
        return pd.DataFrame(rows).sort_values(["semester", "utilization_pct"]) if rows else pd.DataFrame()


class SearchService:
    def keyword_search(self, df: pd.DataFrame, keyword_text: str) -> pd.DataFrame:
        keywords = [part.strip() for part in keyword_text.split(",") if part.strip()]
        if not keywords:
            return df.iloc[0:0].copy()
        mask = df.apply(
            lambda row: safe_contains_any(row["course_title"], keywords) or safe_contains_any(row["course_code"], keywords),
            axis=1,
        )
        return df[mask].sort_values(["semester", "course_code", "crn"])


class ScheduleService:
    def build_schedule(self, df: pd.DataFrame, semester: str, crns: Iterable[str]) -> tuple[pd.DataFrame, list[dict]]:
        clean_crns = [str(crn).strip() for crn in crns if str(crn).strip()]
        semester_df = df[df["semester"] == semester].copy()
        schedule_df = semester_df[semester_df["crn"].isin(clean_crns)].copy()
        valid_crns = set(schedule_df["crn"].tolist())
        invalid_crns = [crn for crn in clean_crns if crn not in valid_crns]
        conflicts = []
        rows = schedule_df.reset_index(drop=True)
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = rows.loc[i]
                b = rows.loc[j]
                if shared_days(a["meeting_days"], b["meeting_days"]) and overlap(a["start_time"], a["end_time"], b["start_time"], b["end_time"]):
                    conflicts.append({
                        "crn_1": a["crn"],
                        "crn_2": b["crn"],
                        "shared_days": ", ".join(DAY_MAP[d] for d in shared_days(a["meeting_days"], b["meeting_days"])),
                        "details": f"{a['course_code']} overlaps with {b['course_code']}",
                    })
        for crn in invalid_crns:
            conflicts.append({"crn_1": crn, "crn_2": "", "shared_days": "", "details": f"Invalid CRN: {crn}"})
        return schedule_df, conflicts

    def weekly_grid(self, schedule_df: pd.DataFrame) -> pd.DataFrame:
        slots = [
            "08:00 AM - 09:15 AM", "09:30 AM - 10:45 AM", "11:00 AM - 12:15 PM", "12:30 PM - 01:45 PM",
            "02:00 PM - 03:15 PM", "03:30 PM - 04:45 PM", "05:00 PM - 06:15 PM", "06:30 PM - 07:45 PM",
        ]
        grid = pd.DataFrame("", index=slots, columns=[DAY_MAP[d] for d in ["M", "T", "W", "R", "F"]])
        for _, row in schedule_df.iterrows():
            label = f"{row['course_code']}\nCRN {row['crn']}\n{row['meeting_room']}"
            for d in meeting_day_letters(row["meeting_days"]):
                day = DAY_MAP.get(d)
                if day in grid.columns and row["meeting_times"] in grid.index:
                    existing = grid.loc[row["meeting_times"], day]
                    grid.loc[row["meeting_times"], day] = label if not existing else f"{existing}\n⚠ CONFLICT\n{label}"
        return grid


class AnalyticsService:
    def course_frequency(self, df: pd.DataFrame) -> pd.DataFrame:
        pivot = (
            df.groupby(["course_code", "course_title", "semester"])
            .size()
            .reset_index(name="section_count")
            .pivot_table(index=["course_code", "course_title"], columns="semester", values="section_count", fill_value=0)
            .reset_index()
        )
        for semester in ["S25", "F25", "S26"]:
            if semester not in pivot.columns:
                pivot[semester] = 0
        pivot["total_sections"] = pivot[["S25", "F25", "S26"]].sum(axis=1)
        pivot["bottleneck_flag"] = pivot[["S25", "F25", "S26"]].min(axis=1) <= 1
        return pivot.sort_values(["bottleneck_flag", "total_sections", "course_code"], ascending=[False, True, True])

    def seasonal_courses(self, df: pd.DataFrame) -> pd.DataFrame:
        grouped = (
            df.groupby(["course_code", "course_title", "semester"])
            .size()
            .reset_index(name="count")
            .pivot_table(index=["course_code", "course_title"], columns="semester", values="count", fill_value=0)
            .reset_index()
        )
        for semester in ["S25", "F25", "S26"]:
            if semester not in grouped.columns:
                grouped[semester] = 0
        def classify(row):
            if row["S25"] > 0 and row["S26"] > 0 and row["F25"] == 0:
                return "Spring-Only"
            if row["F25"] > 0 and row["S25"] == 0 and row["S26"] == 0:
                return "Fall-Only"
            return "Every Semester / Mixed"
        grouped["pattern"] = grouped.apply(classify, axis=1)
        grouped = grouped[grouped["pattern"] != "Every Semester / Mixed"].copy()
        grouped["graduation_risk"] = grouped["pattern"].map({"Spring-Only": "High", "Fall-Only": "Medium"})
        return grouped.sort_values(["graduation_risk", "course_code"], ascending=[True, True])

    def prerequisite_conflicts(self, df: pd.DataFrame, prerequisite_map: dict[str, list[str]] | None = None) -> pd.DataFrame:
        prerequisite_map = prerequisite_map or DEFAULT_PREREQUISITES
        by_semester = []
        for semester, sem_df in df.groupby("semester"):
            rows = sem_df.reset_index(drop=True)
            for prereq, follow_ups in prerequisite_map.items():
                prereq_rows = rows[rows["course_code"] == prereq]
                follow_rows = rows[rows["course_code"].isin(follow_ups)]
                for _, a in prereq_rows.iterrows():
                    for _, b in follow_rows.iterrows():
                        if shared_days(a["meeting_days"], b["meeting_days"]) and overlap(a["start_time"], a["end_time"], b["start_time"], b["end_time"]):
                            by_semester.append({
                                "semester": semester,
                                "prerequisite": prereq,
                                "follow_up": b["course_code"],
                                "prereq_crn": a["crn"],
                                "follow_up_crn": b["crn"],
                                "details": f"{prereq} conflicts with {b['course_code']} in {semester}.",
                            })
        return pd.DataFrame(by_semester)
