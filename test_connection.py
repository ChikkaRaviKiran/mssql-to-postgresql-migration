#!/usr/bin/env python3
"""
Test connectivity to both MSSQL and PostgreSQL databases.
"""

import os
import sys
import pyodbc
import psycopg2
from dotenv import load_dotenv
from tabulate import tabulate

# Load environment variables
load_dotenv()

def test_mssql_connection():
    """Test connection to Azure SQL Server."""
    print("\n" + "="*60)
    print("Testing Azure SQL Server Connection")
    print("="*60)
    
    try:
        server = os.getenv('MSSQL_SERVER')
        port = os.getenv('MSSQL_PORT', '1433')
        database = os.getenv('MSSQL_DATABASE')
        username = os.getenv('MSSQL_USER')
        password = os.getenv('MSSQL_PASSWORD')
        
        if not all([server, database, username, password]):
            print("❌ Missing MSSQL configuration in .env file")
            return False
        
        print(f"📡 Connecting to {server}:{port}/{database}...")
        
        conn_str = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={server},{port};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
        )
        
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Get SQL Server version
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"✅ Connected successfully!")
        print(f"📌 Version: {version.split('-')[0].strip()}")
        
        # Get table count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
        """)
        table_count = cursor.fetchone()[0]
        print(f"📊 Total tables: {table_count}")
        
        # List sample tables
        cursor.execute("""
            SELECT TOP 10 TABLE_SCHEMA, TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"\n📋 Sample tables:")
            table_data = [[t[0], t[1]] for t in tables]
            print(tabulate(table_data, headers=['Schema', 'Table'], tablefmt='grid'))
        
        cursor.close()
        conn.close()
        return True
        
    except pyodbc.Error as e:
        print(f"❌ Connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_postgresql_connection():
    """Test connection to PostgreSQL."""
    print("\n" + "="*60)
    print("Testing PostgreSQL Connection")
    print("="*60)
    
    try:
        host = os.getenv('PGSQL_HOST')
        port = os.getenv('PGSQL_PORT', '5432')
        database = os.getenv('PGSQL_DATABASE')
        username = os.getenv('PGSQL_USER')
        password = os.getenv('PGSQL_PASSWORD')
        
        if not all([host, database, username, password]):
            print("❌ Missing PostgreSQL configuration in .env file")
            return False
        
        print(f"📡 Connecting to {host}:{port}/{database}...")
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password,
            connect_timeout=30
        )
        cursor = conn.cursor()
        
        # Get PostgreSQL version
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✅ Connected successfully!")
        print(f"📌 Version: {version.split('(')[0].strip()}")
        
        # Check for uuid-ossp extension
        cursor.execute("""
            SELECT COUNT(*) 
            FROM pg_extension 
            WHERE extname = 'uuid-ossp'
        """)
        has_uuid = cursor.fetchone()[0] > 0
        
        if has_uuid:
            print("✅ uuid-ossp extension: Installed")
        else:
            print("⚠️  uuid-ossp extension: Not installed (required for UUID support)")
            print("   Run: CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        
        # Get table count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            AND table_type = 'BASE TABLE'
        """)
        table_count = cursor.fetchone()[0]
        print(f"📊 Total tables: {table_count}")
        
        # List sample tables
        cursor.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
            LIMIT 10
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"\n📋 Sample tables:")
            table_data = [[t[0], t[1]] for t in tables]
            print(tabulate(table_data, headers=['Schema', 'Table'], tablefmt='grid'))
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main function to test both connections."""
    print("\n🚀 Database Connection Test")
    
    mssql_ok = test_mssql_connection()
    pgsql_ok = test_postgresql_connection()
    
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    
    results = [
        ["Azure SQL Server", "✅ Connected" if mssql_ok else "❌ Failed"],
        ["PostgreSQL", "✅ Connected" if pgsql_ok else "❌ Failed"]
    ]
    print(tabulate(results, headers=['Database', 'Status'], tablefmt='grid'))
    
    if mssql_ok and pgsql_ok:
        print("\n✅ All connections successful! Ready to migrate.")
        return 0
    else:
        print("\n❌ Some connections failed. Please check your .env configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
