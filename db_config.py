import pyodbc

def get_sql_server_connection():
    conn = pyodbc.connect(
        r'DRIVER={ODBC Driver 17 for SQL Server};'
        r'SERVER=EKSRV\SQLEXPRESS;'
        r'DATABASE=ArrowAnalysis;'
        r'UID=ilyda;'
        r'PWD=6726200;'
    )
    return conn
