# filepath: streamlit_app.py
import asyncio
from pathlib import Path
import streamlit as st
from app.backend_engine import execute_nexus_engine, process_file_ingestion

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

st.set_page_config(
    page_title="NexusMind — Nexa Cognitive Assistant", 
    page_icon="🧠", 
    layout="wide"
)

st.title("🧠 NexusMind Engine — Nexa")
st.caption("Enterprise GraphRAG RAG Pipeline Interface (Google ADK Framework)")

# Initialize pure UI memory stores
if "messages" not in st.session_state:
    st.session_state.messages = []
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

# --- SIDEBAR ATTACHMENT: SEPARATED DIRECT FILE INGESTION ---
with st.sidebar:
    st.header("📁 Data Ingestion Console")
    st.write("Load raw PDF documents into Chroma and Neo4j databases concurrently.")
    uploaded_pdf = st.file_uploader("Select Target PDF Document", type=["pdf"])
    
    if uploaded_pdf is not None and st.button("🚀 Execute Ingestion Pipeline"):
        with st.spinner("Staging asset locally and executing isolated indexing workflow..."):
            try:
                # 1. Enforce local root data folder persistence constraints
                data_dir = Path("data")
                data_dir.mkdir(exist_ok=True)
                saved_path = data_dir / uploaded_pdf.name
                
                # Write the binary straight to disk
                with open(saved_path, "wb") as f:
                    f.write(uploaded_pdf.getbuffer())
                
                # 2. Fire direct batch processing out of the file's landing spot
                report_output = asyncio.run(process_file_ingestion(uploaded_pdf.name))
                
                st.success(f"✅ Ingested {uploaded_pdf.name} successfully!")
                st.markdown(report_output)
                st.session_state.suggestions = ["Check database structural logs", "Query the uploaded content metrics"]
            except Exception as ex:
                st.error(f"❌ Ingestion pipeline failed: {str(ex)}")

# Render standard messaging log tables
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask Nexa a question or analyze infrastructure vectors...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    with st.chat_message("assistant"):
        with st.spinner("🧠 Nexa is thinking..."):
            try:
                # Execute the conversational orchestration route cleanly
                answer = asyncio.run(execute_nexus_engine(
                    user_id="default_user",
                    session_id="active_chat_session",
                    raw_input=user_input
                ))
                
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.session_state.suggestions = ["Analyze matching vector entities", "View Neo4j operational paths"]
                st.rerun()
            except Exception as ex:
                st.error(f"❌ Core runtime error: {str(ex)}")