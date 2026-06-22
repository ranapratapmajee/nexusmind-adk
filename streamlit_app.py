# filepath: streamlit_app.py
import asyncio
import streamlit as st
from app.backend_engine import execute_nexus_engine
from app.infrastructure import pdf_extractor

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

# --- SIDEBAR ATTACHMENT: PDF UPLOADER CONTROL ---
with st.sidebar:
    st.header("📁 Data Ingestion Console")
    st.write("Load raw PDF documents into Chroma and Neo4j databases concurrently.")
    uploaded_pdf = st.file_uploader("Select Target PDF Document", type=["pdf"])
    
    if uploaded_pdf is not None and st.button("🚀 Execute Ingestion Pipeline"):
        with st.spinner("Parsing document layouts and running multi-agent indexing..."):
            try:
                raw_bytes = uploaded_pdf.getvalue()
                parsed_text_dump = pdf_extractor.extract_clean_text(raw_bytes)
                payload_string = f"DOCUMENT_INJECT_STREAM:\nFilename: {uploaded_pdf.name}\nContent:\n{parsed_text_dump}"
                
                # Simple stateless backend execution call
                report_output = asyncio.run(execute_nexus_engine(
                    user_id="nexus_admin",
                    session_id="static_ingest_session",
                    raw_input=payload_string
                ))
                
                st.success("✅ Ingestion Completed Successfully!")
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
                # Let the backend automatically evaluate conversations using the ADK context
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