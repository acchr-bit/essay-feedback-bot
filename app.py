import streamlit as st
import requests
import re
import time

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]

# 2. THE PEDAGOGICAL RUBRIC PROMPT
RUBRIC_INSTRUCTIONS = """
You are a supportive but strict British English teacher. Your goal is to grade a B2 essay using a specific rubric, but provide the feedback in a natural, encouraging way. Never mention B2 level in your feedback.

### THE GRADING RULES (Internal use only):
- CRITERION 1 (0–4 pts): Start at 4,0. Deduct for Genre (-1), Register (-0,5), Paragraphs (-0,5), missing info (-0,5), and Connectors (fewer than 5 total or 3 different = -1). Punctuation: 1-2 mistakes (-0,3), 3-4 (-0,6), 5+ (-1).
- CRITERION 2 (0–4 pts): Start at 4,0. Deduct for Tense (-0,3 each), 'to be/have' (-0,4), Subject-verb agreement (-0,4), Spelling (-0,2 each), Prepositions (-0,2 each), Collocations (-0,1), small 'i' (-0,5).
- CRITERION 3 (0–2 pts): 2 (Rich), 1 (Limited/Some errors), 0 (Poor).
- TOTAL: Sum C1+C2+C3. If under 80 words, divide total by 2.

### HOW TO WRITE THE FEEDBACK:
1. Start with a warm greeting and an 'Overall Impression'. Don't mention the students names.
2. Use exactly these sections: 'Morfosintaxi i ortografia', 'Grammar & Spelling', and 'Lèxic'.
3. DO NOT mention specific point deductions (e.g., do not write '-1,0 point').
4. DO NOT give the corrected version of the sentences. Instead, explain the rule or the nature of the error so the student can fix it themselves.
5. Provide a 'Recommendations' section.
6. AT THE VERY END, write 'FINAL MARK: X/10' using a comma for decimals.
"""

# 3. SESSION STATE
if 'essay_content' not in st.session_state:
    st.session_state.essay_content = ""
if 'fb1' not in st.session_state:
    st.session_state.fb1 = ""
if 'fb2' not in st.session_state:
    st.session_state.fb2 = ""

# 4. AI CONNECTION
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    for attempt in range(3):
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        elif response.status_code == 429:
            time.sleep(5)
            continue
    return "The teacher is busy right now. Please try again in a moment."

# 5. UI
st.set_page_config(page_title="Writing", layout="centered")
st.title("📝 Writing")

with st.sidebar:
    st.header("Student Information")
    group = st.selectbox("Group", ["3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1 (Name and Surname)")
    s2 = st.text_input("Student 2 (Name and Surname) (Optional)")
    s3 = st.text_input("Student 3 (Name and Surname) (Optional)")
    s4 = st.text_input("Student 4 (Name and Surname) (Optional)")
    names = [s.strip() for s in [s1, s2, s3, s4] if s.strip()]
    student_list = ", ".join(names)

# Long task description used for both header and prompt
task_name = "This is your last year at school and you are planning your end of year trip together with your classmates and teachers. Write an email to Liam, your exchange partner from last year, who has just sent you an email. Tell him about your plans for the trip: the places you are going to visit, the activities you are going to do there, and also about your classmates, friends and family."

essay = st.text_area(task_name, value=st.session_state.essay_content, height=400)
st.session_state.essay_content = essay

word_count = len(essay.split())
st.caption(f"Word count: {word_count}")

col1, col2 = st.columns(2)

# STEP 1: DRAFT 1
if col1.button("🔍 Get Feedback"):
    if not s1 or not essay:
        st.error("Please enter your name and essay.")
    else:
        with st.spinner("Teacher is reading your work..."):
            full_prompt = f"{RUBRIC_INSTRUCTIONS}\n\nTASK: {task_name}\n\nESSAY:\n{essay}"
            fb = call_gemini(full_prompt)
            
            # Updated Regex to find "FINAL MARK: 7,5/10"
            mark_search = re.search(r"FINAL MARK:\s*(\d+,?\d*/10)", fb)
            mark_value = mark_search.group(1) if mark_search else "N/A"
            
            st.session_state.fb1 = fb
            
            # Posting with Word Count
            requests.post(SHEET_URL, json={
                "type": "FIRST", 
                "Group": group, 
                "Students": student_list, 
                "Task": "End of Year Trip Email", 
                "Mark": mark_value, 
                "FB 1": fb, 
                "Draft 1": essay, 
                "Word Count": word_count
            })
            st.rerun()

# DISPLAY FEEDBACK
if st.session_state.fb1:
    st.markdown("---")
    st.info(st.session_state.fb1)

    if col2.button("🚀 Submit Final Revision"):
        with st.spinner("Checking your improvements..."):
            rev_prompt = (
                f"The student revised their work based on this feedback: {st.session_state.fb1}\n\n"
                f"Compare the new version to the old one. Praise their specific improvements. "
                f"Do not give a new grade.\n\nNEW VERSION: {essay}"
            )
            fb2 = call_gemini(rev_prompt)
            st.session_state.fb2 = fb2
            
            requests.post(SHEET_URL, json={
                "type": "REVISION", 
                "Group": group, 
                "Students": student_list,
                "Final Essay": essay, 
                "FB 2": fb2
            })
            st.balloons()

if st.session_state.fb2:
    st.success(st.session_state.fb2)
