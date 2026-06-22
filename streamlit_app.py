# filepath: streamlit_app.py
import asyncio
import streamlit as st
from app.workflows.master_pipeline import nexus_engine
from app.ingestion.parser_utils import pdf_extractor

st.set_page_config(
    page_title="NexusMind — Nexa Cognitive Assistant", 
    page_icon="🧠", 
    layout="wide"
)

st.title("🧠 NexusMind Engine — Nexa v2.5")
st.caption("Enterprise GraphRAG RAG Pipeline Interface (Google ADK 2.0 & pypdf)")

# Initialize memory stores
if "messages" not in st.session_state:
    st.session_state.messages = []
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

# --- NEW SIDEBAR ATTACHMENT: PDF UPLOADER CONTROL ---
with st.sidebar:
    st.header("📁 Data Ingestion Console")
    st.write("Load raw PDF documents into Chroma and Neo4j databases concurrently.")
    
    uploaded_pdf = st.file_uploader("Select Target PDF Document", type=["pdf"])
    
    if uploaded_pdf is not None:
        if st.button("🚀 Execute Ingestion Pipeline"):
            with st.spinner("Parsing document layouts and running multi-agent indexing..."):
                try:
                    # 1. Extract bytes and parse using utility
                    raw_bytes = uploaded_pdf.getvalue()
                    parsed_text_dump = pdf_extractor.extract_clean_text(raw_bytes)
                    
                    # 2. Package text context and issue transaction directly into the pipeline
                    pipeline_payload = asyncio.run(
                        nexus_engine.process_transaction(
                            user_query=f"DOCUMENT_INJECT_STREAM:\nFilename: {uploaded_pdf.name}\nContent:\n{parsed_text_dump}",
                            history=[]
                        )
                    )
                    
                    st.success("✅ Ingestion Completed Successfully!")
                    st.markdown(pipeline_payload.get("markdown_answer"))
                    
                except Exception as ex:
                    st.error(f"❌ Ingestion pipeline failed: {str(ex)}")

# Render standard messaging log tables
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Render follow-up pills
if st.session_state.suggestions:
    st.write("✨ **Nexa suggests exploring further:**")
    cols = st.columns(len(st.session_state.suggestions))
    for idx, question in enumerate(st.session_state.suggestions):
        if cols[idx].button(question, key=f"sug_pill_{idx}"):
            st.session_state.messages.append({"role": "user", "content": question})
            st.session_state.suggestions = []
            st.rerun()

# Accept standard text inputs
if user_input := st.chat_input("Ask Nexa a question or analyze infrastructure vectors..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    with st.chat_message("assistant"):
        with st.spinner("🧠 Orchestrating ADK Topologies..."):
            try:
                pipeline_payload = asyncio.run(
                    nexus_engine.process_transaction(
                        user_query=user_input,
                        history=st.session_state.messages[:-1]
                    )
                )
                
                answer = pipeline_payload.get("markdown_answer")
                st.markdown(answer)
                
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.session_state.suggestions = pipeline_payload.get("dynamic_followups", [])
                st.rerun()
                
            except Exception as ex:
                st.error(f"❌ Core runtime error: {str(ex)}")