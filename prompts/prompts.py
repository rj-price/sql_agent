# prompts.py

# Prompt to generate SQL query from natural language
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

# Prompt to review a failed SQL query
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

# Prompt to format the final natural language response
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
