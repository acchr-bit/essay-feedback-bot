import streamlit as st
import requests
import re
import time

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]

# 2. THE STERN TEACHER PROMPT (No Corrections, No Names, No "B2" mention)
RUBRIC_INSTRUCTIONS = """
You are a British English Examiner. You must follow these 4 RED LINES:
1. NEVER mention the student's name in any of your feedbacks (first feedback or last feedback).
2. NEVER use the term "B2" or "CEFR" in the feedback.
3. NEVER provide the corrected version of a mistake. If you give the answer, you fail.
4. ONLY comment on missing paragraphs if the text is literally one single block of text.

### THE GRADING RULES (Internal use only):
- CRITERION 1 (0–4 pts): Start 4,0. Deduct: Genre (-1), Register (-0,5), missing info (-0,5), Connectors (fewer than 5 total or 3 different = -1). Punctuation: 1-2 mistakes (-0,3), 3-4 (-0,6), 5+ (-1).
- CRITERION 2 (0–4 pts): Start 4,0. Deduct: Tense (-0,3), 'to be/have' (-0,4), Subject-verb agreement (-0,4), Spelling (-0,2), Prepositions (-0,2), Collocations (-0,1), small 'i' (-0,5).
- CRITERION 3 (0–2 pts): 2 (Rich), 1 (Limited), 0 (Poor).
- TOTAL: Sum C1+C2+C3. If under 80 words, divide total by 2.

### FEEDBACK STRUCTURE:
Start with 'Overall Impression'. Then use these exact headers:

'Adequació, coherència i cohesió'
- Discuss organization of ideas and paragraphs.
- Discuss Genre and resgister.
- Discuss punctuation.
- Discuss connectors.
- For each wrong punctuation mark, quote the phrase and explain the rule (e.g., "You need a stronger break between these two independent clauses") but DO NOT show the corrected punctuation.

'Morfosintaxi i ortografia'
- Quote the error. Write the full list of grammar errors.
- Explain the grammar rule. Example: "In the phrase 'we was', the verb does not match the plural subject." or "Wrong form of comparative adjective." or "Wrong verb tense."
- For spelling, say: "Check the capitalization of the word" and add the word or "There is a spelling mistake in the word" and add the wrong word. DO NOT type the corrected word.

'Lèxic'
- Indicate if the vocabulary is rich, limited or poor.

'Recommendations'
- Give 2 bullet points for improvement.

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
st.set_page_config(page_title="Writing Portal", layout="centered")
st.title("📝 Writing Assessment")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Group", ["3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1 Name and Surname")
    s2 = st.text_input("Student 2 Name and Surname (Optional)")
    s3 = st.text_input("Student 3 Name and Surname (Optional)")
    s4 = st.text_input("Student 4 Name and Surname (Optional)")
    names = [s.strip() for s in [s1, s2, s3, s4] if s.strip()]
    student_list = ", ".join(names)

task_desc = "This is your last year at school and you are planning your end of year trip together with your classmates and teachers. Write an email to Liam, your exchange partner from last year, who has just sent you an email. Tell him about your plans for the trip: the places you are going to visit, the activities you are going to do there, and also about your classmates, friends and family."
essay = st.text_area("This is your last year at school and you are planning your end of year trip together with your classmates and teachers. Write an email to Liam, your exchange partner from last year, who has just sent you an email. Tell him about your plans for the trip: the places you are going to visit, the activities you are going to do there, and also about your classmates, friends and family.", value=st.session_state.essay_content, height=400)
st.session_state.essay_content = essay

word_count = len(essay.split())
st.caption(f"Word count: {word_count}")

col1, col2 = st.columns(2)

if col1.button("🔍 Get Feedback"):
    if not s1 or not essay:
        st.error("Enter your name and essay.")
    else:
        with st.spinner("Teacher is marking..."):
            # Task name is repeated in prompt for context
            full_prompt = f"{RUBRIC_INSTRUCTIONS}\n\nTASK: {task_desc}\n\nESSAY:\n{essay}"
            fb = call_gemini(full_prompt)
            
            mark_search = re.search(r"FINAL MARK:\s*(\d+,?\d*/10)", fb)
            mark_value = mark_search.group(1) if mark_search else "N/A"
            
            st.session_state.fb1 = fb
            
            requests.post(SHEET_URL, json={
                "type": "FIRST", "Group": group, "Students": student_list, 
                "Task": "Trip Email", "Mark": mark_value, "FB 1": fb, 
                "Draft 1": essay, "Word Count": word_count
            })
            st.rerun()

if st.session_state.fb1:
    st.markdown("---")
    st.info(st.session_state.fb1)

    if col2.button("🚀 Submit Final Revision"):
        with st.spinner("Checking revision..."):
            rev_prompt = (
                f"Original Feedback: {st.session_state.fb1}\n\n"
                f"Compare this new version to the draft. Did they fix the quoted errors? "
                f"Mention specific improvements without giving a new grade.\n\nNEW VERSION: {essay}"
            )
            fb2 = call_gemini(rev_prompt)
            st.session_state.fb2 = fb2
            
            requests.post(SHEET_URL, json={
                "type": "REVISION", "Group": group, "Students": student_list,
                "Final Essay": essay, "FB 2": fb2
            })
            st.balloons()

if st.session_state.fb2:
    st.success(st.session_state.fb2)
