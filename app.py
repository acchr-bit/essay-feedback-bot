import streamlit as st
import google.generativeai as genai
import requests

# 1. SETUP WITH COMPATIBILITY FIX
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]
    
    # Force the use of gemini-pro for maximum compatibility
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-pro') 
except Exception as e:
    st.error(f"Setup Error: {e}")
    st.stop()

# 2. SESSION STATE
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'original_essay' not in st.session_state:
    st.session_state.original_essay = ""
if 'first_feedback' not in st.session_state:
    st.session_state.first_feedback = ""

# 3. TEACHER CONFIG
ASSIGNMENT_NAME = "Email to Liam (End of Year Trip)"
TASK_INSTRUCTIONS = """Write an email to Liam (80-100 words). Tell him about your end of year trip plans: places to visit, activities, classmates, friends and family."""

SYSTEM_PROMPT = f"""You are a strict but encouraging British English teacher.
TASK: {TASK_INSTRUCTIONS}
Provide feedback on Adequacy, Morphosyntax, and Lexis. 
Include 'FINAL MARK: X/10' at the end."""

# 4. USER INTERFACE (With 4 names)
st.set_page_config(page_title="Writing Portal", layout="centered")
st.title("📝 Student Writing Portal")

with st.sidebar:
    st.header("Student Info")
    group = st.selectbox("Select Group", ["3A", "3C", "4A", "4B", "4C"])
    s1 = st.text_input("Student 1 Name")
    s2 = st.text_input("Student 2 (Optional)")
    s3 = st.text_input("Student 3 (Optional)")
    s4 = st.text_input("Student 4 (Optional)")
    student_list = ", ".join(filter(None, [s1, s2, s3, s4]))

st.info(f"**Task:** {ASSIGNMENT_NAME}\n\n{TASK_INSTRUCTIONS}")

# 5. LOGIC
if not st.session_state.submitted:
    essay = st.text_area("Type your essay here...", height=350, key="draft1")
    
    if st.button("Submit First Draft"):
        if not s1 or not essay:
            st.error("Please provide a name and your essay.")
        else:
            with st.spinner("AI Teacher is marking..."):
                try:
                    # Combined the prompt and essay into one string for simpler API handling
                    full_query = f"{SYSTEM_PROMPT}\n\nSTUDENT ESSAY:\n{essay}"
                    response = model.generate_content(full_query)
                    
                    if response.text:
                        fb = response.text
                        mark = fb.split("FINAL MARK:")[1].split("\n")[0].strip() if "FINAL MARK:" in fb else "N/A"
                        
                        requests.post(SHEET_URL, json={
                            "type": "FIRST_DRAFT", "group": group, "students": student_list,
                            "assignment": ASSIGNMENT_NAME, "grade": mark, "feedback": fb, "essay": essay
                        })
                        
                        st.session_state.first_feedback = fb
                        st.session_state.original_essay = essay
                        st.session_state.submitted = True
                        st.rerun()
                except Exception as e:
                    st.error(f"API Error: {e}. Try refreshing the page.")

else:
    st.success("First draft submitted!")
    with st.expander("View Feedback", expanded=True):
        st.markdown(st.session_state.first_feedback)
    
    revised = st.text_area("Write your IMPROVED composition here:", value=st.session_state.original_essay, height=350)
    
    if st.button("Submit Final Revision"):
        with st.spinner("Reviewing..."):
            try:
                rev_query = f"Compare this revision to the original and comment on improvements. No mark.\n\nREVISION:\n{revised}"
                res = model.generate_content(rev_query)
                
                requests.post(SHEET_URL, json={
                    "type": "REVISION", "group": group, "students": student_list,
                    "feedback": res.text, "essay": revised
                })
                st.markdown(res.text)
                st.balloons()
            except Exception as e:
                st.error(f"Error: {e}")
