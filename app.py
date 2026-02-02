import streamlit as st
import requests
import time

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]

# 2. SESSION STATE
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'feedback' not in st.session_state:
    st.session_state.feedback = ""

# 3. UI
st.set_page_config(page_title="Writing Portal", layout="centered")
st.title("📝 Student Writing Portal")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Group", ["3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1 Name and Surname")
    s2 = st.text_input("Student 2 Name and Surname (Optional)")
    s3 = st.text_input("Student 3 Name and Surname (Optional)")
    s4 = st.text_input("Student 4 Name and Surname (Optional)")
    names = [s.strip() for s in [s1, s2, s3, s4] if s.strip()]
    student_list = ", ".join(names)

# 4. API CALL
def call_gemini(prompt):
    # In 2026, 'gemini-2.5-flash' is the standard workhorse model.
    # 'gemini-2.0-flash' is the fallback for basic free/pay-as-you-go tiers.
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    # TRY 1: Gemini 2.5 Flash (The current 2026 recommended model)
    url_25 = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    
    try:
        response = requests.post(url_25, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        
        # TRY 2: Gemini 2.0 Flash (If 2.5 isn't active for your tier yet)
        url_20 = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={API_KEY}"
        response = requests.post(url_20, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
            
        raise Exception(f"Error {response.status_code}: {response.text}")
        
    except Exception as e:
        raise Exception(f"AI Connection Failed: {e}")

# 5. LOGIC
st.info("Task: Write an email to Liam (80-100 words) about your trip plans.")

if not st.session_state.submitted:
    essay = st.text_area("Type your essay here...", height=350)
    
    if st.button("Submit for Grade"):
        if not s1 or not essay:
            st.error("Missing name or essay.")
        else:
            with st.spinner("AI Teacher is analyzing..."):
                try:
                    prompt = f"Grade this B2 English essay. Provide feedback and end with 'FINAL MARK: X/10'.\n\nEssay: {essay}"
                    feedback = call_gemini(prompt)
                    
                    st.session_state.feedback = feedback
                    st.session_state.submitted = True
                    
                    # Log to Sheets
                    requests.post(SHEET_URL, json={
                        "type": "FIRST_DRAFT", "group": group, "students": student_list, "feedback": feedback, "essay": essay
                    })
                    st.rerun()
                except Exception as e:
                    st.error(f"Status: {e}")
else:
    st.success("Submission successful!")
    st.markdown(st.session_state.feedback)
    if st.button("New Submission"):
        st.session_state.submitted = False
        st.rerun()
