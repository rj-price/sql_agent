import mysql.connector
import google.generativeai as genai
import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging
from datetime import datetime
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str
    user: str
    password: str
    database: str
    port: int = 3306

@dataclass
class QueryResult:
    """Structure to hold query results"""
    sql_query: str
    data: List[Dict[str, Any]]
    column_names: List[str]
    success: bool
    error_message: Optional[str] = None

@dataclass
class SQLReview:
    """Structure to hold SQL review results"""
    review_text: str
    corrected_query: Optional[str] = None

@dataclass
class AgentResponse:
    """Structure to hold the final response from the agent"""
    natural_language_answer: str
    query_result: QueryResult
    review: Optional[SQLReview] = None

class NaturalLanguageToSQL:
    """Main class for natural language to SQL conversion and execution"""
    
    def __init__(self, db_config: DatabaseConfig, gemini_api_key: str, debug: bool = False):
        self.db_config = db_config
        self.debug = debug
        self.connection = None
        
        # Configure Gemini API
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Connect to database
        self._connect_to_database()
        
        # Get database schema
        self.schema_info = self._get_database_schema()
        
    def _connect_to_database(self):
        """Establish connection to MySQL database"""
        try:
            self.connection = mysql.connector.connect(
                host=self.db_config.host,
                user=self.db_config.user,
                password=self.db_config.password,
                database=self.db_config.database,
                port=self.db_config.port
            )
            logger.info("Successfully connected to MySQL database")
        except mysql.connector.Error as err:
            logger.error(f"Error connecting to MySQL: {err}")
            raise
    
    def _get_database_schema(self) -> str:
        """Extract database schema information"""
        schema_info = []
        cursor = self.connection.cursor()
        
        try:
            # Get all tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            for (table_name,) in tables:
                schema_info.append(f"\nTable: {table_name}")
                
                # Get column information
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                
                for column in columns:
                    col_name, col_type, null, key, default, extra = column
                    schema_info.append(f"  - {col_name}: {col_type} {'(Primary Key)' if key == 'PRI' else ''}")
                
                # Get sample data (first 3 rows)
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                sample_data = cursor.fetchall()
                if sample_data:
                    schema_info.append("  Sample data:")
                    for row in sample_data:
                        schema_info.append(f"    {row}")
        
        except mysql.connector.Error as err:
            logger.error(f"Error getting schema: {err}")
        finally:
            cursor.close()
        
        return "\n".join(schema_info)
    
    def _generate_sql_query(self, natural_language_question: str) -> str:
        """Convert natural language question to SQL query using Gemini"""
        
        prompt = f"""
You are an expert SQL query generator. Given a natural language question and database schema, 
generate a precise SQL query that answers the question.

Database Schema:
{self.schema_info}

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
        
        try:
            response = self.model.generate_content(prompt)
            sql_query = response.text.strip()
            
            # Clean up the response (remove markdown formatting if present)
            if sql_query.startswith('```sql'):
                sql_query = sql_query[6:]
            if sql_query.endswith('```'):
                sql_query = sql_query[:-3]
            sql_query = sql_query.strip()
            
            if self.debug:
                print(f"\n🔍 DEBUG - Generated SQL Query:")
                print(f"   {sql_query}")
            
            return sql_query
            
        except Exception as e:
            logger.error(f"Error generating SQL query: {e}")
            raise
    
    def _execute_sql_query(self, sql_query: str) -> QueryResult:
        """Execute SQL query and return results"""
        cursor = self.connection.cursor(dictionary=True)
        
        try:
            cursor.execute(sql_query)
            data = cursor.fetchall()
            column_names = list(data[0].keys()) if data else []
            
            if self.debug:
                print(f"\n📊 DEBUG - Query Results:")
                print(f"   Rows returned: {len(data)}")
                print(f"   Columns: {column_names}")
                if data:
                    print(f"   Sample data: {data[:3]}")
            
            return QueryResult(
                sql_query=sql_query,
                data=data,
                column_names=column_names,
                success=True
            )
            
        except mysql.connector.Error as err:
            error_msg = f"SQL execution error: {err}"
            logger.error(error_msg)
            
            if self.debug:
                print(f"\n❌ DEBUG - SQL Error:")
                print(f"   {error_msg}")
            
            return QueryResult(
                sql_query=sql_query,
                data=[],
                column_names=[],
                success=False,
                error_message=error_msg
            )
        finally:
            cursor.close()
    
    def _review_sql_query(self, sql_query: str) -> SQLReview:
        """
        Critically evaluates an SQL query and provides a corrected version if necessary.
        """
        review_prompt = f"""
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
        try:
            logger.info("Sending SQL query for review to Gemini...")
            response = self.model.generate_content(review_prompt)
            
            # Clean up and parse JSON
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            review_data = json.loads(response_text)
            
            review = SQLReview(
                review_text=review_data.get("review", "No review text provided."),
                corrected_query=review_data.get("corrected_query")
            )

            if self.debug:
                print("\n📝 DEBUG - SQL Review:")
                print(f"   Review: {review.review_text}")
                if review.corrected_query:
                    print(f"   Corrected Query: {review.corrected_query}")

            return review

        except (Exception, json.JSONDecodeError) as e:
            logger.error(f"Error reviewing SQL query with Gemini: {e}")
            # Fallback in case of error
            return SQLReview(
                review_text=f"Error: Could not review SQL query due to an internal error: {e}",
                corrected_query=None
            )

    def _format_natural_language_response(self, question: str, query_result: QueryResult, review_text: Optional[str] = None) -> str:
        """Generate natural language response from query results using Gemini"""
        
        if not query_result.success:
            return f"I encountered an error while processing your question: {query_result.error_message}"
        
        if not query_result.data:
            return "I found no results for your question in the database."
        
        # Prepare data summary for the LLM
        data_summary = {
            "total_rows": len(query_result.data),
            "columns": query_result.column_names,
            "sample_data": query_result.data[:10],  # Send first 10 rows to avoid token limits
            "has_more_data": len(query_result.data) > 10
        }
        
        review_info = ""
        if review_text and "Error:" not in review_text:
            review_info = f"SQL Query Review:\n{review_text}\n\n"

        prompt = f"""
You are a helpful assistant that explains database query results in natural language.

Original Question: {question}
SQL Query Used: {query_result.sql_query}
{review_info}Query Results Summary: {json.dumps(data_summary, indent=2, default=str)}

Instructions:
1. Provide a clear, conversational answer to the original question
2. Include specific numbers and details from the results
3. If there are many results, summarize the key findings
4. Make the response easy to understand for non-technical users
5. Don't mention SQL or technical database terms unless necessary, but you can mention the review if it's relevant to the answer.

Natural Language Response:
"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error generating natural language response: {e}")
            return f"I found {len(query_result.data)} results, but encountered an error formatting the response."

    def ask_question(self, question: str) -> AgentResponse:
        """Main method to process natural language questions"""
        
        if self.debug:
            print(f"\n❓ User Question: {question}")
            print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Step 1: Generate initial SQL query
            sql_query = self._generate_sql_query(question)
            
            # Step 2: Attempt to execute the initial SQL query
            initial_query_result = self._execute_sql_query(sql_query)
            
            final_query_result = initial_query_result
            review_result_for_response = None
            
            # Step 3: Check for execution errors and conditionally review/re-execute
            if not initial_query_result.success:
                logger.warning(f"Initial SQL query failed: {initial_query_result.error_message}. Attempting review and correction.")
                
                # Review the failed SQL query
                review_result = self._review_sql_query(sql_query)
                review_result_for_response = review_result # Store review object for final response
                
                if review_result.corrected_query:
                    if self.debug:
                        print("\n🔄 DEBUG - Initial query failed. Using corrected SQL query for re-execution.")
                    # Re-execute with the corrected query
                    final_query_result = self._execute_sql_query(review_result.corrected_query)
                    
                    if not final_query_result.success:
                        logger.error(f"Corrected SQL query also failed: {final_query_result.error_message}")
                else:
                    if self.debug:
                        print("\n⚠️ DEBUG - Initial query failed, but no corrected query was provided by the reviewer.")
            
            # Step 4: Generate natural language response using the final query result
            response_text = self._format_natural_language_response(
                question, final_query_result, review_result_for_response.review_text if review_result_for_response else None
            )

            agent_response = AgentResponse(
                natural_language_answer=response_text,
                query_result=final_query_result,
                review=review_result_for_response
            )

            if self.debug:
                print(f"\n💬 Final Response:")
                print(f"   {agent_response.natural_language_answer}")
                print(f"\n" + "="*50)
            
            return agent_response
            
        except Exception as e:
            error_msg = f"Error processing question: {e}"
            logger.error(error_msg)
            return AgentResponse(
                natural_language_answer=error_msg,
                query_result=QueryResult(sql_query="", data=[], column_names=[], success=False, error_message=str(e)),
                review=None
            )
    
    def close_connection(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

def main():
    """Example usage of the NaturalLanguageToSQL system"""
    
    load_dotenv()
    
    # Configuration
    sql_host = os.getenv("SQL_HOST", "localhost")
    sql_user = os.getenv("SQL_USER", "root")
    sql_password = os.getenv("SQL_PASSWORD", "password")
    sql_database = os.getenv("SQL_DATABASE", "sales_db")
    
    db_config = DatabaseConfig(
        host=sql_host,
        user=sql_user,
        password=sql_password,
        database=sql_database
    )
    
    # Get API key from environment variable
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    if not gemini_api_key:
        print("Error: Please set GOOGLE_API_KEY environment variable")
        return
    
    # Initialize the system
    try:
        nl_to_sql = NaturalLanguageToSQL(
            db_config=db_config,
            gemini_api_key=gemini_api_key,
            debug=True  # Enable debug mode
        )
        
        print("🚀 Natural Language to SQL System Ready!")
        print("Type 'quit' to exit, 'debug on/off' to toggle debug mode")
        print("-" * 50)
        
        while True:
            question = input("\n💬 Ask a question about your database: ").strip()
            
            if question.lower() == 'quit':
                break
            elif question.lower() == 'debug on':
                nl_to_sql.debug = True
                print("✅ Debug mode enabled")
                continue
            elif question.lower() == 'debug off':
                nl_to_sql.debug = False
                print("✅ Debug mode disabled")
                continue
            elif not question:
                continue
            
            # Process the question
            response_obj = nl_to_sql.ask_question(question)
            print(f"\n🤖 Answer: {response_obj.natural_language_answer}")
        
    except Exception as e:
        print(f"Error initializing system: {e}")
    finally:
        try:
            nl_to_sql.close_connection()
        except:
            pass


if __name__ == "__main__":
    main()