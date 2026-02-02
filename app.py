import streamlit as st
import google.generativeai as genai
import requests

# 1. SETUP WITH AUTO-MODEL DETECTION
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_URL = st.secrets["GOOGLE_SHEET_URL"]
    genai.configure(api_key=API_KEY)

    # We try a list of possible model names from most modern to most basic
    available_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    model = None
    
    # This loop finds which model your key actually supports
    for model_name in available_models:
        try:
            temp_model = genai.GenerativeModel(model_name)
            # A quick test call to see if it 404s
            temp_model.generate_content("test", generation_config={"max_output_tokens": 1})
            model = temp_model
            break # Found one!
        except:
            continue
            
    if model is None:
        st.error("Could not connect to any Gemini models. Please check if your API key is restricted.")
        st.stop()
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
TASK_INSTRUCTIONS = "Write an email to Liam (80-100 words). Tell him about your end of year trip plans: places to visit, activities, classmates, friends and family."
SYSTEM_PROMPT = f"You are a British English teacher. Task: {TASK_INSTRUCTIONS}. Provide feedback and end with 'FINAL MARK: X/10'."

# 4. USER INTERFACE
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
                    response = model.generate_content(f"{SYSTEM_PROMPT}\n\nESSAY:\n{essay}")
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
                    st.error(f"Submission Error: {e}")
else:
    st.success("First draft submitted!")
    with st.expander("View Feedback", expanded=True):
        st.markdown(st.session_state.first_feedback)
    revised = st.text_area("Write your IMPROVED composition here:", value=st.session_state.original_essay, height=350)
    if st.button("Submit Final Revision"):
        with st.spinner("Reviewing..."):
            try:
                res = model.generate_content(f"Feedback on improvements:\n{revised}")
                requests.post(SHEET_URL, json={
                    "type": "REVISION", "group": group, "students": student_list,
                    "feedback": res.text, "essay": revised
                })
                st.markdown(res.text)
                st.balloons()
            except Exception as e:
                st.error(f"Error: {e}")
