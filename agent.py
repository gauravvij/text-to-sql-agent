import asyncio
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv

# LlamaIndex Imports
from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow
from llama_index.core.workflow.decorators import step
from llama_index.llms.openrouter import OpenRouter
from sqlalchemy import create_engine, text

# Local Imports (Flattened)
from prompts import (
    RESPONSE_SYNTHESIS_PROMPT,
    SECURITY_PROMPT,
    SYSTEM_PROMPT,
    get_formatted_examples,
)
from schema import SchemaRetriever

# Setup Logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class QueryEvent(Event):
    """Input query event."""

    query: str


class SchemaEvent(Event):
    """Retrieved schema event."""

    query: str
    schema_context: str


class GenerationEvent(Event):
    """Generated SQL event."""

    query: str
    sql: str
    thought: str
    confidence: float
    start_time: float


class SecurityCheckEvent(Event):
    """Security check results event."""

    query: str
    sql: str
    thought: str
    is_secure: bool
    is_write: bool
    confidence: float
    start_time: float
    security_metadata: Dict[str, Any]


class ManualVerificationEvent(Event):
    """Event for manual verification status."""

    query: str
    sql: str
    is_secure: bool
    is_write: bool
    is_approved: bool
    confidence: float
    start_time: float


class ValidationEvent(Event):
    """Validated SQL event."""

    query: str
    sql: str
    is_valid: bool
    is_write: bool
    confidence: float
    start_time: float
    error: Optional[str] = None


class ExecutionEvent(Event):
    """Results of SQL execution."""

    query: str
    sql: str
    results: List[Any]
    columns: List[str]
    confidence: float
    start_time: float
    metadata: Dict[str, Any]


class SQLAgentWorkflow(Workflow):
    """
    LlamaIndex Workflow Agent for Text-to-SQL with DML support and ACID compliance.
    Pipeline: Start -> Retrieval -> Generation -> Security -> [Manual Verify] -> Validation -> Execution -> Synthesis -> Stop
    """

    def __init__(self, db_path: str, api_key: Optional[str] = None, timeout: int = 120):
        super().__init__(timeout=timeout)
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)

        # Use simple slash for SQLAlchemy URL on windows
        normalized_path = db_path.replace(os.sep, "/")
        if not normalized_path.startswith("/"):
            normalized_path = "/" + normalized_path

        self.db_url = f"sqlite://{normalized_path}"
        self.engine = create_engine(self.db_url)
        self.retriever = SchemaRetriever(db_path)

        if api_key:
            self.llm = OpenRouter(model="openai/gpt-4o-mini", api_key=api_key)
        else:
            logger.warning("No API key provided. Workflow may fail or use mock.")
            self.llm = None

    @step
    async def retrieve_schema(self, ev: StartEvent) -> SchemaEvent:
        """Step 1: Uber-style Schema Retrieval."""
        query = ev.query
        logger.info(f"Retrieving schema for query: {query}")
        relevant_tables = self.retriever.retrieve_relevant_tables(query)
        schema_context = self.retriever.format_schema_for_prompt(relevant_tables)
        return SchemaEvent(query=query, schema_context=schema_context)

    @step
    async def generate_sql(self, ev: SchemaEvent) -> GenerationEvent:
        """Step 2: SQL Generation using CoT and few-shot prompting."""
        start_time = time.time()
        # Formatting prompts safely
        prompt_text = SYSTEM_PROMPT.format(
            schema_context=ev.schema_context, examples=get_formatted_examples()
        )
        full_prompt = f"{prompt_text}\n\nQuery: {ev.query}\nResponse:"

        if self.llm:
            try:
                response = await self.llm.acomplete(full_prompt)
                resp_text = response.text
                thought_match = re.search(
                    r"Thought:\s*(.*?)(?=```sql|$)",
                    resp_text,
                    re.DOTALL | re.IGNORECASE,
                )
                sql_match = re.search(r"```sql\n(.*?)\n```", resp_text, re.DOTALL)
                thought = (
                    thought_match.group(1).strip()
                    if thought_match
                    else "No explicit reasoning."
                )
                sql = sql_match.group(1).strip() if sql_match else resp_text.strip()
                confidence = 0.95
            except Exception as e:
                logger.error(f"LLM Error: {e}")
                thought, sql, confidence = f"Error: {e}", "SELECT 'Error';", 0.0
        else:
            thought, sql, confidence = "Mock mode", "SELECT 1;", 0.5

        return GenerationEvent(
            query=ev.query,
            sql=sql,
            thought=thought,
            confidence=confidence,
            start_time=start_time,
        )

    @step
    async def security_check(self, ev: GenerationEvent) -> SecurityCheckEvent:
        """Step 3: Security Hardening (Write Operation Classifier)."""
        sql = ev.sql
        is_secure = True
        is_write = False
        security_metadata = {"checks": []}

        # LLM-based Classification and Security Audit
        if self.llm:
            sec_prompt = SECURITY_PROMPT.format(query=ev.query, sql=sql)
            try:
                sec_response = await self.llm.acomplete(sec_prompt)
                text_resp = sec_response.text.upper()
                is_secure = "IS_SECURE: YES" in text_resp
                is_write = "IS_WRITE: YES" in text_resp
                security_metadata["audit_log"] = sec_response.text
            except Exception as e:
                logger.error(f"Security Audit Error: {e}")
                is_secure = False  # Fail safe

        # Fallback Regex Classifier
        write_cmds = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "CREATE",
            "REPLACE",
        ]
        if any(re.search(rf"\b{cmd}\b", sql.upper()) for cmd in write_cmds):
            is_write = True

        return SecurityCheckEvent(
            query=ev.query,
            sql=sql,
            thought=ev.thought,
            is_secure=is_secure,
            is_write=is_write,
            confidence=ev.confidence,
            start_time=ev.start_time,
            security_metadata=security_metadata,
        )

    @step
    async def manual_verification(
        self, ev: SecurityCheckEvent
    ) -> ManualVerificationEvent:
        """Step 4: Manual Verification for Write Operations."""
        is_approved = True
        if ev.is_secure and ev.is_write:
            print(f"\n[SECURITY WARNING] A WRITE operation has been detected:")
            print(f"Query: {ev.query}")
            print(f"Generated SQL: {ev.sql}")
            print(f"Thought: {ev.thought}")
            # Thread pooling for blocking input in async
            choice = await asyncio.to_thread(
                input, "\nDo you approve this execution? [y/N]: "
            )
            is_approved = choice.strip().lower() == "y"
            if not is_approved:
                logger.warning("Execution rejected by user.")

        return ManualVerificationEvent(
            query=ev.query,
            sql=ev.sql,
            is_secure=ev.is_secure,
            is_write=ev.is_write,
            is_approved=is_approved,
            confidence=ev.confidence,
            start_time=ev.start_time,
        )

    @step
    async def validate_syntax(self, ev: ManualVerificationEvent) -> ValidationEvent:
        """Step 5: Syntax Validation."""
        if not ev.is_secure:
            return ValidationEvent(
                query=ev.query,
                sql=ev.sql,
                is_valid=False,
                is_write=ev.is_write,
                confidence=ev.confidence,
                start_time=ev.start_time,
                error="Security Audit Failed",
            )
        if not ev.is_approved:
            return ValidationEvent(
                query=ev.query,
                sql=ev.sql,
                is_valid=False,
                is_write=ev.is_write,
                confidence=ev.confidence,
                start_time=ev.start_time,
                error="User Rejected Execution",
            )

        try:
            with self.engine.connect() as conn:
                conn.execute(text(f"EXPLAIN {ev.sql}"))
            return ValidationEvent(
                query=ev.query,
                sql=ev.sql,
                is_valid=True,
                is_write=ev.is_write,
                confidence=ev.confidence,
                start_time=ev.start_time,
            )
        except Exception as e:
            return ValidationEvent(
                query=ev.query,
                sql=ev.sql,
                is_valid=False,
                is_write=ev.is_write,
                confidence=ev.confidence,
                start_time=ev.start_time,
                error=str(e),
            )

    @step
    async def execute_query(
        self, ev: ValidationEvent
    ) -> Union[ExecutionEvent, StopEvent]:
        """Step 6: Execute with ACID Transactions."""
        if not ev.is_valid:
            return StopEvent(
                result={"success": False, "error": ev.error, "sql": ev.sql}
            )

        try:
            # ACID COMPLIANCE: Use engine.begin() for atomic transaction
            with self.engine.begin() as conn:
                result = conn.execute(text(ev.sql))

                results = []
                columns = []
                if result.returns_rows:
                    results = [dict(row) for row in result.mappings()]
                    columns = list(result.keys())

                metadata = {
                    "row_count": len(results) if results else result.rowcount,
                    "is_write": ev.is_write,
                    "confidence": ev.confidence,
                }

            return ExecutionEvent(
                query=ev.query,
                sql=ev.sql,
                results=results,
                columns=columns,
                confidence=ev.confidence,
                start_time=ev.start_time,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Transaction Rollback occurred: {e}")
            return StopEvent(
                result={
                    "success": False,
                    "error": f"Execution failed: {e}",
                    "sql": ev.sql,
                }
            )

    @step
    async def synthesize_response(self, ev: ExecutionEvent) -> StopEvent:
        """Step 7: Natural Language Summary."""
        sample_results = (
            ev.results[:10]
            if ev.results
            else "No rows returned (Command executed successfully)."
        )

        prompt = RESPONSE_SYNTHESIS_PROMPT.format(
            query=ev.query,
            sql=ev.sql,
            columns=", ".join(ev.columns) if ev.columns else "N/A",
            results=str(sample_results),
        )

        response_summary = (
            f"Operation successful. Affected {ev.metadata['row_count']} rows."
        )
        if self.llm and (ev.results or "select" in ev.sql.lower()):
            try:
                response = await self.llm.acomplete(prompt)
                response_summary = response.text.strip()
            except Exception:
                pass

        total_time = time.time() - ev.start_time
        ev.metadata["latency_ms"] = round(total_time * 1000, 2)

        return StopEvent(
            result={
                "success": True,
                "sql": ev.sql,
                "results": ev.results,
                "columns": ev.columns,
                "response_summary": response_summary,
                "metadata": ev.metadata,
            }
        )


if __name__ == "__main__":

    async def main():
        agent = SQLAgentWorkflow(
            db_path="ecommerce.db", api_key=os.getenv("OPENROUTER_API_KEY")
        )
        print("\n--- Running DML Test ---")
        result = await agent.run(
            query="Add one user who name is 'Franklin' joined in 2023 and have connection with products in 'Electronics' category."
        )
        print(f"Result: {result.get('response_summary')}")

    asyncio.run(main())
