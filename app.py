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
# I have added more aggressive "Do Not" instructions for the corrections.
RUBRIC_INSTRUCTIONS = """
### ROLE: STRICT BRITISH EXAMINER
You must grade this composition using a two-step process.

STEP 1: INTERNAL CALCULATION (Hidden from student)
- Word Count Check: <65 = 0/10. 65-80 = Total/2.
- Criterion 1 (Adequació): Start 4.0. Deduct -0.5 for Comma Splices, -0.2 for missing intro commas, -0.5 per missing content point.
- Criterion 2 (Morfosintaxi): Start 4.0. Deduct -0.2 for spelling, -0.3 for verb/word order/articles, -0.5 for agreement.
- Criterion 3 (Lèxic): Choose 2.0, 1.0, or 0.0.

STEP 2: PUBLIC FEEDBACK (Visible to student)
- **STRICT RULE: NEVER PROVIDE THE CORRECTED WORD.** - Wrong: "Change 'aeroline' to 'airline'" (FORBIDDEN)
- Right: "Check the spelling of the word 'aeroline'."
- Wrong: "It should be 'having dinner'" (FORBIDDEN)
- Right: "Check the verb choice in the phrase 'taking dinner'."

### OUTPUT FORMAT:
Your response must follow this structure exactly:

[INTERNAL_WORKSPACE]
(Write your math and error list here)

[PUBLIC_FEEDBACK]
Overall Impression: (Your intro)

###### **Adequació, coherència i cohesió (Score: X/4)**
(Feedback here)

###### **Morfosintaxi i ortografia (Score: X/4)**
(Feedback here - remember: explain the rule, do NOT give the answer)

###### **Lèxic (Score: X/2)**
(Feedback here)

###### **FINAL MARK: X/10**
"""

REVISION_COACH_PROMPT = """
### ROLE: REVISION CHECKER
Compare the NEW VERSION against the ORIGINAL FEEDBACK.
- List fixed errors under '✅ Improvements'.
- List missed errors under '⚠️ Still Needs Work'.
- DO NOT give a grade. DO NOT give answers/corrections.
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
        raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
        
        # --- PYTHON FILTER: This removes the Internal Workspace automatically ---
        if "[PUBLIC_FEEDBACK]" in raw_text:
            return raw_text.split("[PUBLIC_FEEDBACK]")[-1].strip()
        elif "Overall Impression:" in raw_text:
            return "Overall Impression:" + raw_text.split("Overall Impression:")[-1]
        return raw_text
    
    return "The teacher is busy. Try again in 10 seconds."

# 5. UI CONFIGURATION
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
                full_prompt = f"{RUBRIC_INSTRUCTIONS}\n\nWORD COUNT: {word_count}\nREQUIRED POINTS:\n{formatted_points}\n\nSTUDENT ESSAY:\n{essay}"
                fb = call_gemini(full_prompt)
                st.session_state.fb1 = fb
                
                mark_search = re.search(r"FINAL MARK:\s*(\d+[,.]?\d*/10)", fb)
                mark_value = mark_search.group(1) if mark_search else "N/A"
                
                requests.post(SHEET_URL, json={
                    "type": "FIRST", "Group": group, "Students": student_list, "Mark": mark_value,
                    "Draft 1": essay, "FB 1": fb, "Word Count": word_count
                })
                st.rerun()

# --- 2. DISPLAY FIRST FEEDBACK ---
if st.session_state.fb1:
    st.markdown("---")
    st.markdown(f"""<div style="background-color: #f0f7ff; color: #1a4a7a; padding: 25px; border-radius: 15px; border: 1px solid #b3d7ff; line-height: 1.8;">
            <h3 style="color: #1a4a7a; border-bottom: 1px solid #b3d7ff; padding-bottom: 10px;">🔍 Feedback on Draft 1</h3>
            {st.session_state.fb1}</div>""", unsafe_allow_html=True)

    # --- 3. REVISION BUTTON ---
    if not st.session_state.fb2:
        st.info("💡 **Instructions:** Edit your original text in the box above to fix the mistakes listed in the feedback. When you are finished, click the button below.")
        if st.button("🚀 Submit Final Revision", use_container_width=True):
            with st.spinner("✨ Teacher is reviewing your changes..."):
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
    st.markdown(f"""<div style="background-color: #e6ffed; color: #155724; padding: 25px; border-radius: 15px; border: 1px solid #c3e6cb; margin-top: 20px; line-height: 1.8;">
            <h3 style="color: #155724; border-bottom: 1px solid #c3e6cb; padding-bottom: 10px;">✅ Final Revision Feedback</h3>
            {st.session_state.fb2}</div>""", unsafe_allow_html=True)
