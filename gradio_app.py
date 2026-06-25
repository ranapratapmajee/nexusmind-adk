# filepath: gradio_app.py
import gradio as gr
from google.genai import types

# Connect directly to your unified root topology gateway
from app.agent import root_agent
from google.adk.runners import InMemoryRunner

# Initialize your native ADK persistent chat runner
chat_runner = InMemoryRunner(agent=root_agent, app_name="app")
if hasattr(chat_runner, "auto_create_session"):
    chat_runner.auto_create_session = True

def stream_nexa_response(message: str, history: list):
    """
    Simpler, synchronous-compatible event wrapper running your active 
    runner stream loop directly to output text tokens.
    """
    # Trigger the stream payload execution pass from your gateway runner
    outcome_stream = chat_runner.run(
        user_id="default_user",
        session_id="active_chat_session",
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=message.strip())]
        )
    )
    
    accumulated_text = ""
    for event in outcome_stream:
        # Grab text safely from any event node that produces a string payload
        text_chunk = getattr(event, "text", "")
        if not text_chunk and hasattr(event, "content") and hasattr(event.content, "parts"):
            text_chunk = "".join([p.text for p in event.content.parts if hasattr(p, "text") and p.text])
            
        # Ignore raw structural control flags from leaking into the text window
        if text_chunk and not any(t in text_chunk.upper() for t in ["CHAT_PATH", "RESEARCH_PATH", "ROUTE_TO_ROUTER"]):
            accumulated_text += text_chunk
            yield accumulated_text.strip()

# =========================================================
# ULTRA-SIMPLE GRADIO CHAT INTERFACE
# =========================================================
demo = gr.ChatInterface(
    fn=stream_nexa_response,
    title="🧠 NexusMind Workspace",
    description="Nexa — High-Density Grounded Cognitive Assistant",
    theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate")
)

if __name__ == "__main__":
    demo.queue().launch(server_name="127.0.0.1", server_port=7860)