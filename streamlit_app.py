# filepath: streamlit_app.py
import asyncio
import streamlit as st
from google.adk.runners import InMemoryRunner

# --- TARGET NATIVE ENTRY GATEWAY ---
from app.root_gateway import root_agent
from app.infrastructure import pdf_extractor

st.set_page_config(
    page_title="NexusMind — Nexa Cognitive Assistant", 
    page_icon="🧠", 
    layout="wide"
)

st.title("🧠 NexusMind Engine — Nexa v2.5")
st.caption("Enterprise GraphRAG RAG Pipeline Interface (Google ADK 2.0.0 Gateway)")

# Initialize memory stores
if "messages" not in st.session_state:
    st.session_state.messages = []
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

# Safe async helper to prevent loop collisions in Streamlit
def run_async_task(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)

# --- SIDEBAR ATTACHMENT: PDF UPLOADER CONTROL ---
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
                    
                    # 2. Package text context matching your router's explicit filter token
                    payload_string = f"DOCUMENT_INJECT_STREAM:\nFilename: {uploaded_pdf.name}\nContent:\n{parsed_text_dump}"
                    
                    # Safe execution via async runner wrapper
                    runner = InMemoryRunner(agent=root_agent)
                    pipeline_outcome = run_async_task(runner.run(input_text=payload_string))
                    
                    st.success("✅ Ingestion Completed Successfully!")
                    st.markdown(pipeline_outcome.text)
                    st.session_state.suggestions = ["Check database structural logs", "Query the uploaded content metrics"]
                    
                except Exception as ex:
                    st.error(f"❌ Ingestion pipeline failed: {str(ex)}")

# Render standard messaging log tables
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Track pending prompt submissions from pill clicks
pending_prompt = None

# Render follow-up pills
if st.session_state.suggestions:
    st.write("✨ **Nexa suggests exploring further:**")
    cols = st.columns(len(st.session_state.suggestions))
    for idx, question in enumerate(st.session_state.suggestions):
        if cols[idx].button(question, key=f"sug_pill_{idx}"):
            pending_prompt = question
            st.session_state.suggestions = []

# Accept input either from the interactive pills or standard chat input entry box
user_input = st.chat_input("Ask Nexa a question or analyze infrastructure vectors...")
if pending_prompt:
    user_input = pending_prompt

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    with st.chat_message("assistant"):
        with st.spinner("🧠 Orchestrating ADK Topologies..."):
            try:
                # Build context window history string to maintain conversational flow across runs
                history_context = ""
                for m in st.session_state.messages[:-1]:
                    prefix = "User: " if m["role"] == "user" else "Assistant: "
                    history_context += f"{prefix}{m['content']}\n"
                
                execution_payload = f"{history_context}User: {user_input}"
                
                # Natively run the consolidated workflow pipeline graph safely via wrapper
                runner = InMemoryRunner(agent=root_agent)
                pipeline_outcome = run_async_task(runner.run(input_text=execution_payload))
                
                answer = pipeline_outcome.text
                st.markdown(answer)
                
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # Automatically extract dynamic followups or fall back to safe exploration defaults
                st.session_state.suggestions = ["Analyze matching vector entities", "View Neo4j operational paths"]
                st.rerun()
                
            except Exception as ex:
                st.error(f"❌ Core runtime error: {str(ex)}")