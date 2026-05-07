import google.generativeai as genai
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from app.core.config import settings
from app.db.session import get_db_connection, get_schema_info

logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    sql_query: str
    data: List[Dict[str, Any]]
    column_names: List[str]
    success: bool
    error_message: Optional[str] = None

@dataclass
class SQLReview:
    review_text: str
    corrected_query: Optional[str] = None

@dataclass
class AgentResponse:
    natural_language_answer: str
    query_result: QueryResult
    review: Optional[SQLReview] = None

GENERATE_SQL_PROMPT = """
You are an expert SQL query generator. Given a natural language question and database schema, 
generate a precise SQL query that answers the question.

Database Schema:
{schema_info}

Natural Language Question: {natural_language_question}

Instructions:
1. Generate only the SQL query, no explanations
2. Use proper MySQL syntax
3. Include appropriate WHERE clauses, JOINs, and ORDER BY if needed
4. Ensure the query is safe and doesn't modify data (SELECT only)
5. If the question is ambiguous, make reasonable assumptions
6. Return only the SQL query without any formatting or markdown

SQL Query:
"""

REVIEW_SQL_PROMPT = """
You are a meticulous reviewer of SQL code. Critically evaluate the following SQL query for correctness, performance, and clarity.

SQL Query to Review:
```sql
{sql_query}
```

Instructions:
1.  Identify inefficiencies, bad practices, and logical errors.
2.  Provide suggestions to improve the query's performance and readability.
3.  If the query can be improved, provide a corrected version of the SQL query.
4.  Format your response as a JSON object with two keys: "review" (a string containing your analysis) and "corrected_query" (a string containing the improved SQL query, or null if no changes are needed).

Your JSON Response:
"""

NATURAL_LANGUAGE_RESPONSE_PROMPT = """
You are a helpful assistant that explains database query results in natural language.

Original Question: {question}
SQL Query Used: {sql_query}
{review_info}Query Results Summary: {data_summary}

Instructions:
1. Provide a clear, conversational answer to the original question
2. Include specific numbers and details from the results
3. If there are many results, summarize the key findings
4. Make the response easy to understand for non-technical users
5. Don't mention SQL or technical database terms unless necessary, but you can mention the review if it's relevant to the answer.

Natural Language Response:
"""

class NaturalLanguageToSQL:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.connection = None
        self.schema_info = self._get_schema()

    def _get_schema(self):
        if self.connection is None:
            self.connection = get_db_connection()
        return get_schema_info(self.connection)

    def _generate_sql_query(self, question: str) -> str:
        prompt = GENERATE_SQL_PROMPT.format(
            schema_info=self.schema_info,
            natural_language_question=question,
        )
        try:
            response = self.model.generate_content(prompt)
            sql_query = response.text.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            return sql_query.strip()
        except Exception as e:
            logger.error(f"Error generating SQL query: {e}")
            raise

    def _execute_sql_query(self, sql_query: str) -> QueryResult:
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(sql_query)
            data = cursor.fetchall()
            column_names = list(data[0].keys()) if data else []
            return QueryResult(
                sql_query=sql_query, data=data, column_names=column_names, success=True
            )
        except Exception as err:
            return QueryResult(
                sql_query=sql_query,
                data=[],
                column_names=[],
                success=False,
                error_message=str(err),
            )
        finally:
            cursor.close()

    def _review_sql_query(self, sql_query: str) -> SQLReview:
        review_prompt = REVIEW_SQL_PROMPT.format(sql_query=sql_query)
        try:
            response = self.model.generate_content(review_prompt)
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            review_data = json.loads(response_text.strip())
            return SQLReview(
                review_text=review_data.get("review", ""),
                corrected_query=review_data.get("corrected_query"),
            )
        except Exception as e:
            logger.error(f"Error reviewing SQL query: {e}")
            return SQLReview(
                review_text=f"Error reviewing query: {e}",
                corrected_query=None,
            )

    def _format_response(self, question: str, query_result: QueryResult, review_text: Optional[str] = None) -> str:
        if not query_result.success:
            return f"Error: {query_result.error_message}"
        if not query_result.data:
            return "No results found."
        
        data_summary = {
            "total_rows": len(query_result.data),
            "columns": query_result.column_names,
            "sample_data": query_result.data[:10],
            "has_more_data": len(query_result.data) > 10,
        }
        
        review_info = f"SQL Query Review:\n{review_text}\n\n" if review_text else ""
        
        prompt = NATURAL_LANGUAGE_RESPONSE_PROMPT.format(
            question=question,
            sql_query=query_result.sql_query,
            review_info=review_info,
            data_summary=json.dumps(data_summary, indent=2, default=str),
        )
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error formatting response: {e}")
            return f"Found {len(query_result.data)} results, but failed to format response."

    def ask_question(self, question: str) -> AgentResponse:
        try:
            sql_query = self._generate_sql_query(question)
            initial_result = self._execute_sql_query(sql_query)
            final_result = initial_result
            review = None

            if not initial_result.success:
                review = self._review_sql_query(sql_query)
                if review.corrected_query:
                    final_result = self._execute_sql_query(review.corrected_query)
            
            answer = self._format_response(
                question, 
                final_result, 
                review.review_text if review else None
            )
            
            return AgentResponse(
                natural_language_answer=answer,
                query_result=final_result,
                review=review
            )
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return AgentResponse(
                natural_language_answer=str(e),
                query_result=QueryResult("", [], [], False, str(e)),
                review=None
            )
            
    def close(self):
        if self.connection:
            self.connection.close()
