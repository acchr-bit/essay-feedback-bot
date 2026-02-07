import streamlit as st
import requests
import re
import time

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]

# --- TASK CONFIGURATION ---
TASK_DESC = ("This is your last year at school and you are planning your end of year trip "
             "together with your classmates and teachers. Write an email to Liam, your "
             "exchange partner from last year, who has just sent you an email. Tell him "
             "about your plans for the trip: the places you are going to visit, the "
             "activities you are going to do there, and also about your classmates, "
             "friends and family.")

REQUIRED_CONTENT_POINTS = [
    "Plans for the trip",
    "Places you are going to visit",
    "Activities you are going to do",
    "Information about classmates, friends, and family"
]

# 2. THE STERN TEACHER PROMPT (Draft 1)
RUBRIC_INSTRUCTIONS = """
### ROLE: STRICT EXAMINER
You are a meticulous British English Examiner. You grade according to strict mathematical rules. You must follow these 4 RED LINES:
1. WORD COUNT OVERRIDE: Look at the EXACT WORD COUNT provided. If the text is UNDER 65 words, STOP immediately. Do not grade the criteria. Provide the note "Your composition is too short to be marked." and set 'FINAL MARK: 0/10'.
2. LENGTH PENALTY: Look at the EXACT WORD COUNT provided. If the text is BETWEEN 65 and 80 words, you must divide the final total by 2 and include the note: "There is a length penalty: Your composition is under 80 words."
3. NO ANSWERS: NEVER provide the corrected version of a mistake. If you write the correct form, you have failed your mission. You must ONLY quote the error and explain the grammar rule behind it.
4. NEVER mention the student's name in any of your feedbacks.
5. NEVER use the term "B2" or "CEFR" in the feedback.
6. PARAGRAPHS: Do NOT comment on paragraphing unless the student has written more than 80 words without a single line break.

### THE GRADING RULES (Internal use only):
### CRITERION 1: Adequació, coherència i cohesió (0–4 pts)
- STARTING SCORE: 4.0
- DEDUCTION RULES: Comma Splice -0.5, Missing Intro Comma -0.2, Poor Paragraphs -0.5, Wrong Register -0.5, Content Coverage -0.5/point, Connectors penalty -1.0.
### CRITERION 2: Morfosintaxi i ortografia (0–4 pts)
- STARTING SCORE: 4.0
- DEDUCTIONS: Spelling -0.2, Word Order -0.3, Tense -0.3, To Be/To Have -0.5, Agreement -0.5, Articles -0.3, Prepositions -0.2.
### CRITERION 3: Lèxic i Riquesa (0–2 pts)
- Choose 2.0 (Rich), 1.0 (Limited), or 0.0 (Poor).

### FEEDBACK STRUCTURE (PUBLIC):
1. 'Overall Impression: '
2. ###### **Adequació, coherència i cohesió (Score: X/4)**
3. ###### **Morfosintaxi i ortografia (Score: X/4)**
4. ###### **Lèxic (Score: X/2)**
5. ###### **FINAL MARK: X/10**
"""

# --- NEW ADDITION: REVISION SPECIALIST PROMPT ---
# This ensures the final feedback is actually a comparison, not a re-grading.
REVISION_COACH_PROMPT = """
### ROLE: REVISION CHECKER
You are a helpful writing tutor. Your ONLY goal is to check if the student fixed the errors found in the first draft.
1. DO NOT give a new grade or points.
2. DO NOT provide the correct answers.
3. Compare the NEW VERSION against the ORIGINAL FEEDBACK.
4. Use this structure:
   - **✅ Improvements**: What did they fix correctly?
   - **⚠️ Still Needs Work**: Which errors from the first feedback are still there?
   - **🏁 Final Advice**: A brief encouraging closing.
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
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0}
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    return "The teacher is busy. Try again in 10 seconds."

# 5. UI CONFIGURATION (Your Original Styling)
st.set_page_config(page_title="Writing Test", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    [data-testid="stHeaderActionElements"], .stDeployButton, [data-testid="stToolbar"], 
    [data-testid="stSidebarCollapseButton"], #MainMenu, [data-testid="stDecoration"], footer {
        display: none !important;
    }
    header { background-color: rgba(0,0,0,0) !important; }
    .stTextArea textarea { font-size: 18px !important; line-height: 1.6 !important; }
    .stCaption { font-size: 14px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📝 Writing")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Group", [" ","3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1")
    s2 = st.text_input("Student 2")
    s3 = st.text_input("Student 3")
    s4 = st.text_input("Student 4")
    names = [s.strip() for s in [s1, s2, s3, s4] if s.strip()]
    student_list = ", ".join(names)

st.markdown(f"### 📋 Task Description")
st.markdown(f"<div style='font-size: 20px; line-height: 1.5; margin-bottom: 20px;'>{TASK_DESC}</div>", unsafe_allow_html=True)

essay = st.text_area("Write your composition below:", value=st.session_state.essay_content, height=500)
st.session_state.essay_content = essay
word_count = len(essay.split())
st.caption(f"Word count: {word_count}")

# --- 1. FIRST FEEDBACK BUTTON ---
if not st.session_state.fb1:
    if st.button("🔍 Get Feedback", use_container_width=True):
        if not s1 or not essay:
            st.error("Please enter your name and write your composition first.")
        else:
            with st.spinner("Teacher is marking your composition..."):
                formatted_points = "\n".join([f"- {p}" for p in REQUIRED_CONTENT_POINTS])
                full_prompt = f"{RUBRIC_INSTRUCTIONS}\n\nWORD COUNT: {word_count}\nPOINTS: {formatted_points}\nESSAY:\n{essay}"
                fb = call_gemini(full_prompt)
                st.session_state.fb1 = fb
                
                mark_search = re.search(r"FINAL MARK:\s*(\d+,?\d*/10)", fb)
                mark_value = mark_search.group(1) if mark_search else "N/A"
                
                requests.post(SHEET_URL, json={
                    "type": "FIRST", "Group": group, "Students": student_list, "Mark": mark_value,
                    "Draft 1": essay, "FB 1": fb, "Word Count": word_count
                })
                st.rerun()

# --- 2. DISPLAY FIRST FEEDBACK ---
if st.session_state.fb1:
    st.markdown("---")
    st.markdown(f"""<div style="background-color: #e7f3ff; color: #1a4a7a; padding: 20px; border-radius: 12px; border: 1px solid #b3d7ff;">
            <h3>🔍 Read the feedback and improve your composition</h3>
            {st.session_state.fb1}</div>""", unsafe_allow_html=True)

    # --- 3. REVISION BUTTON ---
    if not st.session_state.fb2:
        if st.button("🚀 Submit Final Revision", use_container_width=True):
            with st.spinner("✨ Teacher is reviewing your changes..."):
                # Notice we use the COACH prompt here for better accuracy
                rev_prompt = f"{REVISION_COACH_PROMPT}\n\nORIGINAL FEEDBACK:\n{st.session_state.fb1}\n\nNEW REVISED VERSION:\n{essay}"
                fb2 = call_gemini(rev_prompt)
                st.session_state.fb2 = fb2
                
                requests.post(SHEET_URL, json={
                    "type": "REVISION", "Group": group, "Students": student_list,
                    "Final Essay": essay, "FB 2": fb2, "Word Count": word_count
                })
                st.balloons()
                st.rerun()

# --- 4. FINAL FEEDBACK ---
if st.session_state.fb2:
    st.markdown(f"""<div style="background-color: #d4edda; color: #155724; padding: 20px; border-radius: 12px; border: 1px solid #c3e6cb; margin-top: 20px;">
            <h3>✅ Final Revision Feedback</h3>
            {st.session_state.fb2}</div>""", unsafe_allow_html=True)
