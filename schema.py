import os
import sqlite3
from typing import List, Dict, Any
from sqlalchemy import create_engine, inspect

class SchemaRetriever:
    """
    Uber-style Schema Retriever that caches table metadata and dynamically 
    retrieves relevant tables based on query keywords.
    """
    
    def __init__(self, db_path: str):
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        
        normalized_path = db_path.replace("\\", "/")
        if not normalized_path.startswith("/"):
            normalized_path = "/" + normalized_path
            
        self.db_url = f"sqlite://{normalized_path}"
        self.engine = create_engine(self.db_url)
        self._cache = {}
        self._refresh_cache()

    def _refresh_cache(self):
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()
        
        for table in table_names:
            columns = inspector.get_columns(table)
            column_info = [{"name": c["name"], "type": str(c["type"])} for c in columns]
            description = f"Table containing information about {table.replace('_', ' ')}"
            self._cache[table] = {
                "name": table,
                "description": description,
                "columns": column_info
            }

    def get_all_tables(self) -> List[str]:
        return list(self._cache.keys())

    def retrieve_relevant_tables(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_words = set(query.lower().replace("?", "").replace(".", "").split())
        scored_tables = []
        
        for table_name, meta in self._cache.items():
            score = 0
            for word in query_words:
                if word in table_name.lower(): score += 10
            for col in meta["columns"]:
                for word in query_words:
                    if word in col["name"].lower(): score += 5
            if score > 0: scored_tables.append((score, meta))
        
        scored_tables.sort(key=lambda x: x[0], reverse=True)
        if not scored_tables:
            return [meta for name, meta in list(self._cache.items())[:top_k]]
            
        return [t[1] for t in scored_tables[:top_k]]

    def format_schema_for_prompt(self, tables: List[Dict[str, Any]]) -> str:
        formatted = []
        for table in tables:
            lines = [f"Table: {table['name']} ({table['description']})"]
            cols = ", ".join([f"{c['name']} ({c['type']})" for c in table["columns"]])
            lines.append(f"Columns: {cols}")
            formatted.append("\n".join(lines))
        return "\n\n".join(formatted)
