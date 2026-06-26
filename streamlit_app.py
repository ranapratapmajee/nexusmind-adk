# filepath: streamlit_app.py
import asyncio
from pathlib import Path
import streamlit as st
from google.genai import types
from google.adk.runners import InMemoryRunner
from app.agent import root_agent

import warnings

warnings.filterwarnings("ignore", message="Task was destroyed but it is pending!")
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

# 1. PAGE CONFIGURATION & THEME PRESETS
st.set_page_config(
    page_title="NexusMind Workspace — Nexa AI", 
    page_icon="🧠", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. INJECT ASYMMETRIC PURE-BUBBLE STYLES (Light High-Contrast Workspace Theme)
st.markdown(
    """
    <style>
    /* Force layout components to utilize full viewport real estate smoothly */
    div[data-testid="stMainBlockContainer"] {
        max-width: 100% !important;
        padding-top: 2rem !important;
        padding-left: 3rem !important;
        padding-right: 3rem !important;
        background-color: #F8FAFC !important; /* Premium clean off-white workspace background */
    }
    
    /* Completely hide Streamlit's default background chat wrapper borders and paddings */
    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin-bottom: 0 !important;
        max-width: 100% !important;
    }
    
    /* Remove default avatar and structural row constraints to prevent alignment locking */
    div[data-testid="stChatMessage"] > div {
        display: block !important;
        padding: 0 !important;
    }

    /* 🟢 USER BUBBLE CUSTOM WRAPPER (Sleek Slate Indigo Accent) */
    .user-bubble {
        background: #6366F1 !important;
        color: #FFFFFF !important;
        padding: 14px 20px !important;
        border-radius: 20px 20px 4px 20px !important;
        max-width: 75% !important;
        font-size: 15px !important;
        float: right !important;
        clear: both !important;
        margin-bottom: 18px !important;
        box-shadow: 0 4px 10px rgba(99, 102, 241, 0.12) !important;
    }

    /* 🔵 ASSISTANT BUBBLE CUSTOM WRAPPER (Premium High-Contrast Light Card Panel) */
    .assistant-bubble {
        background: #FFFFFF !important; /* Clean solid canvas background blocks any bleeding */
        color: #0F172A !important; /* High contrast crisp slate black text for complete visibility */
        padding: 20px 24px !important;
        border-radius: 20px 20px 20px 4px !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
        border-left: 5px solid #4F46E5 !important; /* Deep Nexa accent identity border */
        float: left !important;
        clear: both !important;
        width: 100% !important; /* Let long outputs scale naturally over the wide layout grid */
        margin-bottom: 20px !important;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04) !important;
    }
    
    /* Internal typography overrides ensuring clean presentation layouts inside custom layouts */
    .assistant-bubble p { margin-bottom: 12px !important; color: #0F172A !important; }
    .assistant-bubble ul, .assistant-bubble ol { margin-left: 20px !important; margin-bottom: 12px !important; color: #0F172A !important; }
    .assistant-bubble li { margin-bottom: 6px !important; }
    .assistant-bubble h1, .assistant-bubble h2, .assistant-bubble h3 { color: #0F172A !important; margin-top: 16px !important; margin-bottom: 10px !important; font-weight: 600 !important; }
    .user-bubble p { margin: 0 !important; padding: 0 !important; color: inherit !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- NATIVE ADK PERSISTENT RUNNER INITIALIZATION (CACHED) ---
@st.cache_resource
def get_nexus_runners():
    """Initializes and holds single instance runners directly inside the UI context."""
    chat_runner = InMemoryRunner(agent=root_agent, app_name="app")
    if hasattr(chat_runner, "auto_create_session"):
        chat_runner.auto_create_session = True
    return chat_runner

chat_runner = get_nexus_runners()

def run_async_task(coro):
    """Executes async routines securely inside Streamlit's runtime thread pool."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# Initialize pure UI memory stores
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- SIDEBAR ATTACHMENT: BRANDED INTERACTION MANAGEMENT ---
with st.sidebar:
    st.title("🧠 NexusMind")
    st.caption("Enterprise Cognitive Workspace — Core v1.0")
    st.markdown("---")
    st.subheader("🪐 Agent Status")
    st.success("🤖 Nexa Core Active")
    st.info("🔗 Gateway Connected")
    
    if st.button("🧹 Reset Active Session", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# --- CENTER CANVAS ALIGNMENT GRID CONTAINER ---
_, center_canvas, _ = st.columns([0.5, 7.0, 0.5])

with center_canvas:
    # Render Centered Clean Hero Workspace Header if message stream history is pristine
    if not st.session_state.messages:
        st.markdown(
            """
            <div style="text-align: center; margin-top: 12vh; margin-bottom: 6vh; clear: both;">
                <div style="font-family: monospace; font-size: 0.85rem; color: #4F46E5; font-weight: 600; letter-spacing: 1.5px; margin-bottom: 8px;">NEXUSMIND // INTELLIGENCE SYSTEM</div>
                <div style="font-size: 2.5rem; font-weight: 700; letter-spacing: -0.5px; color: #0F172A;">Meet Nexa, Your Cognitive Assistant.</div>
                <div style="font-size: 1.0rem; color: #334155; max-width: 600px; margin: 12px auto 0 auto; line-height: 1.5; opacity: 0.8;">
                    A high-density engineering workspace optimized for source-grounded exploration, adaptive GraphRAG execution, and clean topological routing.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Render history logs using custom classes inside native clean text blocks
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"<div class='user-bubble'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='assistant-bubble'>{msg['content']}</div>", unsafe_allow_html=True)

# --- FLOATING MACRO COMPOSER CONTROL INPUT BOTTOM BAR ---
user_input = st.chat_input("Message Nexa or submit system orchestration queries...")

if user_input:
    clean_input = user_input.strip()
    if clean_input:
        # Append and render user turn inside center layout grid tracking scope immediately
        st.session_state.messages.append({"role": "user", "content": clean_input})
        with center_canvas:
            st.markdown(f"<div class='user-bubble'>{clean_input}</div>", unsafe_allow_html=True)
                
            with st.chat_message("assistant"):
                with st.spinner("🧠 Nexa is generating response..."):
                    try:
                        # 1. Trigger the asynchronous stream payload from your gateway runner
                        outcome_stream = chat_runner.run_async(
                            user_id="default_user",
                            session_id="active_chat_session",
                            new_message=types.Content(
                                role="user",
                                parts=[types.Part.from_text(text=clean_input)]
                            )
                        )
                        
                        # 2. Define a clean async accumulator that FILTERS out router leaking noise
                        async def stream_accumulator():
                            text_pieces = []
                            async for event in outcome_stream:
                                author = getattr(event, "author", "").strip()
                                
                                if author in ["FastConversationalAgent", "ResearchAgent"]:
                                    if hasattr(event, "text") and event.text:
                                        text_pieces.append(event.text)
                                    elif hasattr(event, "content") and hasattr(event.content, "parts"):
                                        for part in event.content.parts:
                                            if hasattr(part, "text") and part.text:
                                                text_pieces.append(part.text)
                                                
                                elif not author:
                                    raw_text = ""
                                    if hasattr(event, "text") and event.text:
                                        raw_text = event.text
                                    elif hasattr(event, "content") and hasattr(event.content, "parts"):
                                        raw_text = "".join([p.text for p in event.content.parts if hasattr(p, "text") and p.text])
                                    
                                    if raw_text and not any(t in raw_text.upper() for t in ["CASUAL_CHAT", "RESEARCH"]):
                                        text_pieces.append(raw_text)
                                        
                            return "".join(text_pieces)
                        
                        # 3. Resolve the filtered stream data safely within the runtime thread pool
                        answer_string = run_async_task(stream_accumulator())
                        answer = answer_string.strip() if answer_string else "No response generated by the cognitive topology."
                        
                        # DEFENSIVE CLEANUP LOGIC: Strip out raw prompt echoes or control artifacts if leaked by intermediate ADK nodes
                        if answer.startswith(clean_input):
                            answer = answer.replace(clean_input, "", 1).strip().strip("`json").strip("`").strip()
                        
                        # Render final clean response utilizing the premium assistant-bubble markup styles
                        st.markdown(f"<div class='assistant-bubble'>{answer}</div>", unsafe_allow_html=True)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        st.rerun()
                        
                    except Exception as ex:
                        st.error(f"❌ Core runtime error: {str(ex)}")