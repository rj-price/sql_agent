import mysql.connector
from mysql.connector import Error
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=settings.SQL_HOST,
            user=settings.SQL_USER,
            password=settings.SQL_PASSWORD,
            database=settings.SQL_DATABASE,
            port=settings.SQL_PORT,
        )
        return connection
    except Error as e:
        logger.error(f"Error connecting to MySQL: {e}")
        raise


def get_schema_info() -> str:
    connection = get_db_connection()
    schema_info = []
    cursor = connection.cursor()
    try:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        for (table_name,) in tables:
            schema_info.append(f"\nTable: {table_name}")
            cursor.execute(f"DESCRIBE `{table_name}`")
            columns = cursor.fetchall()
            for column in columns:
                col_name, col_type, null, key, default, extra = column
                schema_info.append(
                    f"  - {col_name}: {col_type} {'(Primary Key)' if key == 'PRI' else ''}"
                )
            cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 3")
            sample_data = cursor.fetchall()
            if sample_data:
                schema_info.append("  Sample data:")
                for row in sample_data:
                    schema_info.append(f"    {row}")
    except Error as err:
        logger.error(f"Error getting schema: {err}")
    finally:
        cursor.close()
        connection.close()
    return "\n".join(schema_info)
