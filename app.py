from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from bellini.data_loader import BelliniDataLoader
from bellini.services import (
    AnalyticsService,
    AuditService,
    BelliniRepository,
    SearchService,
    ScheduleService,
)

DATA_DIR = Path(__file__).resolve().parent / "data"

st.set_page_config(page_title="Bellini College Course Management System", layout="wide")


@st.cache_data
def load_initial_dataframe() -> pd.DataFrame:
    loader = BelliniDataLoader(DATA_DIR)
    return loader.load_all(include_new_classes=True)


def init_state() -> None:
    if "bellini_df" not in st.session_state:
        st.session_state.bellini_df = load_initial_dataframe()


def build_services():
    repo = BelliniRepository(st.session_state.bellini_df)
    return repo, AuditService(), SearchService(), ScheduleService(), AnalyticsService()


def save_repo(repo: BelliniRepository):
    st.session_state.bellini_df = repo.all_data()
    # Save the updated DataFrame back to the Excel file
    data_file_path = DATA_DIR / "Bellini Classes S25.xlsx"  # Update this to the correct file if needed
    data_file_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists
    st.session_state.bellini_df.to_excel(data_file_path, index=False)


def dashboard(df: pd.DataFrame):
    st.header("Bellini College Course Management System")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sections", len(df))
    c2.metric("Unique Courses", df["course_code"].nunique())
    c3.metric("Unique Instructors", df["instructor"].nunique())
    c4.metric("Semesters", ", ".join(sorted(df["semester"].unique())))
    chart_df = df.groupby("semester").size().reset_index(name="sections")
    fig = px.bar(chart_df, x="semester", y="sections", title="Sections by Semester")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df.head(20), use_container_width=True)


def manage_class_data(repo: BelliniRepository):
    st.header("US7 / Mandatory: Manage Class Data")
    st.caption("Add, update, and delete class records.")
    df = repo.all_data().sort_values(["semester", "course_code", "crn"])
    st.dataframe(df[["semester", "crn", "course_code", "course_title", "meeting_days", "meeting_times", "meeting_room", "instructor", "enrollment"]], use_container_width=True)

    with st.expander("Add New Class"):
        with st.form("add_class"):
            cols = st.columns(3)
            class_data = {
                "semester": cols[0].selectbox("Semester", ["S25", "F25", "S26"]),
                "term": cols[1].text_input("Term", "202601"),
                "campus": cols[2].text_input("Campus", "Tampa"),
                "course_level": cols[0].text_input("Course Level", "UG"),
                "course_section": cols[1].text_input("Course Section", "1"),
                "crn": cols[2].text_input("CRN", "99999"),
                "subject": cols[0].text_input("Subject", "CIS"),
                "course_number": cols[1].text_input("Course Number", "4930"),
                "course_title": cols[2].text_input("Course Title", "Demo Added Course"),
                "enrollment": cols[0].number_input("Enrollment", min_value=0, value=15),
                "meeting_days": cols[1].text_input("Meeting Days", "MW"),
                "meeting_times": cols[2].text_input("Meeting Times", "03:30 PM - 04:45 PM"),
                "meeting_room": cols[0].text_input("Meeting Room", "CHE 111"),
                "instructor": cols[1].text_input("Instructor", "Demo, Instructor"),
                "instructor_email": cols[2].text_input("Instructor Email", "demo@usf.edu"),
                "grad_tas": "",
                "ugtas": "",
                "start_time": None,
                "end_time": None,
            }
            class_data["course_code"] = f"{class_data['subject']}{class_data['course_number']}"
            submitted = st.form_submit_button("Add Class")
            if submitted:
                from bellini.utils import parse_time_range
                class_data["start_time"], class_data["end_time"] = parse_time_range(class_data["meeting_times"])
                repo.add_class(class_data)
                save_repo(repo)  # Ensure changes are saved to session state
                st.success(f"Added class CRN {class_data['crn']}")

    with st.expander("Update Existing Class"):
        crn = st.selectbox("Select CRN to update", options=df["crn"].tolist()) if not df.empty else None
        if crn:
            current = df[df["crn"] == crn].iloc[0]
            with st.form("update_class"):
                new_room = st.text_input("Meeting Room", current["meeting_room"])
                new_times = st.text_input("Meeting Times", current["meeting_times"])
                new_enrollment = st.number_input("Enrollment", min_value=0, value=int(current["enrollment"]))
                do_update = st.form_submit_button("Update Class")
                if do_update:
                    from bellini.utils import parse_time_range
                    start, end = parse_time_range(new_times)
                    repo.update_class(crn, {
                        "meeting_room": new_room,
                        "meeting_times": new_times,
                        "enrollment": int(new_enrollment),
                        "start_time": start,
                        "end_time": end,
                    })
                    save_repo(repo)  # Ensure changes are saved to session state
                    st.success(f"Updated CRN {crn}")

    with st.expander("Delete Class"):
        crn_delete = st.selectbox("Select CRN to delete", options=df["crn"].tolist(), key="delete_crn") if not df.empty else None
        if crn_delete and st.button("Delete Selected Class"):
            repo.delete_class(crn_delete)
            save_repo(repo)  # Ensure changes are saved to session state
            st.warning(f"Deleted CRN {crn_delete}")


def audit_schedule(df: pd.DataFrame, audit_service: AuditService):
    st.header("US8 / Mandatory: Audit Schedule Integrity")
    semester = st.multiselect("Select semester(s) to audit", options=sorted(df["semester"].unique()), default=sorted(df["semester"].unique()))
    if st.button("Run Integrity Audit"):
        # Ensure the filtered result is a DataFrame
        filtered_df = df[df["semester"].isin(semester)]
        if not isinstance(filtered_df, pd.DataFrame):
            filtered_df = pd.DataFrame(filtered_df)
        result = audit_service.audit_integrity(filtered_df)
        if result.empty:
            st.success("System Validated: no integrity issues found.")
        else:
            st.error(f"Found {len(result)} issue(s).")
            st.dataframe(result, use_container_width=True)


def visualize_student_schedule(df: pd.DataFrame, schedule_service: ScheduleService):
    st.header("US1: Visualize Student Schedule")
    semester = st.selectbox("Semester", options=sorted(df["semester"].unique()), key="schedule_sem")
    available = df[df["semester"] == semester][["crn", "course_code", "course_title", "meeting_days", "meeting_times"]].sort_values(["course_code", "crn"])
    st.dataframe(available, use_container_width=True, height=250)
    crn_input = st.text_input("Enter CRNs separated by commas", "14915,14922,14891")
    if st.button("Build Schedule"):
        schedule_df, conflicts = schedule_service.build_schedule(df, semester, [x.strip() for x in crn_input.split(",")])
        grid = schedule_service.weekly_grid(schedule_df)
        st.subheader("Weekly Calendar Grid")
        st.dataframe(grid, use_container_width=True)
        if conflicts:
            st.warning("Conflicts / errors detected")
            st.dataframe(pd.DataFrame(conflicts), use_container_width=True)
        else:
            st.success("No conflicts detected.")


def analyze_course_frequency(df: pd.DataFrame, analytics_service: AnalyticsService):
    st.header("US2: Analyze Course Frequency")
    semester = st.selectbox("Semester", options=sorted(df["semester"].unique()), key="frequency_sem")
    # Ensure the filtered result is a DataFrame
    filtered_df = df[df["semester"].isin(["S25", "F25", "S26"])]
    if not isinstance(filtered_df, pd.DataFrame):
        filtered_df = pd.DataFrame(filtered_df)
    freq = analytics_service.course_frequency(filtered_df).head(50)
    st.dataframe(freq, use_container_width=True)
    bottlenecks = freq[freq["bottleneck_flag"]]
    if not bottlenecks.empty:
        fig = px.bar(bottlenecks.head(15), x="course_code", y=["S25", "F25", "S26"], barmode="group", title="Potential Bottleneck Courses")
        st.plotly_chart(fig, use_container_width=True)


def search_courses(df: pd.DataFrame, search_service: SearchService):
    st.header("US3: Search Courses by Keyword")
    keywords = st.text_input("Keyword(s)", "Python, AI, Database")
    if st.button("Search"):
        results = search_service.keyword_search(df, keywords)
        st.dataframe(results[["semester", "crn", "course_code", "course_title", "meeting_days", "meeting_times", "instructor"]], use_container_width=True)
        st.info(f"Found {len(results)} matching section(s).")


def low_capacity_rooms(df: pd.DataFrame, audit_service: AuditService):
    st.header("US4: Flag Low-Capacity Rooms")
    threshold = st.slider("Utilization threshold", 0.1, 0.9, 0.5, 0.05)
    result = audit_service.low_capacity_rooms(df, threshold)
    st.dataframe(result, use_container_width=True)
    st.info("Rows shown are classes using less than the selected percentage of room capacity.")


def prerequisite_timing(df: pd.DataFrame, analytics_service: AnalyticsService):
    st.header("US5: Check Prerequisite Timing")
    st.caption("Uses a demo prerequisite map based on course progression pairs.")
    result = analytics_service.prerequisite_conflicts(df)
    if result.empty:
        st.success("No prerequisite timing conflicts found.")
    else:
        st.dataframe(result, use_container_width=True)


def course_rotation(df: pd.DataFrame, analytics_service: AnalyticsService):
    st.header("US6: Analyze Course Rotation")
    # Ensure the filtered result is a DataFrame
    filtered_df = df[df["semester"].isin(["S25", "F25", "S26"])]
    if not isinstance(filtered_df, pd.DataFrame):
        filtered_df = pd.DataFrame(filtered_df)
    result = analytics_service.seasonal_courses(filtered_df)
    st.dataframe(result, use_container_width=True)


def main():
    init_state()
    repo, audit_service, search_service, schedule_service, analytics_service = build_services()
    df = repo.all_data()
    st.sidebar.title("Bellini Navigation")
    page = st.sidebar.radio(
        "Choose a feature",
        [
            "Dashboard",
            "Manage Class Data",
            "Audit Schedule Integrity",
            "Visualize Student Schedule",
            "Analyze Course Frequency",
            "Search Courses by Keyword",
            "Flag Low-Capacity Rooms",
            "Check Prerequisite Timing",
            "Analyze Course Rotation",
        ],
    )

    if page == "Dashboard":
        dashboard(df)
    elif page == "Manage Class Data":
        manage_class_data(repo)
    elif page == "Audit Schedule Integrity":
        audit_schedule(df, audit_service)
    elif page == "Visualize Student Schedule":
        visualize_student_schedule(df, schedule_service)
    elif page == "Analyze Course Frequency":
        analyze_course_frequency(df, analytics_service)
    elif page == "Search Courses by Keyword":
        search_courses(df, search_service)
    elif page == "Flag Low-Capacity Rooms":
        low_capacity_rooms(df, audit_service)
    elif page == "Check Prerequisite Timing":
        prerequisite_timing(df, analytics_service)
    elif page == "Analyze Course Rotation":
        course_rotation(df, analytics_service)


if __name__ == "__main__":
    main()
