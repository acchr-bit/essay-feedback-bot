import streamlit as st
import requests
import re
import time

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]

TASK_TITLE = "End of Year Trip Email"
REQUIRED_CONTENT_POINTS = [
    "Plans for the trip",
    "Places you are going to visit",
    "Activities you are going to do",
    "Information about classmates, friends, and family"
]

RUBRIC_INSTRUCTIONS = """
You are a British English Examiner. You must follow these 4 RED LINES:
1. NEVER mention the student's name in any of your feedbacks.
2. NEVER use the term "B2" or "CEFR" in the feedback.
3. NEVER provide the corrected version of a mistake.
4. ONLY comment on missing paragraphs if the text is one single block.

Follow the scoring rubric provided (C1/4, C2/4, C3/2). 
Include 'FINAL MARK: X/10' at the very end.
"""

# 3. SESSION STATE
if 'essay_content' not in st.session_state:
    st.session_state.essay_content = ""
if 'fb1' not in st.session_state:
    st.session_state.fb1 = ""
if 'fb2' not in st.session_state:
    st.session_state.fb2 = ""

# 4. AI CONNECTION (With improved retry logic for classroom use)
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    for attempt in range(4): # 4 attempts instead of 3
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            elif response.status_code == 429:
                time.sleep(2 * (attempt + 1)) # Wait longer each time
                continue
        except:
            time.sleep(2)
    return "The teacher is temporarily busy. Please wait 10 seconds and click the button again."

# 5. UI & LOCKDOWN CSS
st.set_page_config(page_title="Writing Test", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Hide top icons and menus */
    [data-testid="stHeaderActionElements"], .stDeployButton, [data-testid="stToolbar"], #MainMenu {
        display: none !important;
    }
    /* Lock the sidebar open */
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    /* Hide footer and decoration */
    [data-testid="stDecoration"], footer {
        display: none !important;
    }
    /* Clean header */
    header { background-color: rgba(0,0,0,0) !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📝 Writing Test")

# 6. SIDEBAR
with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Group", [" ","3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1 - Name and Surname")
    s2 = st.text_input("Student 2 - Name and Surname")
    s3 = st.text_input("Student 3 - Name and Surname")
    s4 = st.text_input("Student 4 - Name and Surname")
    names = [s.strip() for s in [s1, s2, s3, s4] if s.strip()]
    student_list = ", ".join(names)

# 7. MAIN AREA
task_desc = "Write an email to Liam about your end of year trip: places, activities, and your classmates/family."
essay = st.text_area(task_desc, value=st.session_state.essay_content, height=400)
st.session_state.essay_content = essay

word_count = len(essay.split())
st.caption(f"Word count: {word_count}")

col1, col2 = st.columns(2)

if col1.button("🔍 Get Feedback"):
    if not s1 or not essay:
        st.error("Enter your name and essay.")
    else:
        with st.spinner("Teacher is marking..."):
            formatted_points = "\n".join([f"- {p}" for p in REQUIRED_CONTENT_POINTS])
            full_prompt = f"{RUBRIC_INSTRUCTIONS}\n\nPOINTS:\n{formatted_points}\n\nESSAY:\n{essay}"
            fb = call_gemini(full_prompt)
            
            mark_search = re.search(r"FINAL MARK:\s*(\d+,?\d*/10)", fb)
            mark_value = mark_search.group(1) if mark_search else "N/A"
            st.session_state.fb1 = fb
            
            requests.post(SHEET_URL, json={
                "type": "FIRST", "Group": group, "Students": student_list, 
                "Task": TASK_TITLE, "Mark": mark_value, "FB 1": fb, 
                "Draft 1": essay, "Word Count": word_count
            })
            st.rerun()

if st.session_state.fb1:
    st.markdown("---")
    st.info(st.session_state.fb1)
    if col2.button("🚀 Submit Final Revision"):
        with st.spinner("Checking revision..."):
            rev_prompt = f"ORIGINAL FB:\n{st.session_state.fb1}\n\nREVISED ESSAY:\n{essay}\n\nCheck if mistakes were fixed."
            fb2 = call_gemini(rev_prompt)
            st.session_state.fb2 = fb2
            requests.post(SHEET_URL, json={
                "type": "REVISION", "Group": group, "Students": student_list,
                "Final Essay": essay, "FB 2": fb2
            })
            st.balloons()

if st.session_state.fb2:
    st.success(st.session_state.fb2)
