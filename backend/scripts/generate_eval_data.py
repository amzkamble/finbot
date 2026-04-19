import os
import json
import time
from pathlib import Path
from tqdm import tqdm
from groq import Groq
from dotenv import load_dotenv

load_dotenv("../.env")

# Configuration
DATA_DIR = Path("../data")
OUTPUT_FILE = DATA_DIR / "eval_dataset.json"
COLLECTIONS = ["finance", "engineering", "marketing", "hr", "general"]
QA_PER_COLLECTION = 10

# Initialize Groq
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.1-8b-instant"

PROMPT_TEMPLATE = """
As an AI Evaluation Engineer, generate {count} high-quality Question and Answer pairs based on the text below. 
The questions should be specific and require data from the text to answer accurately. 
Include the exact snippet of text that supports each answer as "context".

Format your response AS A JSON LIST ONLY:
[
  {{"question": "...", "answer": "...", "context": "...", "collection": "{collection}"}},
  ...
]

TEXT:
{text}
"""

def generate_qa_pairs():
    dataset = []
    
    for collection in COLLECTIONS:
        print(f"Generating QA for {collection}...")
        col_dir = DATA_DIR / collection
        if not col_dir.exists():
            continue
            
        # Read a few files to get enough context
        combined_text = ""
        for file_path in list(col_dir.glob("*"))[:3]: # Top 3 files
            if file_path.is_file():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        combined_text += f.read() + "\n\n"
                except:
                    continue
        
        if not combined_text.strip():
            continue

        # Truncate text if too long for prompt
        truncated_text = combined_text[:4000]

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(count=QA_PER_COLLECTION, text=truncated_text, collection=collection)}],
                temperature=0.7,
                response_format={"type": "json_object"} if "llama-3-70b" in MODEL else None
            )
            
            content = response.choices[0].message.content
            # Basic cleanup in case JSON isn't perfect
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            
            pairs = json.loads(content)
            # Support if the LLM wrapped it in a key
            if isinstance(pairs, dict):
                for key in ["questions", "pairs", "data"]:
                    if key in pairs:
                        pairs = pairs[key]
                        break
            
            dataset.extend(pairs)
            print(f"  Successfully generated {len(pairs)} pairs.")
            time.sleep(1) # Rate limiting
            
        except Exception as e:
            print(f"  Error generating for {collection}: {e}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    
    print(f"\nDone! Dataset saved to {OUTPUT_FILE}")
    print(f"Total pairs generated: {len(dataset)}")

if __name__ == "__main__":
    generate_qa_pairs()
