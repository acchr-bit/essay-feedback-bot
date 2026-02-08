import streamlit as st
import requests
import re
import time
import json

# 1. SETUP
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]
DEBUG = True


# GRADING CONFIGURATION
MIN_ESSAI_WORD_COUNT = 65
GRADING_CONFIG = {
    "C1": {
        "start_score": 4.0,
        "rules": {
            "MPoPOC": {"penalty": 0.5, "type": "once", "label": "Organization/Paragraphs"},
            "WRF": {"penalty": 0.5, "type": "once", "label": "Register/Format"},
            "WG": {"penalty": 1.0, "type": "once", "label": "Genre Accuracy"},
            "MCP": {"penalty": 0.5, "type": "list", "label": "Content Points"},
            "CS": {"penalty": 0.2, "type": "list", "label": "Comma Splices"},
            "IC": {"penalty": 0.2, "type": "list", "label": "Introductory Commas"},
            "GP": {"penalty": 0.3, "type": "list", "label": "General Punctuation"},
        }
    },
    "C2": {
        "start_score": 4.0,
        "rules": {
            "SpCap": {"penalty": 0.2, "type": "list", "label": "Spelling/Caps"},
            "WWO": {"penalty": 0.3, "type": "list", "label": "Word Order"},
            "VTF": {"penalty": 0.3, "type": "list", "label": "Verb Tense/Form"},
            "TBTH": {"penalty": 0.5, "type": "list", "label": "To Be/To Have"},
            "SVA": {"penalty": 0.5, "type": "list", "label": "Subject-Verb Agreement"},
            "NDA": {"penalty": 0.3, "type": "list", "label": "Noun-Determiner Agreement"},
            "ART": {"penalty": 0.3, "type": "list", "label": "Articles"},
            "PREP": {"penalty": 0.2, "type": "list", "label": "Prepositions"},
            "PRO": {"penalty": 0.3, "type": "list", "label": "Pronouns"},
            "COLL": {"penalty": 0.1, "type": "list", "label": "Collocations"},
            "SI": {"penalty": 0.5, "type": "once", "label": "Small 'i' usage"},
            "CSU": {"penalty": 0.3, "type": "list", "label": "Comparatives/Superlatives"},
        }
    }
}

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

# 2. THE STERN TEACHER PROMPT
RUBRIC_INSTRUCTIONS = """
### ROLE: LINGUISTIC ANALYST (STRICT EXAMINER)
You are a meticulous British English Examiner. The level of your students is B2 in CEFR. Your task is to analyze the student's text and categorize every error found into a specific JSON structure.

### RULES:
1. **NO ANSWERS**: Never provide the corrected version of an error. 
2. **EXHAUSTIVE**: You must catch and categorize every single mistake.
3. **ONLY JSON**: Your entire output must be a single, valid JSON object.
4. **NO CEFR MENTION**: Never use "B2" or "CEFR" in the feedback.

### ERROR CATEGORIZATION LOGIC:
You must distinguish between **Global Issues** (listed once) and **Specific Occurrences** (list every instance).

### KEY DEFINITIONS (Use these codes):
#### Criterion 1 (Adequació):
- `MPoPOC`: Missing Paragraphs or poorly organized content.
- `WRF`: Wrong Register/Format (e.g., formal vs informal).
- `WG`: Wrong Genre (e.g., writing a story instead of an email).
- `MCP`: Missing Content Points (From the list provided).
- `CS`: Comma Splices (Joining two sentences with only a comma).
- `IC`: Missing Introductory Commas (After "First of all", "Yesterday", etc.).
- `GP`: General Punctuation (Missing full stops, capital letters at start of sentences).
- `CONN`: List of every connector used (e.g., "but", "however", "firstly").

#### Criterion 2 (Morfosintaxi):
- `SpCap`: Spelling or Capitalization errors.
- `WWO`: Wrong Word Order.
- `VTF`: Verb Tense or Verb Form errors.
- `TBTH`: Misuse of 'To Be' vs 'To Have'.
- `SVA`: Subject-Verb Agreement.
- `NDA`: Noun-Determiner Agreement.
- `ART`: Missing or wrong Articles (a, an, the).
- `PREP`: Wrong Prepositions.
- `PRO`: Pronoun errors.
- `COLL`: Lexical Collocations (words that don't sound natural together).
- `SI`: Use of lowercase 'i' instead of uppercase 'I'.
- `CSU`: Comparative or Superlative errors.

#### Criterion 3 (Lèxic):
- `VOC`: Vocabulary level (Must be "2.0", "1.0", or "0.0"). Depending on this criterion:
    - 2.0 (Rich): High variety of vocabulary, sophisticated phrasing, and appropriate use of idioms or advanced words.
    - 1.0 (Limited): Repetitive vocabulary, basic word choices, but sufficient for the task.
    - 0.0 (Poor): Very basic or incorrect vocabulary that hinders communication.

### JSON FORMATTING:
- Every value except `CONN`, `VOC`, and `IMP` must be a LIST of OBJECTS: `{"q": "quote", "r": "rule"}`. quote must be the specific quote of the text and rule is the explain the grammar rule behind it.
- If no error is found in this category, return an empty list `[]`.

### OUTPUT STRUCTURE:
{
  "C1": {
    "MPoPOC": [], "WRF": [], "WG": [], "MCP": [], 
    "CS": [], "IC": [], "GP": [], "CONN": []
  },
  "C2": {
    "SpCap": [], "WWO": [], "VTF": [], "TBTH": [], 
    "SVA": [], "NDA": [], "ART": [], "PREP": [], "PRO": [], "COLL": [], 
    "SI": [], "CSU": []
  },
  "C3": {"VOC": "1.0"},
  "OVERALL": {"IMP": "Brief general impression."}
}
"""

import json

def compute_mark(data, word_count):
    # Calculate C1
    c1_score = GRADING_CONFIG["C1"]["start_score"]
    for key, rule in GRADING_CONFIG["C1"]["rules"].items():
        errors = data["C1"].get(key, [])
        count = 1 if rule["type"] == "once" and errors else len(errors)
        c1_score -= (count * rule["penalty"])
    
    # Connector Penalty logic
    conns = data["C1"].get("CONN", [])
    if len(conns) < 5 or len(set(conns)) < 3:
        c1_score -= 1.0
    c1_score = max(0, c1_score)

    # Calculate C2
    c2_score = GRADING_CONFIG["C2"]["start_score"]
    for key, rule in GRADING_CONFIG["C2"]["rules"].items():
        errors = data["C2"].get(key, [])
        count = 1 if rule["type"] == "once" and errors else len(errors)
        c2_score -= (count * rule["penalty"])
    c2_score = max(0, c2_score)

    # C3
    c3_score = float(data["C3"].get("VOC", 1.0))

    total = c1_score + c2_score + c3_score
    if word_count < 80:
        total = total / 2
        
    return round(c1_score, 2), round(c2_score, 2), c3_score, round(total, 2)

def format_feedback(data, scores):
    c1_s, c2_s, c3_s, total = scores
    output = f"\n**Overall Impression:** {data['OVERALL']['IMP']}\n\n---\n"
    
    # Format C1
    output += f"###### **Adequació, coherència i cohesió (Score: {str(c1_s).replace('.', ',')}/4)**\n"
    for key, rule in GRADING_CONFIG["C1"]["rules"].items():
        errors = data["C1"].get(key, [])
        if errors:
            output += f"* **{rule['label']}:**\n"
            for e in errors:
                if isinstance(e, dict):
                    output += f"  - \"{e['q']}\": {e['r']}\n"
                else:
                    output += f"  - {e}\n"
                    
    # Format C2
    output += f"\n###### **Morfosintaxi i ortografia (Score: {str(c2_s).replace('.', ',')}/4)**\n"
    for key, rule in GRADING_CONFIG["C2"]["rules"].items():
        errors = data["C2"].get(key, [])
        if errors:
            output += f"* **{rule['label']}:**\n"
            for e in errors:
                output += f"  - \"{e['q']}\": {e['r']}\n" if isinstance(e, dict) else f"  - {e}\n"

    output += f"\n###### **Lèxic (Score: {str(c3_s).replace('.', ',')}/2)**\n"
    output += f"\n---\n###### **FINAL MARK: {str(total).replace('.', ',')}/10**"
    if total < 4.0: output += "\n\n⚠️ *Length penalty applied or significant errors found.*"
    return output

REVISION_COACH_PROMPT = """
### ROLE: REVISION CHECKER
- Compare the NEW VERSION against the PREVIOUS FEEDBACK.
- Use the original "NO ANSWERS" rule.
- Use the exact format for the following headers:
###### **✅ Fixed Errors**
* List every corrected error.
###### **⚠️ Remaining Errors**
* List every missed error.

"""

# 3. SESSION STATE
if 'essay_content' not in st.session_state:
    st.session_state.essay_content = ""
if 'fb1' not in st.session_state:
    st.session_state.fb1 = ""
if 'fb2' not in st.session_state:
    st.session_state.fb2 = ""
if 'raw_response' not in st.session_state:
    st.session_state.raw_response = ""

# 4. AI CONNECTION
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
        }
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
            
            # Remove Markdown code blocks if the AI included them
            clean_json = re.sub(r'^```json\s*|```$', '', raw_text, flags=re.MULTILINE).strip()
            return clean_json
        
        elif response.status_code == 429:
            return "The teacher is busy (Rate limit). Try again in 10 seconds."
            
        return f"An unexpected error occurred: {response.status_code}"
    
    except Exception as e:
        return f"Connection error: {str(e)}"

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
st.info(TASK_DESC)

essay = st.text_area("Write your composition below:", value=st.session_state.essay_content, height=500)
st.session_state.essay_content = essay
word_count = len(essay.split())
st.caption(f"Word count: {word_count}")

# --- 1. FIRST FEEDBACK BUTTON ---
if not st.session_state.fb1:
    if st.button("🔍 Get Feedback", use_container_width=True):
        if not s1 or not essay:
            st.error("Please enter your name and write your composition first.")
        elif word_count <= MIN_ESSAI_WORD_COUNT:
            # Handle the too-short case immediately
            fb = "Your composition is too short to be marked. FINAL MARK: 0/10"
            st.session_state.fb1 = fb
            requests.post(SHEET_URL, json={
                "type": "FIRST", "Group": group, "Students": student_list, "Mark": "0/10",
                "Draft 1": essay, "FB 1": fb, "Word Count": word_count
            })
            st.rerun()
        else:
            with st.spinner("Teacher is analyzing your text and computing the grade..."):
                formatted_points = "\n".join([f"- {p}" for p in REQUIRED_CONTENT_POINTS])
                full_prompt = f"{RUBRIC_INSTRUCTIONS}\n\nREQUIRED POINTS:\n{formatted_points}\n\nESSAY:\n{essay}"
                
                raw_response = call_gemini(full_prompt)
                st.session_state.raw_response = "" + raw_response
                
                # Logic to determine if we got valid JSON or an error message
                if raw_response.strip().startswith("{"):
                    try:
                        # 1. Clean and Load JSON
                        clean_json = re.sub(r'^```json\s*|```$', '', raw_response, flags=re.MULTILINE).strip()
                        data = json.loads(clean_json)
                        
                        # 2. Compute scores using Python logic
                        # scores returns: (c1_score, c2_score, c3_score, final_mark)
                        scores = compute_mark(data, word_count)
                        
                        # 3. Format the beautiful output for the student
                        st.session_state.fb1 = format_feedback(data, scores)
                        
                        # 4. Log to Google Sheets
                        requests.post(SHEET_URL, json={
                            "type": "FIRST", 
                            "Group": group, 
                            "Students": student_list, 
                            "Mark": f"{str(scores[3]).replace('.', ',')}/10", 
                            "Draft 1": essay,
                            "FB 1": st.session_state.fb1, 
                            "Word Count": word_count
                        })
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Linguistic Analysis Error: The AI response was not in the expected format.")
                        with st.expander("Debug Raw Response"):
                            st.code(raw_response)
                            st.write(f"Python Error: {e}")
                else:
                    # This handles the "Teacher is busy" or connection error strings
                    st.error(raw_response)

# --- 2. DISPLAY FIRST FEEDBACK ---
if st.session_state.fb1:
    st.markdown("---")
    st.markdown(f"""<div style="background-color: #e7f3ff; color: #1a4a7a; padding: 20px; border-radius: 12px; border: 1px solid #b3d7ff;">
            <h3>🔍 Detailed Feedback</h3>
            {st.session_state.fb1}</div><p></p>""", unsafe_allow_html=True)
    
    if DEBUG: 
        st.json(st.session_state.raw_response)

# --- 3. REVISION BUTTON ---
    if not st.session_state.fb2:
        if st.button("🚀 Submit Final Revision", use_container_width=True):
            with st.spinner("✨ Teacher is reviewing your changes..."):
                rev_prompt = f"{REVISION_COACH_PROMPT}\n\nORIGINAL FEEDBACK:\n{st.session_state.fb1}\n\nNEW VERSION:\n{essay}"
                fb2_response = call_gemini(rev_prompt)
                
                # FIX: Check if the response failed BEFORE saving it to state
                if "The teacher is busy" in fb2_response or "Connection error" in fb2_response:
                    st.error("The teacher is currently busy. Please click the button again in a few seconds.")
                else:
                    st.session_state.fb2 = fb2_response
                    
                    requests.post(SHEET_URL, json={
                        "type": "REVISION", "Group": group, "Students": student_list,
                        "Final Essay": essay, "FB 2": st.session_state.fb2, "Word Count": word_count
                    })
                    st.balloons()
                    st.rerun()

# --- 4. FINAL FEEDBACK ---
if st.session_state.fb2:
    st.markdown(f"""<div style="background-color: #d4edda; color: #155724; padding: 20px; border-radius: 12px; border: 1px solid #c3e6cb; margin-top: 20px;">
            <h3>✅ Revision Check</h3>
            {st.session_state.fb2}</div>""", unsafe_allow_html=True)
