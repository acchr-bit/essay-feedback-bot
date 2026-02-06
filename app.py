import streamlit as st
import requests
import re
import time

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]

# --- CHANGE THESE EVERY TIME YOU START A NEW COMPOSITION TASK ---
TASK_TITLE = "End of Year Trip Email"
REQUIRED_CONTENT_POINTS = [
    "Plans for the trip",
    "Places you are going to visit",
    "Activities you are going to do",
    "Information about classmates, friends, and family"
]
# ----------------------------------------------------------------
# 2. THE STERN TEACHER PROMPT (Strict Content Filtering)
RUBRIC_INSTRUCTIONS = """
You are a British English Examiner. You must follow these 4 RED LINES:
1. NEVER mention the student's name in any of your feedbacks.
2. NEVER use the term "B2" or "CEFR" in the feedback.
3. NEVER provide the corrected version of a mistake. If you give the answer, you fail.
4. ONLY comment on missing paragraphs if the text is literally one single block of text.

### THE GRADING RULES (Internal use only):
- CRITERION 1 (0–4 pts): Start 4,0. 
  - Deduct: Genre (-1), Register (-0,5), Paragraphs (-0,5).
  - Content Coverage: I will provide a list of REQUIRED CONTENT POINTS. Deduct -0,5 for EACH point from that list that is missing. 
  - IMPORTANT: DO NOT deduct points for information mentioned in the Task Context if it is NOT in the Required Content Points list.
  - Connectors: Deduct -1 if fewer than 5 total connectors or fewer than 3 DIFFERENT connectors are used. 
  - Punctuation: 1-2 mistakes (-0,4), 3-4 (-0,6), 5+ (-1).
- CRITERION 2 (0–4 pts): Start 4,0. Deduct: Wrong word order (-0,3 each), Tense (-0,3 each), 'to be/have' (-0,5 each), Subject-verb agreement (-0,5 each), Spelling (-0,2 each), Prepositions (-0,2 each), Collocations (-0,1 each), small 'i' (-0,5 each).
- CRITERION 3 (0–2 pts): 2 (Rich), 1 (Limited), 0 (Poor).
- WORD COUNT PENALTY: If the text is under 80 words, calculate the total (C1+C2+C3) and divide by 2.

### FEEDBACK STRUCTURE:
Start with 'Overall Impression'. Then use these exact headers:

'Adequació, coherència i cohesió (Score: X/4)'
- Discuss organization, genre, register, and punctuation. 
- Content: ONLY check for the items in the 'REQUIRED CONTENT POINTS' list. If they are present, do not mention missing details from the Task Context.
- For punctuation errors, quote the phrase and explain the rule without correcting it.
- Discuss connectors (quantity and variety).

'Morfosintaxi i ortografia (Score: X/4)'
- Quote every grammar error and explain the rule.
- For spelling, say: "Check the capitalization/spelling of the word [wrong word]". DO NOT type the corrected word.

'Lèxic (Score: X/2)'
- Indicate if the vocabulary is "rich", "suitable but not rich" or "poor".

'Recommendations'
- Give 2 bullet points for improvement.

### FINAL GRADE CALCULATION:
If the word count is under 80 words, include a note: "Length Penalty: Composition is under 80 words; the total score has been divided by 2."
AT THE VERY END, write 'FINAL MARK: X/10' (Use a comma for decimals).
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
    return "The teacher is busy. Try again in 10 seconds."

# 5. UI
st.set_page_config(
    page_title="Writing Test", 
    layout="centered",
    initial_sidebar_state="expanded" # Start with it open
)

# --- CSS TO HIDE ICONS AND LOCK SIDEBAR OPEN ---
st.markdown("""
    <style>
    /* 1. Hide the right-side icons (Share, GitHub, etc.) */
    [data-testid="stHeaderActionElements"], .stDeployButton, [data-testid="stToolbar"] {
        display: none !important;
    }

    /* 2. Hide the 'Close' button (the arrow) on the sidebar so it can't be hidden */
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    /* 3. Hide the main hamburger menu (the three lines) */
    #MainMenu {
        visibility: hidden;
    }

    /* 4. Hide the top decoration line and the footer */
    [data-testid="stDecoration"], footer {
        display: none !important;
    }

    /* 5. Clean up the header background so it's invisible but exists */
    header {
        background-color: rgba(0,0,0,0) !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📝 Writing Test")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Group", [" ","3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1 - Name and Surname")
    s2 = st.text_input("Student 2 - Name and Surname")
    s3 = st.text_input("Student 3 - Name and Surname")
    s4 = st.text_input("Student 4 - Name and Surname")
    names = [s.strip() for s in [s1, s2, s3, s4] if s.strip()]
    student_list = ", ".join(names)

task_desc = "This is your last year at school and you are planning your end of year trip together with your classmates and teachers. Write an email to Liam, your exchange partner from last year, who has just sent you an email. Tell him about your plans for the trip: the places you are going to visit, the activities you are going to do there, and also about your classmates, friends and family."
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
            # Format the dynamic content points for the AI
            formatted_points = "\n".join([f"- {p}" for p in REQUIRED_CONTENT_POINTS])
            
            full_prompt = (
                f"{RUBRIC_INSTRUCTIONS}\n\n"
                f"REQUIRED CONTENT POINTS FOR THIS TASK:\n{formatted_points}\n\n"
                f"TASK CONTEXT:\n{task_desc}\n\n"
                f"STUDENT ESSAY:\n{essay}"
            )
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
            rev_prompt = (
                f"--- ORIGINAL FEEDBACK ---\n{st.session_state.fb1}\n\n"
                f"--- NEW REVISED VERSION ---\n{essay}\n\n"
                f"CRITICAL INSTRUCTIONS FOR THE EXAMINER:\n"
                f"1. You are a strict proofreader. Compare the NEW VERSION to the ORIGINAL FEEDBACK.\n"
                f"2. Check if the errors quoted in the first feedback were fixed correctly.\n"
                f"3. If a student 'half-fixes' something (e.g., they fix the grammar but introduce a new spelling mistake like 'travell'), you MUST identify it as a failed fix.\n"
                f"4. Be very specific. Use phrasing like: 'You attempted to fix X, but you introduced a new spelling error: Y'.\n"
                f"5. Do NOT say 'Corrected' unless it is 100% perfect.\n"
                f"6. DO NOT give a new grade. NEVER mention names. NEVER mention B2."
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
