import streamlit as st
import requests

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]

# 2. SESSION STATE
if 'essay_content' not in st.session_state:
    st.session_state.essay_content = ""
if 'fb1' not in st.session_state:
    st.session_state.fb1 = ""
if 'fb2' not in st.session_state:
    st.session_state.fb2 = ""
if 'submitted_first' not in st.session_state:
    st.session_state.submitted_first = False

def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    raise Exception(f"AI Error: {response.status_code}")

# 3. UI
st.set_page_config(page_title="Writing Portal", layout="centered")
st.title("📝 Writing & Revision Portal")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Group", ["3A", "3C", "4A", "4B", "4C"])
    
    # Restoring the 4 input fields
    s1 = st.text_input("Student 1 Name and Surname")
    s2 = st.text_input("Student 2 Name and Surname (Optional)")
    s3 = st.text_input("Student 3 Name and Surname (Optional)")
    s4 = st.text_input("Student 4 Name and Surname (Optional)")
    
    # Logic to combine them into one string for the spreadsheet
    names = [s.strip() for s in [s1, s2, s3, s4] if s.strip()]
    student_list = ", ".join(names)

task_name = "Email to Liam (Trip Plans)"
st.info(f"**Task:** {task_name}")

# THE TEXT AREA
essay = st.text_area("Write and edit your essay here:", value=st.session_state.essay_content, height=350)
st.session_state.essay_content = essay

col1, col2 = st.columns(2)

# STEP 1: FIRST DRAFT
with col1:
    if st.button("🔍 Get Feedback (Draft 1)"):
        if not s1 or not essay:
            st.error("Enter names and essay first.")
        else:
            with st.spinner("Analyzing Draft 1..."):
                try:
                    fb = call_gemini(f"Grade this B2 essay. Feedback first, then end with 'FINAL MARK: X/10'.\n\n{essay}")
                    st.session_state.fb1 = fb
                    mark = fb.split("FINAL MARK:")[1].split("\n")[0].strip() if "FINAL MARK:" in fb else "N/A"
                    
                    requests.post(SHEET_URL, json={
                        "type": "FIRST", "Group": group, "Students": student_list, "Task": task_name,
                        "Mark": mark, "FB1": fb, "Draft1": essay
                    })
                    st.session_state.submitted_first = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# DISPLAY AREA
if st.session_state.fb1:
    st.markdown("---")
    st.subheader("💡 First Feedback")
    st.info(st.session_state.fb1)

    # STEP 2: FINAL SUBMISSION (Only shows after Draft 1 is checked)
    with col2:
        if st.button("🚀 Submit FINAL Version"):
            with st.spinner("Saving Final Essay..."):
                try:
                    fb2 = call_gemini(f"Compare this final version to the first. Did they improve? Give a final short comment.\n\n{essay}")
                    st.session_state.fb2 = fb2
                    
                    requests.post(SHEET_URL, json={
                        "type": "REVISION", "Group": group, "Students": student_list, "FinalEssay": essay, "FB2": fb2
                    })
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")

if st.session_state.fb2:
    st.subheader("✅ Final Result")
    st.success(st.session_state.fb2)
