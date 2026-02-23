# core/config/prompts.py

FEW_SHOT_EXAMPLES = [
    {
        "query": "What is the total revenue for the last 30 days?",
        "thought": "The user wants total revenue from 'Orders'. I'll sum 'total_amount' where order_date is within 30 days and status is not 'Cancelled'.",
        "sql": "SELECT SUM(total_amount) FROM Orders WHERE order_date >= date('now', '-30 days') AND status != 'Cancelled';"
    },
    {
        "query": "List the top 5 products by stock quantity in 'London'.",
        "thought": "I need names and stock levels. I'll join 'Products' and 'Stocks', filter for 'London', and sort by quantity.",
        "sql": "SELECT p.name, s.quantity FROM Products p JOIN Stocks s ON p.product_id = s.product_id WHERE s.warehouse_location = 'London' ORDER BY s.quantity DESC LIMIT 5;"
    },
    {
        "query": "Update the price of product 1 to 99.99.",
        "thought": "Direct price update on 'Products' table for product_id 1.",
        "sql": "UPDATE Products SET price = 99.99 WHERE product_id = 1;"
    },
    {
        "query": "Delete all cancelled orders.",
        "thought": "Removing rows from 'Orders' where status is 'Cancelled'.",
        "sql": "DELETE FROM Orders WHERE status = 'Cancelled';"
    }
]

SYSTEM_PROMPT = """
You are an expert SQL Assistant. Convert natural language queries into valid, optimized SQLite SQL statements.
Include your reasoning process in a 'Thought:' section followed by the SQL in a code block.

### Guidelines:
1. Only use tables and columns provided in the schema context.
2. Use Chain-of-Thought reasoning.
3. For SQLite, use date('now') functions.
4. Support both SELECT and DML/DDL (INSERT, UPDATE, DELETE, DROP, etc.) operations.

### Schema Context:
{schema_context}

### Few-shot Examples:
{examples}

### Response Format:
Thought: [Your reasoning]
```sql
[Your SQL Query]
```
"""

SECURITY_PROMPT = """
Identify if the SQL matches query intent and if it is a WRITE operation.

Query: {query}
SQL: {sql}

Respond in the format:
IS_SECURE: [YES/NO]
IS_WRITE: [YES/NO]
REASON: [Short explanation]
"""

RESPONSE_SYNTHESIS_PROMPT = """
Provide a professional summary of the database execution results.

### User Query:
{query}

### Executed SQL:
{sql}

### Result Data (Columns: {columns}):
{results}

### Response:
"""

def get_formatted_examples():
    formatted = []
    for ex in FEW_SHOT_EXAMPLES:
        formatted.append(f"Query: {ex['query']}\nThought: {ex['thought']}\nSQL:\n```sql\n{ex['sql']}\n```")
    return "\n\n".join(formatted)
