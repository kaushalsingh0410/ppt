import streamlit as st
from datetime import datetime
import requests
import os
import json
from dotenv import load_dotenv
from streamlit_logger import setup_streamlit_logger
logger = setup_streamlit_logger()

load_dotenv()
API_URL = os.getenv('API_URL')

# Page config
st.set_page_config(page_title="Ritey PPT", layout="wide")
# logger.info("Streamlit App Started")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "show_form" not in st.session_state:
    st.session_state.show_form = False
if "topic" not in st.session_state:
    st.session_state.topic = False
if "num_slide" not in st.session_state:
    st.session_state.num_slide = False
if "state" not in st.session_state:
    st.session_state.state = False
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0




# ============ API Function ===============
def get_session_from_backend():
    """Fetch all session or state or thread form backen checkpointer"""
    try:
        response = requests.get(f'{API_URL}/threads/')
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error('This is get_session_from_backend %s',e)
        return []
    
def get_session_state(thread_id):
    try:
        response = requests.get(f'{API_URL}/threads/{thread_id}')
        if response.status_code == 200:
            data = response.json()

            return data
    except Exception as e:
        logger.error('get_session_state error %s',e)
        return None


# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("### Activity")
    
    # New PPT Button
    if st.button("New PPT", use_container_width=True, key="new_ppt_btn"):
        st.session_state.show_form = True
    
    st.divider()
    
    # Display existing sessions
    sessions = get_session_from_backend()
    if sessions:
        st.markdown("**Recent Sessions**")
        for idx, session in enumerate(sessions):
            if st.button(
                f" {session['topic'][:30].capitalize()}...",
                key=f"session_{idx}",
                use_container_width=True,
            ):
                st.session_state.thread_id = session['thread_id']
                st.session_state.show_form = False
                st.session_state.topic = session['topic'] 
                st.session_state.num_slide = False
                st.rerun()
            
    else:
        st.info("📭 No sessions yet. Create your first PPT!")

# ============ MAIN CONTENT ============

# Show form when "New PPT" clicked
if st.session_state.show_form:
    st.title(" Create New Presentation")
    
    with st.form("ppt_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            topic = st.text_input(
                "📝 Presentation Topic",
                placeholder="e.g., Introduction to AI, Climate Change...",
                help="What should your presentation be about?"
            )
        
        with col2:
            num_slides = st.number_input(
                "🔢 Number of Slides",
                step=1,
                help="How many slides do you want?"
            )
        
        submitted = st.form_submit_button("✅ Create Presentation", use_container_width=True)
        if submitted:
            if not topic.strip():
                st.error("⚠️ Please enter a presentation topic.")
                st.stop()
            if num_slides > 5:
                st.error("⚠️ This app uses a free API, so you can generate a maximum of 5 slides only.")
                st.stop()
            
            if num_slides < 3:
                st.error("⚠️ Please select at least 3 slide.")
                st.stop()

            thread = requests.post(f'{API_URL}/threads/',json={"topic":topic,"num_slide":num_slides})
            thread = thread.json()
            thread_id = thread['thread_id']
            st.session_state.thread_id = thread_id
            st.session_state.topic = topic
            st.session_state.num_slide = num_slides
            st.session_state.show_form = False
            st.session_state.active_tab = 0
            st.success(f"✨ Session created! Thread ID: `{thread_id}`")
            st.info(f"📋 Topic: **{topic}** | Slides: **{num_slides}**")
            st.rerun()

# Show current session
elif st.session_state.thread_id is not None:

    if st.session_state.topic and st.session_state.num_slide:
        state = {
            "topic": st.session_state.topic,
            "num_slide": st.session_state.num_slide,
            "thread_id": st.session_state.thread_id,
                }
        state = requests.post(f'{API_URL}/states/',json=state)
        st.session_state.num_slide = False
        st.session_state.topic = False
        state = state.json()
        st.session_state.state = state
        
    # st.subheader(st.session_state.topic)
    session = get_session_state(st.session_state.thread_id)

    # kaushal 
    if session:

        topic = (session.get('thread')or {'topic':'No Title'}).get('topic','No Title')
        
        
        st.title(f"🎯 {topic}")
        
        st.subheader("Presentation Outline")
        if session['outline']:
            st.json(session['outline'])

            if session['detailed_slides']:
                st.subheader("Slide Details")
                for idx, slide in enumerate(session['detailed_slides']):
                    with st.expander(f"Slide {idx + 1}: {slide.get('slide_title', 'Untitled')}"):
                        st.write(slide)
                
                st.subheader("Download Presentation")
                st.download_button(
                        label="⬇️ Click here to Download PPT",
                        data=requests.post(f'{API_URL}/ppt/', json={"thread_id": st.session_state.thread_id}).content,
                        file_name=session['thread']['topic']+'.pptx',
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
            else:
                if st.button('Continue to slide'):
                    with st.spinner('Generating slides... Please wait ⏳'):
                        state = {"action":"continue_slide","thread_id":st.session_state.thread_id}
                        response = requests.post(f'{API_URL}/states/',json=state)
                        if response.status_code == 429:
                            error_detail = response.json().get('detail', {})
                            wait_time = error_detail.get('wait_time', 'some time')
                            st.error(f"⚠️ Groq daily token limit reached!")
                            st.warning(f"⏳ Please try again in **{wait_time}** or next 24 hours..")
                        else:
                            st.rerun()
                        
    else:
        st.subheader(f'No Presentation found for {st.session_state.topic}.')            
else:
    # Welcome screen
    st.title("Welcome to Ritey PPT")
    st.subheader('Build Easy, Build Fast, Build Smart')
    
    st.markdown("""
    ### 🚀 Get Started
    
    Click **"✨ New PPT"** in the sidebar to:
    1. Enter your presentation topic
    2. Choose number of slides
    3. Start building your presentation!
    
    ---
    
    ### ✨ Features
    - 🤖 **AI-Powered Outlines**: Automatic content generation
    - ✏️ **Interactive Editing**: Review and revise each slide
    - 📊 **Smart Formatting**: Beautiful slide layouts
    - 💾 **Session Persistence**: Your work is always saved
    
    ---
    
    ### 📖 How It Works
    1. **Create** → Describe your topic
    2. **Review** → Check AI-generated outline
    3. **Refine** → Provide feedback on slides
    4. **Download** → Get your PPT file
    """)
    
    # Example cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("📌 **Business**\nCreate pitches & reports")
    with col2:
        st.info("🎓 **Education**\nBuild lesson slides")
    with col3:
        st.info("🎨 **Creative**\nDesign portfolios")
