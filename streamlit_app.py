# filepath: streamlit_app.py
import asyncio
from pathlib import Path
import streamlit as st
from google.genai import types

# Native framework runners & custom workflow engines
from google.adk.runners import InMemoryRunner
from app.root_gateway import root_agent
from app.ingest_pipeline import ingest_flow_engine
from app.infrastructure import pdf_extractor

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

# 1. PAGE CONFIGURATION & THEME PRESETS
st.set_page_config(
    page_title="NexusMind — Nexa Cognitive Assistant", 
    page_icon="🧠", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. INJECT ASYMMETRIC PURE-BUBBLE STYLES (High-Contrast Theme for Visibility)
st.markdown(
    """
    <style>
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

    /* 🟢 USER BUBBLE CUSTOM WRAPPER (Right-Aligned Indigo) */
    .user-bubble {
        background: #6366F1 !important;
        color: #FFFFFF !important;
        padding: 12px 18px !important;
        border-radius: 18px 18px 2px 18px !important;
        max-width: 70% !important;
        font-size: 15px !important;
        float: right !important;
        clear: both !important;
        margin-bottom: 18px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
    }

    /* 🔵 ASSISTANT BUBBLE CUSTOM WRAPPER (Dark Slate Background for Complete Visibility) */
    .assistant-bubble {
        background: #1E293B !important; /* Premium Dark Slate background blocks light background bleeding */
        color: #FFFFFF !important; /* Forces high-contrast crisp white text */
        padding: 14px 20px !important;
        border-radius: 18px 18px 18px 2px !important;
        font-size: 15px !important;
        line-height: 1.5 !important;
        border-left: 4px solid #4F46E5 !important; /* Deep accent indicator border */
        float: left !important;
        clear: both !important;
        margin-bottom: 18px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.08) !important;
    }
    
    /* Global layout reset for markdown contents inside custom floats */
    .user-bubble p, .assistant-bubble p {
        margin: 0 !important;
        padding: 0 !important;
        color: inherit !important;
    }
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

# --- SIDEBAR ATTACHMENT: DIRECT FILE INGESTION VIA WORKING WRAPPER ---
with st.sidebar:
    st.header("📁 Data Ingestion Console")
    st.write("Load raw PDF documents into Chroma and Neo4j databases concurrently.")
    uploaded_pdf = st.file_uploader("Select Target PDF Document", type=["pdf"])
    
    if uploaded_pdf is not None and st.button("🚀 Execute Ingestion Pipeline"):
        with st.spinner("Staging asset locally and executing isolated indexing workflow..."):
            try:
                data_dir = Path("data")
                data_dir.mkdir(exist_ok=True)
                saved_path = data_dir / uploaded_pdf.name
                
                with open(saved_path, "wb") as f:
                    f.write(uploaded_pdf.getbuffer())
                
                with open(saved_path, "rb") as f:
                    raw_bytes = f.read()
                parsed_text_dump = pdf_extractor.extract_clean_text(raw_bytes)
                
                report_output = run_async_task(ingest_flow_engine.ingest_pdf_document(
                    file_content_stream=parsed_text_dump, 
                    filename=uploaded_pdf.name
                ))
                
                st.success(f"✅ Ingested {uploaded_pdf.name} successfully!")
                st.markdown(report_output.get("markdown_answer", "Pipeline executed successfully."))
            except Exception as ex:
                st.error(f"❌ Ingestion pipeline failed: {str(ex)}")

# --- CENTER CANVAS ALIGNMENT GRID CONTAINER ---
_, center_canvas, _ = st.columns([1.2, 5.0, 1.2])

with center_canvas:
    # Render Centered Clean Hero Workspace Header if message stream history is pristine
    if not st.session_state.messages:
        st.markdown(
            """
            <div style="text-align: center; margin-top: 8vh; margin-bottom: 4vh; clear: both;">
                <div style="font-family: monospace; font-size: 0.85rem; color: #6366F1; font-weight: 600; letter-spacing: 1px; margin-bottom: 4px;">NEXUS // CORE</div>
                <div style="font-size: 2.0rem; font-weight: 700; letter-spacing: -0.5px;">Ask anything. Research deeply.</div>
                <div style="font-size: 0.9rem; opacity: 0.6; max-width: 540px; margin: 8px auto 0 auto; line-height: 1.4;">
                    A high-density engineering workspace for source-grounded exploration, GraphRAG processing, and token-clean chat interactions.
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
user_input = st.chat_input("Ask Nexa a question or analyze infrastructure vectors...")

if user_input:
    clean_input = user_input.strip()
    if clean_input:
        # Append and render user turn inside center layout grid tracking scope immediately
        st.session_state.messages.append({"role": "user", "content": clean_input})
        with center_canvas:
            st.markdown(f"<div class='user-bubble'>{clean_input}</div>", unsafe_allow_html=True)
                
            with st.chat_message("assistant"):
                with st.spinner("🧠 Nexa is thinking..."):
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
                                
                                if author in ["FastConversationalAgent", "ResponseAgent"]:
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
                        
                        # Render final clean response utilizing the premium assistant-bubble markup styles
                        st.markdown(f"<div class='assistant-bubble'>{answer}</div>", unsafe_allow_html=True)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        st.rerun()
                        
                    except Exception as ex:
                        st.error(f"❌ Core runtime error: {str(ex)}")