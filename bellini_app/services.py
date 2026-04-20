from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from .data import DISPLAY_COLUMNS, days_overlap, time_overlap

PREREQUISITE_MAP = {
    "COP 3515": ["COP 4530", "COP 4610"],
    "CIS 3360": ["CIS 4930"],
    "CDA 3103": ["CDA 4101"],
    "CIS 3213": ["COP 4710"],
}


@dataclass
class BelliniService:
    df: pd.DataFrame

    def all_display(self) -> pd.DataFrame:
        cols = [c for c in DISPLAY_COLUMNS if c in self.df.columns]
        return self.df[cols].sort_values(["semester", "subject", "course_number", "course_section"])

    def search_courses(self, keyword: str) -> pd.DataFrame:
        keyword = keyword.strip()
        if not keyword:
            return self.df.iloc[0:0].copy()
        mask = (
            self.df["course_title"].str.contains(keyword, case=False, na=False)
            | self.df["course_key"].str.contains(keyword, case=False, na=False)
            | self.df["subject"].str.contains(keyword, case=False, na=False)
        )
        return self.df.loc[mask, self._display_columns()]

    def build_schedule(self, semester: str, crns: List[int]) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
        subset = self.df[(self.df["semester"] == semester) & (self.df["crn"].isin(crns))].copy()
        found = set(subset["crn"].dropna().astype(int).tolist())
        missing = [str(crn) for crn in crns if int(crn) not in found]
        conflicts = self._find_pairwise_conflicts(subset)
        return subset[self._display_columns()], conflicts, missing

    def audit_integrity(self, semester: str | None = None) -> Dict[str, pd.DataFrame]:
        subset = self.df if not semester or semester == "ALL" else self.df[self.df["semester"] == semester]
        duplicate_crns = subset[subset["crn"].duplicated(keep=False)].sort_values("crn")
        incomplete = subset[
            subset["crn"].isna() | subset["meeting_room"].isin(["", "TBA"]) | subset["meeting_times"].isin(["", "TBA"])
        ]
        room_conflicts = self._conflict_records(subset, key="meeting_room")
        instructor_conflicts = self._conflict_records(subset, key="instructor")
        return {
            "duplicate_crns": duplicate_crns[self._display_columns()],
            "room_conflicts": room_conflicts,
            "instructor_conflicts": instructor_conflicts,
            "incomplete_rows": incomplete[self._display_columns()],
        }

    def analyze_course_frequency(self) -> pd.DataFrame:
        grouped = (
            self.df.groupby(["course_key", "semester"])["crn"]
            .nunique()
            .unstack(fill_value=0)
            .reset_index()
        )
        for sem in ["S25", "F25", "S26"]:
            if sem not in grouped.columns:
                grouped[sem] = 0
        grouped["max_sections"] = grouped[["S25", "F25", "S26"]].max(axis=1)
        grouped["min_sections"] = grouped[["S25", "F25", "S26"]].min(axis=1)
        grouped["bottleneck_flag"] = grouped["max_sections"] - grouped["min_sections"] >= 1
        return grouped.sort_values(["bottleneck_flag", "course_key"], ascending=[False, True])

    def flag_low_capacity_rooms(self, threshold: float = 0.5) -> pd.DataFrame:
        subset = self.df.copy()
        subset["utilization"] = subset["enrollment"] / subset["room_capacity"].replace(0, pd.NA)
        subset["utilization"] = subset["utilization"].fillna(0)
        result = subset[(subset["room_capacity"] > 0) & (subset["utilization"] < threshold)]
        cols = self._display_columns() + ["utilization"]
        return result[cols].sort_values("utilization")

    def detect_prerequisite_conflicts(self, prerequisite_map: Dict[str, List[str]] | None = None) -> pd.DataFrame:
        prerequisite_map = prerequisite_map or PREREQUISITE_MAP
        rows = []
        for prereq, followers in prerequisite_map.items():
            prereq_rows = self.df[self.df["course_key"] == prereq]
            follow_rows = self.df[self.df["course_key"].isin(followers)]
            for _, a in prereq_rows.iterrows():
                for _, b in follow_rows[follow_rows["semester"] == a["semester"]].iterrows():
                    if days_overlap(a["meeting_days"], b["meeting_days"]) and time_overlap(a["start_minutes"], a["end_minutes"], b["start_minutes"], b["end_minutes"]):
                        rows.append({
                            "semester": a["semester"],
                            "prerequisite": a["course_key"],
                            "follower": b["course_key"],
                            "prereq_crn": int(a["crn"]),
                            "follower_crn": int(b["crn"]),
                            "days": a["meeting_days"],
                            "time": a["meeting_times"],
                        })
        return pd.DataFrame(rows)

    def analyze_course_rotation(self) -> pd.DataFrame:
        grouped = (
            self.df.groupby(["course_key", "semester"])["crn"]
            .nunique()
            .unstack(fill_value=0)
            .reset_index()
        )
        for sem in ["S25", "F25", "S26"]:
            if sem not in grouped.columns:
                grouped[sem] = 0
        conditions = [
            (grouped["S25"] > 0) & (grouped["F25"] == 0) & (grouped["S26"] > 0),
            (grouped["S25"] == 0) & (grouped["F25"] > 0) & (grouped["S26"] == 0),
            (grouped["S25"] > 0) & (grouped["F25"] > 0) & (grouped["S26"] > 0),
        ]
        choices = ["Spring-Only", "Fall-Only", "Every Semester"]
        import numpy as np
        grouped["rotation_type"] = pd.Series(pd.Categorical(np.select(conditions, choices, default="Mixed/Irregular")))
        grouped["graduation_risk"] = grouped["rotation_type"].map({
            "Spring-Only": "High",
            "Fall-Only": "High",
            "Every Semester": "Low",
            "Mixed/Irregular": "Medium",
        })
        return grouped.sort_values(["graduation_risk", "course_key"])

    def add_class(self, record: Dict) -> None:
        self.df.loc[len(self.df)] = record

    def update_class(self, crn: int, updates: Dict) -> bool:
        idx = self.df.index[self.df["crn"] == crn]
        if len(idx) == 0:
            return False
        for k, v in updates.items():
            self.df.loc[idx, k] = v
        return True

    def delete_class(self, crn: int) -> bool:
        before = len(self.df)
        self.df = self.df[self.df["crn"] != crn].copy()
        return len(self.df) < before

    def export_excel(self, path: str) -> None:
        self.df.to_excel(path, index=False)

    def _display_columns(self) -> List[str]:
        return [c for c in DISPLAY_COLUMNS if c in self.df.columns]

    def _find_pairwise_conflicts(self, subset: pd.DataFrame) -> pd.DataFrame:
        rows = []
        records = subset.to_dict("records")
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                a, b = records[i], records[j]
                if days_overlap(a["meeting_days"], b["meeting_days"]) and time_overlap(a["start_minutes"], a["end_minutes"], b["start_minutes"], b["end_minutes"]):
                    rows.append({
                        "crn_a": int(a["crn"]),
                        "course_a": a["course_key"],
                        "crn_b": int(b["crn"]),
                        "course_b": b["course_key"],
                        "days": a["meeting_days"],
                        "time_a": a["meeting_times"],
                        "time_b": b["meeting_times"],
                    })
        return pd.DataFrame(rows)

    def _conflict_records(self, subset: pd.DataFrame, key: str) -> pd.DataFrame:
        rows = []
        records = subset[subset["has_meeting"]].to_dict("records")
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                a, b = records[i], records[j]
                if a[key] == b[key] and days_overlap(a["meeting_days"], b["meeting_days"]) and time_overlap(a["start_minutes"], a["end_minutes"], b["start_minutes"], b["end_minutes"]):
                    rows.append({
                        "semester": a["semester"],
                        key: a[key],
                        "crn_a": int(a["crn"]),
                        "course_a": a["course_key"],
                        "crn_b": int(b["crn"]),
                        "course_b": b["course_key"],
                        "days": a["meeting_days"],
                        "time_a": a["meeting_times"],
                        "time_b": b["meeting_times"],
                    })
        return pd.DataFrame(rows)
