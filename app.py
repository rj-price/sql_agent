import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

from sql_agent import NaturalLanguageToSQL, DatabaseConfig, AgentResponse

# --- Page Configuration ---
st.set_page_config(
    page_title="SQL Agent",
    page_icon="🤖",
    layout="wide"
)

# --- Load Environment Variables ---
load_dotenv()

# --- Caching the Agent Initialization ---
@st.cache_resource
def get_sql_agent():
    """Initializes and returns the NaturalLanguageToSQL agent."""
    try:
        db_config = DatabaseConfig(
            host=os.getenv("SQL_HOST"),
            user=os.getenv("SQL_USER"),
            password=os.getenv("SQL_PASSWORD"),
            database=os.getenv("SQL_DATABASE"),
            port=int(os.getenv("SQL_PORT", 3306))
        )
        gemini_api_key = os.getenv("GOOGLE_API_KEY")

        if not all([db_config.host, db_config.user, db_config.password, db_config.database, gemini_api_key]):
            st.error("Missing database configuration or Google API key. Please set them in your environment.")
            return None

        agent = NaturalLanguageToSQL(
            db_config=db_config,
            gemini_api_key=gemini_api_key,
            debug=False # Debug is off for the Streamlit app
        )
        return agent
    except Exception as e:
        st.error(f"Failed to initialize the SQL Agent: {e}")
        return None

# --- Main Application ---
st.title("SQL Agent")
st.markdown("Ask questions about your database in plain English, and get answers, the SQL query, and insights.")

agent = get_sql_agent()

if agent:
    # User input
    if question := st.chat_input("What would you like to know?"):
        with st.chat_message("user"):
            st.markdown(question)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response_obj: AgentResponse = agent.ask_question(question)

                # Create tabs based on whether a review was performed
                tab_names = ["Answer", "SQL Query & Results"]
                if response_obj.review:
                    tab_names.append("Review Info")
                
                tab1, tab2, *extra_tabs = st.tabs(tab_names)

                with tab1:
                    st.markdown(response_obj.natural_language_answer)

                with tab2:
                    st.subheader("Executed SQL Query")
                    st.code(response_obj.query_result.sql_query, language="sql")
                    st.subheader("Query Results")
                    if response_obj.query_result.success and response_obj.query_result.data:
                        df = pd.DataFrame(response_obj.query_result.data)
                        st.dataframe(df, use_container_width=True)
                    elif response_obj.query_result.success:
                        st.info("The query ran successfully but returned no data.")
                    else:
                        st.error(f"The query failed with the following error:\n\n{response_obj.query_result.error_message}")

                if response_obj.review and extra_tabs:
                    with extra_tabs[0]:
                        st.subheader("SQL Query Review")
                        st.info("The initial query failed and was reviewed for correctness.")
                        st.markdown(response_obj.review.review_text)
                        if response_obj.review.corrected_query:
                            st.subheader("Corrected Query")
                            st.code(response_obj.review.corrected_query, language="sql")
else:
    st.warning("The SQL Agent could not be initialized. Please check your configuration.")