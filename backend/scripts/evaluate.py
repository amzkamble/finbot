import os
import json
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv

# Ragas imports
from ragas import evaluate
try:
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
        answer_correctness,
    )
except ImportError:
    # Older versions of ragas
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    answer_correctness = None

from datasets import Dataset
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings

# Configure Groq as the Judge for Ragas
def get_judge_llm():
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "llama-3.1-8b-instant"),
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
    )

def get_judge_embeddings():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# App imports
import sys
sys.path.append("src")
from finbot.api.deps import get_rag_chain, get_query_router
from finbot.auth.rbac import ALL_COLLECTIONS

load_dotenv("../.env")

# Evaluation Configuration
DATA_DIR = Path("../data")
EVAL_DATA_FILE = DATA_DIR / "eval_dataset.json"

def run_evaluation(use_routing=True):
    print(f"\n--- Running Evaluation (Routing={'ON' if use_routing else 'OFF'}) ---")
    
    with open(EVAL_DATA_FILE, "r", encoding="utf-8") as f:
        ground_truth_data = json.load(f)

    rag_chain = get_rag_chain()
    router = get_query_router()
    
    results = []
    
    # We use a subset for speed if needed, but let's try the whole 40
    for item in tqdm(ground_truth_data[:40]):
        query = item["question"]
        target_role = "executive" # Use executive to ensure access to all
        
        # Decide collections
        if use_routing:
            route_res = router.classify(query, target_role)
            cols = route_res.target_collections
        else:
            cols = ["finance", "engineering", "marketing", "hr", "general"]

        # Run RAG
        response = rag_chain.run(
            query=query,
            user_role=target_role,
            target_collections=cols
        )
        
        results.append({
            "question": query,
            "answer": response.answer,
            "contexts": response.contexts,
            "ground_truth": item["answer"]
        })

    # Prepare for RAGAs
    dataset_dict = {
        "question": [r["question"] for r in results],
        "answer": [r["answer"] for r in results],
        "contexts": [r["contexts"] for r in results],
        "ground_truth": [r["ground_truth"] for r in results]
    }
    dataset = Dataset.from_dict(dataset_dict)
    
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    if answer_correctness:
        metrics.append(answer_correctness)

    score = evaluate(
        dataset,
        metrics=metrics,
        llm=get_judge_llm(),
        embeddings=get_judge_embeddings(),
    )
    
    return score.to_pandas()

if __name__ == "__main__":
    if not EVAL_DATA_FILE.exists():
        print("Error: Run generate_eval_data.py first.")
        sys.exit(1)
        
    # Ablation Study
    results_routing = run_evaluation(use_routing=True)
    print("\nMetrics with Routing (Full Pipeline):")
    print(results_routing.mean(numeric_only=True))
    
    results_baseline = run_evaluation(use_routing=False)
    print("\nMetrics without Routing (Baseline):")
    print(results_baseline.mean(numeric_only=True))
    
    # Save results
    results_routing.to_csv("eval_results_full.csv", index=False)
    results_baseline.to_csv("eval_results_baseline.csv", index=False)
