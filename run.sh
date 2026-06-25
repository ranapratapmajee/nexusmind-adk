#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# Configuration variables
VENV_DIR=".venv"
GRADIO_APP="gradio_app.py"  # 🌟 FIXED: Pointing to Gradio workspace instead of Streamlit

# Setup text styling colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO] $(date +'%Y-%m-%d %H:%M:%S') - $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}[WARN] $(date +'%Y-%m-%d %H:%M:%S') - $1${NC}"
}

log_error() {
    echo -e "${RED}[ERROR] $(date +'%Y-%m-%d %H:%M:%S') - $1${NC}"
}

# =========================================================
# ⚙️ EXPLICIT PROCESS TEARDOWN TRAP HANDLER
# =========================================================
cleanup_services() {
    echo ""
    log_warn "🛑 Termination signal intercepted. Safely shutting down app runtime..."
    trap - SIGINT SIGTERM # Prevent infinite loop recursion
    
    # 🌟 FIXED: Target specifically running app pids rather than terminal group kill 0
    if [ -not -z "$APP_PID" ]; then
        kill "$APP_PID" 2>/dev/null || true
    fi
    
    log_info "✅ Port cleared. Goodbye!"
    exit 0
}

# Catch Ctrl + C (SIGINT) and system stop requests (SIGTERM)
trap cleanup_services SIGINT SIGTERM

echo "========================================================="
echo "🧠 NexusMind Engine Execution Gateway v2.5"
echo "========================================================="

# 1. Check for Virtual Environment
if [ -d "$VENV_DIR" ]; then
    log_info "Found virtual environment at '$VENV_DIR'. Activating..."
    source "$VENV_DIR/bin/activate"
    RUN_PREFIX=""
else
    log_warn "No virtual environment found at '$VENV_DIR'."
    if command -v uv &> /dev/null; then
        log_info "Detected 'uv' toolchain. Using 'uv run' configuration..."
        RUN_PREFIX="uv run "
    elif command -v poetry &> /dev/null; then
        log_info "Detected 'poetry' toolchain. Using 'poetry run' configuration..."
        RUN_PREFIX="poetry run "
    else
        log_warn "Proceeding with system global Python context (not recommended)..."
        RUN_PREFIX=""
    fi
fi

# 2. Infrastructure Health Checking Dependencies
log_info "Verifying required service availability vectors..."

OLLAMA_HOST="${LOCAL_LLM_URL:-http://localhost:11434}"
log_info "Pinging Ollama Core instance at: $OLLAMA_HOST ..."
if curl -s --output /dev/null --connect-timeout 3 "$OLLAMA_HOST"; then
    log_info "✅ Ollama Endpoint is responsive."
else
    log_error "❌ Ollama is unreachable. Please start Ollama before launching NexusMind."
    exit 1
fi

CHROMA_PORT="${CHROMA_PORT:-8000}"
CHROMA_HOST="${CHROMA_HOST:-localhost}"
log_info "Checking ChromaDB HTTP Vector cluster on port: $CHROMA_PORT ..."
if nc -z "$CHROMA_HOST" "$CHROMA_PORT" 2>/dev/null || curl -s "http://$CHROMA_HOST:$CHROMA_PORT/api/v1/heartbeat" --output /dev/null --connect-timeout 2; then
    log_info "✅ Chroma DB cluster connectivity confirmed."
else
    log_warn "⚠️ Chroma DB server connection timed out."
fi

NEO4J_HOST="localhost"
NEO4J_PORT="7687"
log_info "Checking Neo4j transactional graph database engine on port: $NEO4J_PORT ..."
if nc -z "$NEO4J_HOST" "$NEO4J_PORT" 2>/dev/null; then
    log_info "✅ Neo4j graph driver network connectivity confirmed."
else
    log_warn "⚠️ Neo4j port $NEO4J_PORT is unresponsive."
fi

# 3. Export PythonPath to ensure clean app module resolution
# 🌟 FIXED: Standard configuration checks for preceding values to prevent syntax splits
if [ -z "$PYTHONPATH" ]; then
    export PYTHONPATH=$(pwd)
else
    export PYTHONPATH=$PYTHONPATH:$(pwd)
fi

# 4. Launch Gradio UI Web Gateway Engine
if [ -f "$GRADIO_APP" ]; then
    log_info "Spawning Gradio Web Application Node on http://127.0.0.1:7860 ..."
    echo "--------------------------------------------------------"
    
    # 🌟 FIXED: Runs Gradio natively via python invocation matching your app architecture
    ${RUN_PREFIX}python "$GRADIO_APP" &
    APP_PID=$!
    wait $APP_PID
else
    log_error "Target entrypoint UI matrix file '$GRADIO_APP' was not found in working path."
    exit 1
fi