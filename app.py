import streamlit as st
import google.generativeai as genai
import requests

# 1. SETUP API KEYS FROM STREAMLIT SECRETS
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]
    genai.configure(api_key=API_KEY)
    
    # We use 'gemini-1.5-flash' as the primary, but 'gemini-pro' as a backup
    # If gemini-1.5-flash gives a 'NotFound', try 'gemini-2.0-flash' or 'gemini-pro'
    model = genai.GenerativeModel('gemini-1.5-flash') 
except Exception as e:
    st.error(f"Setup Error: {e}")
    st.stop()

# 2. INITIALIZE SESSION STATE
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'original_essay' not in st.session_state:
    st.session_state.original_essay = ""

# 3. TEACHER CONFIGURATION
ASSIGNMENT_NAME = "Email to Liam (End of Year Trip)"
TASK_INSTRUCTIONS = """
Write an email to Liam (80-100 words), your exchange partner. 
Tell him about your end of year trip plans: places to visit, 
activities, and about your classmates, friends and family.
"""

SYSTEM_PROMPT = f"""
You are a strict but encouraging British English teacher grading at B2 CEFR level.
TASK: {TASK_INSTRUCTIONS}

RUBRIC RULES:
1. Criterion 1 (Adequació): Start 4.0. Deduct for length (<80 words = total grade / 2), genre (-1.0), register (-0.5), structure (-1.0), missing info (-0.5 per item), connectors (-1.0 if <5 total or <3 different), punctuation (-0.5 to -1.5).
2. Criterion 2 (Morfosintaxi): Start 4.0. Deduct 0.4 for: verb tense, 'to be', 'to have', subject-verb agreement. Deduct 0.3 for: spelling, prepositions. Deduct 0.1 for collocations. Deduct 0.5 for small 'i'. Deduct 0.5 if no complex sentences.
3. Criterion 3 (Lèxic): Score only 0, 1, or 2.

OUTPUT FORMAT:
- Criterion 1: [Score] + Short comment.
- Criterion 2: [Score] + List of mistakes (Explanations only, NO corrections).
- Criterion 3: [Score] + Short comment.
- FINAL MARK: [Total/10]
- Encouraging closing sentence.
Tone: Strict, straightforward, simple, encouraging.
"""

# 4. USER INTERFACE
st.set_page_config(page_title="Writing Portal", layout="centered")
st.title("📝 Student Writing Portal")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Select Group", ["3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1 Name & Surname")
    s2 = st.text_input("Student 2 (Optional)")
    s3 = st.text_input("Student 3 (Optional)")
    s4 = st.text_input("Student 4 (Optional)")
    student_list = ", ".join(filter(None, [s1, s2, s3, s4]))

st.info(f"**Task:** {ASSIGNMENT_NAME}\n\n{TASK_INSTRUCTIONS}")

# 5. SUBMISSION LOGIC
if not st.session_state.submitted:
    essay = st.text_area("Type your essay here...", height=350, key="draft1")
    
    if st.button("Submit First Draft for Grade"):
        if not s1 or not essay:
            st.error("Please provide at least one name and your essay.")
        else:
            with st.spinner("Teacher AI is grading..."):
                response = model.generate_content([SYSTEM_PROMPT, f"FIRST DRAFT SUBMISSION: {essay}"])
                feedback_text = response.text
                
                mark = "N/A"
                if "FINAL MARK:" in feedback_text:
                    mark = feedback_text.split("FINAL MARK:")[1].split("\n")[0].strip()

                try:
                    requests.post(SHEET_URL, json={
                        "type": "FIRST_DRAFT",
                        "group": group, 
                        "students": student_list, 
                        "assignment": ASSIGNMENT_NAME,
                        "grade": mark, 
                        "feedback": feedback_text, 
                        "essay": essay
                    })
                    st.session_state.original_essay = essay
                    st.session_state.submitted = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Error connecting to Google Sheets: {e}")

else:
    # This part shows AFTER the first submission
    st.success("First draft submitted. Scroll down to see feedback and revise.")
    
    # We put the feedback in an expander so it doesn't take up too much space
    with st.expander("View First Draft Feedback", expanded=True):
        # We need to re-generate or store the feedback. 
        # For simplicity in this free version, we ask the AI to re-summarize or show the status.
        st.info("Please use the feedback provided in the previous step to improve your text.")

    revised_essay = st.text_area("Write your IMPROVED composition here:", value=st.session_state.original_essay, height=350, key="draft2")
    
    if st.button("Submit Final Revision"):
        with st.spinner("Reviewing improvements..."):
            rev_prompt = f"{SYSTEM_PROMPT}\n\nSUBMISSION: FINAL REVISION. Feedback on improvements only. No grade."
            response = model.generate_content([rev_prompt, revised_essay])
            final_feedback = response.text
            
            try:
                requests.post(SHEET_URL, json={
                    "type": "REVISION",
                    "group": group, 
                    "students": student_list, 
                    "feedback": final_feedback, 
                    "essay": revised_essay 
                })
                st.subheader("Final Feedback on Revision")
                st.markdown(final_feedback)
                st.balloons()
            except Exception as e:
                st.error(f"Error updating Sheet: {e}")
