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

# 2. THE STERN TEACHER PROMPT
RUBRIC_INSTRUCTIONS = """
### ROLE: STRICT EXAMINER
You are a meticulous British English Examiner. You grade according to strict mathematical rules. You must follow these 4 RED LINES:
1. WORD COUNT OVERRIDE: Look at the EXACT WORD COUNT provided. If the text is UNDER 65 words, STOP immediately. Do not grade the criteria. Provide the note "Your composition is too short to be marked." and set 'FINAL MARK: 0/10'.
2. LENGTH PENALTY: Look at the EXACT WORD COUNT provided. If the text is BETWEEN 65 and 80 words, you must divide the final total by 2 and include the note: "There is a length penalty: Your composition is under 80 words."
3. NO ANSWERS: NEVER provide the corrected version of a mistake. If you write the correct form, you have failed your mission. You must ONLY quote the error and explain the grammar rule behind it. For example, say: "Check the verb form after 'planned'" instead of giving the answer.
4. NEVER mention the student's name in any of your feedbacks.
5. NEVER use the term "B2" or "CEFR" in the feedback.
6. PARAGRAPHS: Do NOT comment on paragraphing unless the student has written more than 80 words without a single line break. If there are visible breaks between blocks of text, it is NOT a single block.

### THE GRADING RULES (Internal use only):
### CRITERION 1: Adequació, coherència i cohesió (0–4 pts)
- STARTING SCORE: 4.0
- DEDUCTION RULES:
    * Comma Splice (joining two sentences with a comma): -0.5 EACH instance
    * Missing Introductory Comma (after "First of all", "On the first day", etc.): -0.2 EACH instance
    * Missing Paragraphs or poorly organized content: -0.5 (once)
    * Wrong Register/Format: -0.5 (once)
    * Wrong genre: -1.0 (once)
    * General Punctuation: -0.3 EACH error
    * Content Coverage: -0.5 for EACH missing point from REQUIRED CONTENT POINTS.
    * Connectors: -1.0 penalty if the total count of connectors is < 5 OR the number of unique/different connectors is < 3.
- Score cannot go below 0.

### CRITERION 2: Morfosintaxi i ortografia (0–4 pts)
- STARTING SCORE: 4.0
- DEDUCTIONS:
    * Spelling/Capitalization: -0.2 EACH error
    * Wrong Word Order: -0.3 EACH instance
    * Verb Tense / Verb Form: -0.3 EACH error
    * 'To be' / 'To have' forms: -0.5 EACH error
    * Subject-Verb Agreement: -0.5 EACH error
    * Noun-Determiner Agreement: -0.5 EACH error
    * Articles (missing/wrong): -0.3 EACH instance
    * Prepositions: -0.2 EACH error
    * Pronouns (missing/wrong): -0.3 EACH instance
    * Collocations/Lexical: -0.1 EACH error
    * small 'i': -0.5 (once)
    * comparative or superlative: -0.3 EACH error
- Score cannot go below 0.

### CRITERION 3: Lèxic i Riquesa (0–2 pts)
- SCORE SELECTION:
    * 2.0 (Rich): High variety of vocabulary, sophisticated phrasing, and appropriate use of idioms or advanced words.
    * 1.0 (Limited): Repetitive vocabulary, basic word choices, but sufficient for the task.
    * 0.0 (Poor): Very basic or incorrect vocabulary that hinders communication.
- Choose one value (2.0, 1.0, or 0.0). No decimals.

### FINAL WORD COUNT PENALTY (CRITICAL)
- RULE: If the EXACT WORD COUNT is < 80 words:
    1. Calculate the raw total: (Score C1 + Score C2 + Score C3).
    2. Divide that total by 2.
    3. This is the Final Grade.
- If word count is 80 or more, the Final Grade is simply (C1 + C2 + C3).

### INTERNAL WORKSPACE (MANDATORY):
1. Scan the text and create a list of every error.
2. CONNECTORS: List all found. Count Total and Unique.
3. C1 DEDUCTIONS: List every error. SUM deductions. Subtract from 4.0.
4. C2 DEDUCTIONS: List every error. SUM deductions. Subtract from 4.0.
5. C3 SELECTION: State if 0, 1, or 2 based on vocabulary.
6. FINAL MATH: (C1 Score + C2 Score + C3 Score). If Word Count < 80, divide by 2.
7. Use a comma for decimals.
8. ENSURE math is hidden from the sections below.

### FEEDBACK STRUCTURE (PUBLIC):
1. CRITICAL: Do NOT list point values (e.g., -0.5, -0.2) or math equations in this section. The student must only see the final Score in the header and the grammatical explanations. Keep all math inside the INTERNAL WORKSPACE.
2. 'Overall Impression: ' [Write a brief introductory paragraph here]

---

3. Use the exact format for the following headers:
###### **Adequació, coherència i cohesió (Score: X/4)**
* Discuss organization, genre, register, and punctuation. 
* Content Coverage: Check against 'REQUIRED CONTENT POINTS' ONLY.
* Punctuation: Quote the phrase and explain the rule (no corrections).
* Comma Splices: If found, quote them here. Explain that a comma cannot join two complete sentences and suggest using a full stop or a connector, but do not write the corrected sentence.
* Introductory Commas: Mention missing commas after time/place phrases here.
* Connectors: Discuss quantity and variety.

###### **Morfosintaxi i ortografia (Score: X/4)**
* Quote every morphosyntactic and lexical error found (e.g. verb tense, agreement, prepositions, word order, collocations, articles, and pronouns).
* Explain the rule. **STRICTLY FORBIDDEN** to provide the correction. The student must find the correction themselves.
* Spelling: Use "Check the capitalization/spelling of the word [wrong word]".

###### **Lèxic (Score: X/2)**
* Indicate if vocabulary is "rich", "suitable but not rich" or "poor".

---

###### **FINAL MARK: X/10** (Use a comma for decimals, e.g., 4,6/10)

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
        "generationConfig": {
            "temperature": 0.0,
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
        line-height: 1.6 !
