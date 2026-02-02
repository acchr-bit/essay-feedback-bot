import streamlit as st
import requests
import json

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

# 4. STABLE API CALL (Using v1 stable and Gemini 2.0)
def call_gemini_stable(prompt):
    # Using the v1 stable endpoint instead of v1beta
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    else:
        # If gemini-2.0-flash is also "Not Found", we try one last fallback to gemini-1.5-flash on v1
        fallback_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={API_KEY}"
        fallback_res = requests.post(fallback_url, headers=headers, json=data)
        if fallback_res.status_code == 200:
            return fallback_res.json()['candidates'][0]['content']['parts'][0]['text']
        
        raise Exception(f"Status {response.status_code}: {response.text}")

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
                    feedback = call_gemini_stable(prompt)
                    
                    st.session_state.feedback = feedback
                    st.session_state.submitted = True
                    
                    requests.post(SHEET_URL, json={
                        "type": "FIRST_DRAFT", "group": group, "students": student_list, "feedback": feedback, "essay": essay
                    })
                    st.rerun()
                except Exception as e:
                    st.error("❌ Google Connection Error")
                    st.warning(f"Reason: {e}")
else:
    st.success("Submission successful!")
    st.markdown(st.session_state.feedback)
    if st.button("New Submission"):
        st.session_state.submitted = False
        st.rerun()
