# Bellini College Course Management System

A Streamlit-based project implementation for COP 4020 Project 2 using the Bellini S25, F25, and S26 Excel datasets.

## Implemented user stories

### Mandatory
1. Manage Class Data
2. Audit Schedule Integrity

### Team stories
3. Visualize Student Schedule
4. Analyze Course Frequency
5. Search Courses by Keyword
6. Flag Low-Capacity Rooms
7. Check Prerequisite Timing
8. Analyze Course Rotation

## Tech stack
- Python
- pandas
- openpyxl
- Streamlit
- Plotly

## Project structure
- `app.py` - main Streamlit application
- `bellini/data_loader.py` - loads and normalizes semester Excel files
- `bellini/services.py` - feature logic for all use cases
- `bellini/models.py` - data classes
- `data/` - Bellini Excel files

## How to run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Demo notes
Use the built-in **Demo Guide** page in the sidebar for sunny-day and rainy-day recording ideas for each user story.

## Suggested demo flow
1. Dashboard
2. Manage Class Data
3. Audit Schedule Integrity
4. Visualize Student Schedule
5. Analyze Course Frequency
6. Search Courses by Keyword
7. Flag Low-Capacity Rooms
8. Check Prerequisite Timing
9. Analyze Course Rotation
