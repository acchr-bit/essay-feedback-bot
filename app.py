import streamlit as st
import requests
import re
import time

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]

# 2. THE MASTER RUBRIC PROMPT (Updated for commas)
RUBRIC_INSTRUCTIONS = """
You are a strict British English Examiner. Grade the following B2 composition using these exact rules:
IMPORTANT: Use a COMMA for decimals (e.g., 2,7 instead of 2.7) as is standard in Spain.

CRITERION 1: Adequació, coherència i cohesió (0–4 pts)
- Start at 4,0. 
- Deductions: Wrong Genre (-1,0), Wrong Register (-0,5), Not organized in clear paragraphs (-1,0), Fewer than 3 paragraphs (-1,0), Missing required info (-0,5 per piece), Fewer than 5 total connectors (-1,0), Fewer than 3 different connectors (-1,0).
- Punctuation Deductions: 1-2 mistakes (-0,5), 3-4 mistakes (-1,0), 5+ mistakes (-1,5).
- Rule: Round to 1 decimal using a comma.

CRITERION 2: Morfosintaxi i ortografia (0–4 pts)
- Start at 4,0.
- Penalties: Wrong tense (-0,4), Wrong 'to be' (-0,4), Wrong 'to have' (-0,4), Subject-verb agreement (-0,4), Spelling (-0,3), Preposition (-0,3), Collocation/Phrasal Verb (-0,1), Small 'i' instead of 'I' (-0,5), No complex sentences (-0,5).
- Rule: Round to 1 decimal using a comma. 
- Feedback: List mistakes with explanations. DO NOT provide corrections.

CRITERION 3: Lèxic (0–2 pts)
- Allowed scores: 0, 1, or 2 (No decimals).

FINAL TOTAL (0-10):
- Sum C1 + C2 + C3.
- WORD COUNT RULE: If the text is fewer than 80 words, divide the TOTAL grade by 2.
- Report the final mark as: 'FINAL MARK: X/10' (e.g., 7,5/10).
"""

# 3. SESSION STATE
if 'essay_content' not in st.session_state:
    st.session_state.essay_content = ""
if 'fb1' not in st.session_state:
    st.session_state.fb1 = ""
if 'fb2' not in st.session_state:
    st.session_state.fb2 = ""
if 'submitted_first' not in st.session_state:
    st.session_state.submitted_first = False

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
    return "AI Error: The system is busy. Please try again in 1 minute."

# 5. UI
st.set_page_config(page_title="B2 Exam Portal", layout="centered")
st.title("📝 B2 English Writing Examiner")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Group", ["3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1")
    s2 = st.text_input("Student 2 (Opt)")
    s3 = st.text_input("Student 3 (Opt)")
    s4 = st.text_input("Student 4 (Opt)")
    names = [s.strip() for s in [s1, s2, s3, s4] if s.strip()]
    student_list = ", ".join(names)

task_name = "Email to Liam (Trip Plans)"
essay = st.text_area("Write your essay here:", value=st.session_state.essay_content, height=400)
st.session_state.essay_content = essay

# Calculate word count for display
word_count = len(essay.split())
st.caption(f"Word count: {word_count}")

col1, col2 = st.columns(2)

# STEP 1: DRAFT 1
with col1:
    if st.button("🔍 Grade Draft 1"):
        if not s1 or not essay:
            st.error("Missing name or essay.")
        else:
            with st.spinner("Calculating grade..."):
                full_prompt = f"{RUBRIC_INSTRUCTIONS}\n\nTASK: {task_name}\n\nSTUDENT ESSAY:\n{essay}"
                fb = call_gemini(full_prompt)
                
                # Regex Updated for Commas: Searches for 0,0/10 to 10,0/10
                mark_search = re.search(r"FINAL MARK:\s*(\d+,?\d*/10)", fb)
                mark_value = mark_search.group(1) if mark_search else "N/A"
                
                st.session_state.fb1 = fb
                st.session_state.submitted_first = True
                
                # Send to Google Sheets
                requests.post(SHEET_URL, json={
                    "type": "FIRST", "Group": group, "Students": student_list, "Task": task_name,
                    "Mark": mark_value, "FB 1": fb, "Draft 1": essay
                })
                st.rerun()

# STEP 2: REVISION
if st.session_state.fb1:
    st.markdown("---")
    st.subheader("📊 Rubric Assessment & Feedback")
    st.info(st.session_state.fb1)

    with col2:
        if st.button("🚀 Submit FINAL Revision"):
            with st.spinner("Checking improvements..."):
                rev_prompt = (
                    f"The student revised based on this: {st.session_state.fb1}\n\n"
                    f"Check if they addressed the issues. Confirm progress. NO NEW GRADE.\n\n"
                    f"REVISED ESSAY: {essay}"
                )
                fb2 = call_gemini(rev_prompt)
                st.session_state.fb2 = fb2
                
                requests.post(SHEET_URL, json={
                    "type": "REVISION", "Group": group, "Students": student_list,
                    "Final Essay": essay, "FB 2": fb2
                })
                st.balloons()

if st.session_state.fb2:
    st.subheader("✅ Final Teacher Comments")
    st.success(st.session_state.fb2)
