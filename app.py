import streamlit as st
import requests
import re
import time

# 1. SETUP
# Ensure you have .streamlit/secrets.toml set up with GEMINI_API_KEY and GOOGLE_SHEET_URL
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    st.error("Missing GEMINI_API_KEY in secrets.")
    st.stop()
    
if "GOOGLE_SHEET_URL" in st.secrets:
    SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]
else:
    st.error("Missing GOOGLE_SHEET_URL in secrets.")
    st.stop()

# --- CHANGE THESE EVERY TIME YOU START A NEW COMPOSITION TASK ---
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

# --- PROMPT 1: THE STRICT EXAMINER (For First Draft) ---
RUBRIC_EXAMINER = """
### ROLE: STRICT EXAMINER
You are a meticulous British English Examiner. You grade according to strict mathematical rules. You must follow these RED LINES:
1. WORD COUNT OVERRIDE: Look at the EXACT WORD COUNT provided. If text is UNDER 65 words, STOP. Return "Final Mark: 0/10" and note "Too short to mark."
2. LENGTH PENALTY: If text is BETWEEN 65 and 80 words, calculate the score, then DIVIDE BY 2. State: "Length penalty applied (<80 words)."
3. NO ANSWERS: NEVER correct the mistake. ONLY quote the error and explain the grammar rule.
4. ANONYMITY: Never mention the student's name.
5. NO CEFR/B2: Do not mention proficiency levels.

### GRADING ALGORITHM (Internal Processing):
1. **Content (0-4 pts):** Start at 4.0. Deduct:
   - 0.5 per missing Content Point.
   - 0.5 for Comma Splices (each).
   - 0.2 for missing Introductory Commas.
   - 1.0 if Connectors < 5 total OR Unique Connectors < 3.
2. **Morphosyntax/Spelling (0-4 pts):** Start at 4.0. Deduct:
   - 0.2 Spelling/Prepositions.
   - 0.3 Verb Tense/Articles/Pronouns/Word Order.
   - 0.5 Subject-Verb Agreement/ 'i' (lowercase).
3. **Vocabulary (0-2 pts):** Select 0 (Poor), 1 (Limited), or 2 (Rich).

### FINAL CALCULATION:
- Sum (Content + Morphosyntax + Vocabulary).
- IF Word Count < 80: Divide Sum by 2.
- Cap score at 0 if negative.

### OUTPUT FORMAT (Strictly Follow):
1. **Internal Workspace:** (Do your math here, list deductions. This section will be hidden).
2. **FEEDBACK START:** (Start public response here).
3. **Overall Impression:** (Brief intro).
4. **Adequació, coherència i cohesió (Score: X/4)** (Details here).
5. **Morfosintaxi i ortografia (Score: X/4)** (Details here).
6. **Lèxic (Score: X/2)** (Details here).
7. **FINAL MARK: X/10** (End with this line).
"""

# --- PROMPT 2: THE REVISION COACH (For Final Feedback) ---
# This prompt is simplified to avoid confusing the AI with math during the revision check.
RUBRIC_COACH = """
### ROLE: REVISION CHECKER
You are a helpful writing tutor. Your ONLY goal is to check if the student has improved their text based on previous feedback.
DO NOT CALCULATE A NEW SCORE. DO NOT USE THE GRADING RUBRIC.

### INPUT DATA:
1. **PREVIOUS FEEDBACK:** The errors the student was told to fix.
2. **NEW DRAFT:** The student's corrected text.

### YOUR MISSION:
1. **Compare:** Check the NEW DRAFT against the PREVIOUS FEEDBACK.
2. **Verify:** Did they fix the specific errors mentioned?
3. **Scan:** Did they introduce any MAJOR new errors?

### OUTPUT FORMAT:
Start your response immediately with the feedback. Use this structure:

**✅ Improvements**
* List specific errors from the feedback that the student has successfully fixed.
* Be specific (e.g., "You correctly changed 'people is' to 'people are'.")

**⚠️ Still Needs Work**
* List errors from the previous feedback that were NOT fixed or were fixed incorrectly.
* Explain the rule again simply.

**🆕 New Observations**
* (Optional) Only if they added new text that contains significant errors.

**🏁 Final Comment**
* A brief, encouraging sentence about their revision effort.
"""

# 3. SESSION STATE INITIALIZATION
if 'essay_content' not in st.session_state:
    st.session_state.essay_content = ""
if 'draft1_content' not in st.session_state:
    st.session_state.draft1_content = ""  # Store the original text specifically
if 'fb1' not in st.session_state:
    st.session_state.fb1 = ""
if 'fb2' not in st.session_state:
    st.session_state.fb2 = ""

# 4. AI CONNECTION FUNCTION
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0, # Keep temp low for strict adherence
            "topP": 0.8,
            "topK": 10
        }
    }
    
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    return result['candidates'][0]['content']['parts'][0]['text']
                else:
                    return "Error: AI returned an empty response."
            elif response.status_code == 429:
                time.sleep(5)
                continue
            else:
                return f"Error {response.status_code}: {response.text}"
        except Exception as e:
            return f"Connection Error: {str(e)}"
            
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
    .stTextArea textarea {
        font-size: 18px !important;
        line-height: 1.6 !important;
        font-family: 'Source Sans Pro', sans-serif !important;
    }
    .stCaption { font-size: 14px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📝 Writing Task")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Group", [" ","3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1")
    s2 = st.text_input("Student 2")
    names = [s.strip() for s in [s1, s2] if s.strip()]
    student_list = ", ".join(names)

# Main Essay Area
st.markdown(f"### 📋 Task Description")
st.info(TASK_DESC)

# Text Area Management
# If we haven't submitted Draft 1, the box is editable. 
# After feedback, it stays editable for the revision.
essay = st.text_area("Write your composition below:", value=st.session_state.essay_content, height=400)
st.session_state.essay_content = essay 

word_count = len(essay.split())
st.caption(f"Word count: {word_count}")

# --- 1. FIRST FEEDBACK BUTTON (DRAFT 1) ---
if not st.session_state.fb1:
    if st.button("🔍 Get Feedback (Draft 1)", use_container_width=True):
        if not s1 or not essay:
            st.error("Please enter your name and write your composition first.")
        else:
            with st.spinner("Teacher is marking your composition..."):
                # Save Draft 1 explicitely so we can log it later
                st.session_state.draft1_content = essay
                
                full_prompt = f"""
{RUBRIC_EXAMINER}

STATISTICS:
- EXACT WORD COUNT: {word_count} words
- REQUIRED CONTENT: {', '.join(REQUIRED_CONTENT_POINTS)}
- TASK: {TASK_DESC}

STUDENT ESSAY:
\"\"\"
{essay}
\"\"\"

COMMAND: Perform the internal workspace calculation, but ONLY output the text following 'FEEDBACK STRUCTURE'.
"""
                fb = call_gemini(full_prompt)

                if "Error" not in fb and "busy" not in fb:
                    st.session_state.fb1 = fb
                    
                    # Extract mark for Google Sheets
                    mark_search = re.search(r"FINAL MARK:\s*(\d+[,.]?\d*)/10", fb)
                    mark_value = mark_search.group(1) if mark_search else "N/A"

                    # Log to Google Sheets
                    requests.post(SHEET_URL, json={
                      "type": "FIRST", 
                      "Group": group, 
                      "Students": student_list, 
                      "Task": TASK_DESC[:50],
                      "Mark": mark_value,
                      "Draft 1": essay,
                      "FB 1": fb,
                      "Final Essay": "",
                      "FB 2": "",
                      "Word Count": word_count
                    })                  
                    st.rerun()
                else:
                    st.error(fb)

# --- 2. DISPLAY FIRST FEEDBACK ---
if st.session_state.fb1:
    st.markdown("---")
    # Clean up the feedback (remove internal workspace if the AI leaked it)
    display_fb1 = st.session_state.fb1
    if "FEEDBACK START:" in display_fb1:
        display_fb1 = display_fb1.split("FEEDBACK START:")[-1]

    st.markdown(f"""
        <div style="background-color: #e7f3ff; color: #1a4a7a; padding: 20px; border-radius: 12px; border: 1px solid #b3d7ff;">
            <h3>🔍 Feedback on Draft 1</h3>
            <div>{display_fb1}</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.info("👇 **Now, edit your text in the box above to fix these mistakes.** Then click the button below.")

    # --- 3. REVISION BUTTON (DRAFT 2) ---
    if not st.session_state.fb2:
        if st.button("🚀 Submit Final Revision", use_container_width=True):
            # Check if text actually changed
            if essay.strip() == st.session_state.draft1_content.strip():
                st.warning("You haven't changed your text yet! Please correct your mistakes in the text box above before submitting.")
            else:
                with st.spinner("✨ Teacher is reviewing your changes..."):
                    
                    # USE THE SIMPLIFIED COACH PROMPT HERE
                    rev_prompt = f"""
{RUBRIC_COACH}

--- START OF DATA ---

[PREVIOUS FEEDBACK GIVEN TO STUDENT]
{st.session_state.fb1}

[NEW REVISED DRAFT FROM STUDENT]
{essay}

--- END OF DATA ---
"""
                    fb2 = call_gemini(rev_prompt)
                    
                    if "Error" not in fb2 and "busy" not in fb2:
                        st.session_state.fb2 = fb2
                        
                        # Log Revision to Sheets
                        requests.post(SHEET_URL, json={
                            "type": "REVISION", 
                            "Group": group, 
                            "Students": student_list,
                            "Task": TASK_DESC[:50],
                            "Mark": "REVISED",
                            "Draft 1": st.session_state.draft1_content,
                            "FB 1": "---",
                            "Final Essay": essay,
                            "FB 2": fb2,
                            "Word Count": word_count
                        })
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(fb2)

# --- 4. FINAL FEEDBACK ---
if st.session_state.fb2:
    st.markdown(f"""
        <div style="background-color: #d4edda; color: #155724; padding: 20px; border-radius: 12px; border: 1px solid #c3e6cb; margin-top: 20px;">
            <h3>✅ Final Revision Feedback</h3>
            <div>{st.session_state.fb2}</div>
        </div>
    """, unsafe_allow_html=True)
