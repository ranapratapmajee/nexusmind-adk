# filepath: scripts/ingest.py
import os
import sys
import argparse
import asyncio
import shutil
from pathlib import Path

# Connect directly to the decoupled ingestion worker
from app.backend_engine import process_file_ingestion

# Set up the clean landing path for files destined for ingestion
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"

def setup_ingest_directory():
    """Natively constructs the local ingestion file directory if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR

async def run_cli_ingestion(file_path: str):
    target_path = Path(file_path)
    if not target_path.exists() or not target_path.is_file():
        print(f"❌ Error: Target file configuration resource not found: {file_path}")
        sys.exit(1)
        
    if target_path.suffix.lower() != ".pdf":
        print(f"❌ Error: Ingestion architecture strictly enforces standard .pdf validation constraints.")
        sys.exit(1)

    # 1. Stage the file into your isolated ingest data folder
    ingest_home = setup_ingest_directory()
    staged_destination = ingest_home / target_path.name
    
    # If the user targets a file already inside the data directory, skip copying
    if target_path.parent.resolve() != ingest_home.resolve():
        print(f"📁 Staging a copy into the ingestion channel: {staged_destination}")
        shutil.copy2(target_path, staged_destination)
    else:
        print(f"📁 Processing file directly inside ingestion channel: {staged_destination}")

    # 2. Fire direct batch processing out of the file's landing spot
    print(f"⚙️ Triggering background workflow engine on data/{target_path.name}...")
    try:
        report_output = await process_file_ingestion(target_path.name)
        
        print("\n========================================================")
        print("✅ INGESTION PIPELINE EXECUTED SUCCESSFULLY")
        print("========================================================\n")
        print(report_output)
        
    except Exception as ex:
        print(f"❌ Operational failure during processing phase: {str(ex)}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NexusMind CLI Document Engine Ingestion Tool")
    parser.add_argument("file", help="Path to the local source PDF document asset")
    args = parser.parse_args()

    asyncio.run(run_cli_ingestion(args.file))