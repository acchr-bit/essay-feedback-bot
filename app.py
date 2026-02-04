import streamlit as st
import requests
import re
import time

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]

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
# ----------------------------------------------------------------

# 2. THE STERN TEACHER PROMPT
RUBRIC_INSTRUCTIONS = """
You are a strict British English Examiner. You must follow these 4 RED LINES:
1. WORD COUNT OVERRIDE: Look at the EXACT WORD COUNT provided. If the text is UNDER 65 words, STOP immediately. Do not grade the criteria. Provide the note "Your composition is too short to be marked." and set 'FINAL MARK: 0/10'.
2. LENGTH PENALTY: Look at the EXACT WORD COUNT provided. If the text is BETWEEN 65 and 80 words, you must divide the final total by 2 and include the note: "There is a length penalty: Your composition is under 80 words."
3. NO ANSWERS: NEVER provide the corrected version of a mistake. If you write the correct form, you have failed your mission. You must ONLY quote the error and explain the grammar rule behind it. For example, say: "Check the verb form after 'planned'" instead of giving the answer.
4. NEVER mention the student's name in any of your feedbacks.
5. NEVER use the term "B2" or "CEFR" in the feedback.
6. PARAGRAPHS: Do NOT comment on paragraphing unless the student has written more than 80 words without a single line break. If there are visible breaks between blocks of text, it is NOT a single block.

### THE GRADING RULES (Internal use only):
- CRITERION 1 (0–4 pts): Start 4,0. 
  - Deduct: Genre (-1), Register (-0,5), Paragraphs (-0,5).
  - Content Coverage: I will provide a list of REQUIRED CONTENT POINTS. Deduct -0,5 for EACH point from that list that is missing. 
  - IMPORTANT: DO NOT deduct points for information mentioned in the Task Context if it is NOT in the Required Content Points list.
  - Connectors: Deduct -1 if fewer than 5 total connectors or fewer than 3 DIFFERENT connectors are used. 
  - Punctuation & Cohesion: Deduct for missing commas after introductory phrases and Comma Splices (joining two independent sentences with a comma instead of a full stop or connector).
  - Punctuation scale: 1-2 mistakes (-0,4), 3-4 (-0,6), 5+ (-1).
- CRITERION 2 (0–4 pts): Start 4,0. Deduct: Wrong word order (-0,3 each), verb tense (-0,3 each), 'to be/have' form (-0,5 each), Subject-verb agreement (-0,5 each), Spelling (-0,2 each), Prepositions (-0,2 each), Collocations (-0,1 each), small 'i' (-0,5 each), articles (-0,3 each), wrong or missing pronouns (-0,3 each), comparative or superlative (-0,3 each).
- CRITERION 3 (0–2 pts): 2 (Rich), 1 (Limited), 0 (Poor).
- WORD COUNT PENALTY: If the text is under 80 words, calculate the total (C1+C2+C3) and divide by 2.

### FEEDBACK STRUCTURE:
1. Write the header 'Overall Impression: ' and give an overall impression.
2. Leave two blank lines (hit Enter twice)
3. Use the following exact headers in bold:

'Adequació, coherència i cohesió (Score: X/4)'
- Discuss organization of ideas in paragraphs, genre, register, and punctuation. 
- Content: ONLY check for the items in the 'REQUIRED CONTENT POINTS' list. If they are present, do not mention missing details from the Task Context.
- For punctuation errors, quote the phrase and explain the rule without correcting it.
- Comma Splices: If found, quote them here. Explain that a comma cannot join two complete sentences and suggest using a full stop or a connector, but do not write the corrected sentence.
- Introductory Commas: Mention missing commas after time/place phrases here.
- Discuss connectors (quantity and variety).

'Morfosintaxi i ortografia (Score: X/4)'
- INTERNAL STEP (Do not show this to the student): Perform a word-by-word scan. List every error and its deduction value from the rubric (e.g., Spelling -0,2, Verb Tense -0,3). Subtract the total from 4,0. 
- STUDENT-FACING FEEDBACK:
  1. Quote every morphosyntactic and lexical-grammar error found (e.g. verb tense, agreement, prepositions, word order, collocations, articles, and pronouns).
  2. Explain the grammar rule behind the error so the student can find the correction themselves.
  3. DO NOT mention the specific point deduction (e.g., "-0,3") for individual errors.
  4. CRITICAL: Strictly forbidden from typing the corrected phrase. If you type the correction, the student will not learn. Your explanation must guide them to the answer without revealing it.
  5. For spelling, use: "Check the capitalization/spelling of the word [wrong word]".
- FINAL ACTION: Provide the calculated score ONLY at the header: 'Morfosintaxi i ortografia (Score: [Result]/4)'.

'Lèxic (Score: X/2)'
- Indicate if the vocabulary is "rich", "suitable but not rich" or "poor".

### FINAL GRADE CALCULATION:
Sum C1+C2+C3. Apply the RED LINE word count penalties if applicable.
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
    # data = {"contents": [{"parts": [{"text": prompt}]}]}
    # We add "generationConfig" to set the temperature to 0
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,  # This makes the AI much more consistent/deterministic
            "topP": 0.8,
            "topK": 10
        }
    }
  
    for attempt in range(3):
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        elif response.status_code == 429:
            time.sleep(5)
            continue
    return "The teacher is busy. Try again in 10 seconds."

# 5. UI CONFIGURATION
st.set_page_config(page_title="Writing Test", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Hides Streamlit UI elements */
    [data-testid="stHeaderActionElements"], .stDeployButton, [data-testid="stToolbar"], 
    [data-testid="stSidebarCollapseButton"], #MainMenu, [data-testid="stDecoration"], footer {
        display: none !important;
    }
    header { background-color: rgba(0,0,0,0) !important; }

    /* MAKES THE TEXT INSIDE THE WRITING BOX BIGGER */
    .stTextArea textarea {
        font-size: 18px !important;
        line-height: 1.6 !important;
        font-family: 'Source Sans Pro', sans-serif !important;
    }
    
    /* MAKES THE CAPTION (WORD COUNT) SLIGHTLY LARGER */
    .stCaption {
        font-size: 14px !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📝 Writing")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Group", [" ","3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1 - Name and Surname")
    s2 = st.text_input("Student 2 - Name and Surname")
    s3 = st.text_input("Student 3 - Name and Surname")
    s4 = st.text_input("Student 4 - Name and Surname")
    names = [s.strip() for s in [s1, s2, s3, s4] if s.strip()]
    student_list = ", ".join(names)

# Main Essay Area
# 1. Display the Task Description in a larger font
st.markdown(f"### 📋 Task Description")
st.markdown(f"<div style='font-size: 20px; line-height: 1.5; margin-bottom: 20px;'>{TASK_DESC}</div>", unsafe_allow_html=True)

# 2. The Text Area (we use a simple title here or an empty string "")
essay = st.text_area("Write your essay below:", value=st.session_state.essay_content, height=400)
st.session_state.essay_content = essay

word_count = len(essay.split())
st.caption(f"Word count: {word_count}")

# --- 1. FIRST FEEDBACK BUTTON ---
if not st.session_state.fb1 or st.session_state.fb1 == "The teacher is busy. Try again in 10 seconds.":
    if st.button("🔍 Get Feedback", use_container_width=True):
        if not s1 or not essay:
            st.error("Please enter your names and write your essay first.")
        else:
            with st.spinner("Teacher is marking your first draft..."):
                formatted_points = "\n".join([f"- {p}" for p in REQUIRED_CONTENT_POINTS])
                full_prompt = (
                    f"{RUBRIC_INSTRUCTIONS}\n\n"
                    f"STATISTICS:\n"
                    f"- EXACT WORD COUNT: {word_count} words\n\n"              
                    f"REQUIRED CONTENT POINTS:\n{formatted_points}\n\n"
                    f"TASK CONTEXT:\n{TASK_DESC}\n\n"
                    f"EXAMINER TASK: You are now proofreading for minor grammatical slips, specifically article usage (a/an) and singular/plural agreement and verb tenses.\n"
                    f"STUDENT ESSAY (PLEASE OBSERVE THE PARAGRAPHS BELOW):\n"
                    f"\"\"\"\n"
                    f"{essay}\n"
                    f"\"\"\""
                    f"REMINDER: In the Morfosintaxi section, explain the errors to the student but keep the deduction math hidden. Only show the final header score."
                )

                fb = call_gemini(full_prompt)
                st.session_state.fb1 = fb

                if fb != "The teacher is busy. Try again in 10 seconds.":
                    mark_search = re.search(r"FINAL MARK:\s*(\d+,?\d*/10)", fb)
                    mark_value = mark_search.group(1) if mark_search else "N/A"
                    requests.post(SHEET_URL, json={
                      "type": "FIRST", 
                      "Group": group, 
                      "Students": student_list, 
                      "Task": TASK_DESC,
                      "Mark": mark_value,      # Col 5
                      "Draft 1": essay,        # Col 6
                      "FB 1": fb,              # Col 7
                      "Final Essay": "",       # Col 8 (Placeholder)
                      "FB 2": "",              # Col 9 (Placeholder)
                      "Word Count": word_count # Col 10
})                 
                    st.rerun()
                else:
                    st.error(fb)

# --- 2. DISPLAY FIRST FEEDBACK ---
if st.session_state.fb1 and st.session_state.fb1 != "The teacher is busy. Try again in 10 seconds.":
    st.markdown("---")
    fb1_text = st.session_state.fb1
    st.markdown(f"""
        <div style="background-color: #e7f3ff; color: #1a4a7a; padding: 20px; border-radius: 12px; border: 1px solid #b3d7ff; line-height: 1.6; margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #1a4a7a; border-bottom: 2px solid #b3d7ff; padding-bottom: 10px;">
                🔍 Read the feedback and improve your composition
            </h3>
            <div style="margin-top: 15px;">{fb1_text}</div>
        </div>
    """, unsafe_allow_html=True)
  
    # --- 3. REVISION BUTTON ---
    if not st.session_state.fb2:
        if st.button("🚀 Submit Final Revision", use_container_width=True):
            with st.spinner("✨ Teacher is reviewing your changes... please wait."):
                rev_prompt = (
                    f"--- ORIGINAL FEEDBACK ---\n{st.session_state.fb1}\n\n"
                    f"--- NEW REVISED VERSION ---\n{essay}\n\n"
                    f"- EXACT WORD COUNT: {word_count} words\n\n"
                    f"CRITICAL INSTRUCTIONS:\n"
                    f"1. Compare NEW VERSION to ORIGINAL FEEDBACK to see if previous errors were fixed.\n"
                    f"2. IMPORTANT: Scan the NEW VERSION for any NEW grammar, spelling, or punctuation errors introduced during the rewrite.\n"
                    f"3. Mention both the improvements AND any new issues found.\n"
                    f"4. NO new grade. NO names. NO B2."
                )
              
            #    rev_prompt = (
             #       f"--- ORIGINAL FEEDBACK ---\n{st.session_state.fb1}\n\n"
              #      f"--- NEW REVISED VERSION ---\n{essay}\n\n"
               #     f"CRITICAL INSTRUCTIONS:\n1. Compare NEW VERSION to ORIGINAL FEEDBACK.\n"
                #    f"2. Check if quoted errors were fixed.\n3. NO new grade. NO names. NO B2."
                #)
                fb2 = call_gemini(rev_prompt)
                
                if fb2 != "The teacher is busy. Try again in 10 seconds.":
                    st.session_state.fb2 = fb2
                    # THIS BLOCK MUST BE INDENTED TO BE INSIDE THE SUCCESS CONDITION
                    requests.post(SHEET_URL, json={
                        "type": "REVISION", 
                        "Group": group, 
                        "Students": student_list,
                        "Task": TASK_DESC,
                        "Mark": "REVISED",       # Column 5
                        "Draft 1": "---",        # Column 6
                        "FB 1": "---",           # Column 7
                        "Final Essay": essay,    # Column 8
                        "FB 2": fb2,             # Column 9
                        "Word Count": word_count # Column 10
                    })
                    st.balloons()
                    st.rerun()
                else:
                    st.error(fb2)

# --- 4. FINAL FEEDBACK ---
if st.session_state.fb2:
    fb2_text = st.session_state.fb2
    st.markdown(f"""
        <div style="background-color: #d4edda; color: #155724; padding: 20px; border-radius: 12px; border: 1px solid #c3e6cb; margin-top: 20px;">
            <h3 style="margin-top: 0; color: #155724; border-bottom: 2px solid #c3e6cb; padding-bottom: 10px;">
                ✅ Final Revision Feedback
            </h3>
            <div style="margin-top: 15px;">{fb2_text}</div>
        </div>
    """, unsafe_allow_html=True)
