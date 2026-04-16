import sys
import os
from rag import ingest_file

def main():
    if len(sys.argv) < 2:
        print("Usage: python vectorize.py <path_to_pdf_or_txt>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
        
    basename = os.path.basename(file_path)
    source_label = os.path.splitext(basename)[0]
    
    print(f"Vectorizing {file_path} into local ChromaDB with source label '{source_label}'...")
    chunks_ingested = ingest_file(file_path, source_label)
    
    if chunks_ingested > 0:
        print(f"✅ Successfully ingested {chunks_ingested} chunks.")
    else:
        print("❌ Failed to ingest chunks or no text could be extracted.")

if __name__ == "__main__":
    main()
