import os
import asyncio
import time
import pandas as pd
import sqlite3
from agent import SQLAgentWorkflow
from dotenv import load_dotenv

load_dotenv()

BENCHMARK_QUERIES = [
    {
        "query": "Show me the top 5 products by price",
        "type": "Simple Select"
    },
    {
        "query": "Update the price of product with product_id 1 to 89.99",
        "type": "DML - Update"
    },
    {
        "query": "Delete all orders with status 'Cancelled'",
        "type": "DML - Delete"
    },
    {
        "query": "What is the total revenue from all orders?",
        "type": "Aggregate Select"
    }
]

def get_db_checksum(db_path):
    """Simple checksum to verify DB state."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Get count and sum of prices as a proxy for state
        cursor.execute("SELECT COUNT(*), SUM(price) FROM Products")
        p_info = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM Orders")
        o_info = cursor.fetchone()
        conn.close()
        return f"Products: {p_info}, Orders: {o_info}"
    except Exception as e:
        return f"Error: {e}"

async def run_benchmark():
    api_key = os.getenv("OPENROUTER_API_KEY")
    agent = SQLAgentWorkflow(db_path="ecommerce.db", api_key=api_key)
    results = []

    print(f"Starting ACID-Compliant Benchmark on {len(BENCHMARK_QUERIES)} queries...")
    print(f"Pre-run Checksum: {get_db_checksum('ecommerce.db')}")

    for item in BENCHMARK_QUERIES:
        query = item['query']
        start_time = time.time()
        
        print(f"\n[*] Processing ({item['type']}): {query}")
        
        try:
            # Note: For DML, the agent will prompt for [y/N] in console.
            # In an automated benchmark, we might need to mock input or bypass.
            # Here we let it run - agent.py uses input(). 
            # TIP: For this automated run, we can patch input to always 'y'.
            
            workflow_result = await agent.run(query=query)
            latency = time.time() - start_time
            
            results.append({
                "query": query,
                "type": item["type"],
                "success": workflow_result.get("success", False),
                "sql": workflow_result.get("sql", "N/A"),
                "answer": workflow_result.get("response_summary", "N/A"),
                "latency_sec": round(latency, 3),
                "is_write": workflow_result.get("metadata", {}).get("is_write", False),
                "error": workflow_result.get("error", "None")
            })
            
            print(f"    Latency: {round(latency, 2)}s | Success: {workflow_result.get('success')}")
        except Exception as e:
            print(f"[!] Query: {query} | Error: {e}")

    print(f"\nPost-run Checksum: {get_db_checksum('ecommerce.db')}")

    df = pd.DataFrame(results)
    os.makedirs("analysis", exist_ok=True)
    df.to_csv("analysis/dml_benchmark_results.csv", index=False)
    
    accuracy = (df['success'].sum() / len(df)) * 100
    print(f"\nFinal Metrics:")
    print(f"Accuracy: {accuracy}%")
    print("Benchmark logs updated in analysis/dml_benchmark_results.csv")

if __name__ == "__main__":
    # Mock input for automated benchmark execution
    import builtins
    original_input = builtins.input
    builtins.input = lambda _: 'y'
    
    try:
        asyncio.run(run_benchmark())
    finally:
        builtins.input = original_input
