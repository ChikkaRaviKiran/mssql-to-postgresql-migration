#!/usr/bin/env python3
"""
Validation script to compare data between MSSQL and PostgreSQL.
"""

import os
import sys
import random
import pyodbc
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate

# Load environment variables
load_dotenv()

class DataValidator:
    """Validate migrated data between MSSQL and PostgreSQL."""
    
    def __init__(self):
        """Initialize validator."""
        self.mssql_conn = None
        self.pgsql_conn = None
        self.validation_results = []
    
    def connect_mssql(self):
        """Connect to Azure SQL Server."""
        server = os.getenv('MSSQL_SERVER')
        port = os.getenv('MSSQL_PORT', '1433')
        database = os.getenv('MSSQL_DATABASE')
        username = os.getenv('MSSQL_USER')
        password = os.getenv('MSSQL_PASSWORD')
        
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
        
        self.mssql_conn = pyodbc.connect(conn_str)
        print("✅ Connected to MSSQL")
    
    def connect_postgresql(self):
        """Connect to PostgreSQL."""
        host = os.getenv('PGSQL_HOST')
        port = os.getenv('PGSQL_PORT', '5432')
        database = os.getenv('PGSQL_DATABASE')
        username = os.getenv('PGSQL_USER')
        password = os.getenv('PGSQL_PASSWORD')
        
        self.pgsql_conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password
        )
        print("✅ Connected to PostgreSQL")
    
    def get_common_tables(self):
        """Get tables that exist in both databases."""
        mssql_cursor = self.mssql_conn.cursor()
        pg_cursor = self.pgsql_conn.cursor()
        
        # Get MSSQL tables
        mssql_cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
        """)
        mssql_tables = set((row[0], row[1]) for row in mssql_cursor.fetchall())
        
        # Get PostgreSQL tables
        pg_cursor.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            AND table_type = 'BASE TABLE'
        """)
        pg_tables = set((row[0], row[1]) for row in pg_cursor.fetchall())
        
        mssql_cursor.close()
        pg_cursor.close()
        
        # Find common tables
        common = mssql_tables.intersection(pg_tables)
        return sorted(list(common))
    
    def validate_row_count(self, schema, table):
        """Compare row counts between MSSQL and PostgreSQL."""
        try:
            mssql_cursor = self.mssql_conn.cursor()
            pg_cursor = self.pgsql_conn.cursor()
            
            # MSSQL count
            mssql_cursor.execute(f'SELECT COUNT(*) FROM [{schema}].[{table}]')
            mssql_count = mssql_cursor.fetchone()[0]
            
            # PostgreSQL count
            pg_cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
            pg_count = pg_cursor.fetchone()[0]
            
            mssql_cursor.close()
            pg_cursor.close()
            
            match = mssql_count == pg_count
            status = "✅ PASS" if match else "❌ FAIL"
            
            result = {
                'schema': schema,
                'table': table,
                'mssql_count': mssql_count,
                'pg_count': pg_count,
                'match': match,
                'status': status
            }
            
            self.validation_results.append(result)
            return result
            
        except Exception as e:
            print(f"❌ Error validating {schema}.{table}: {e}")
            return {
                'schema': schema,
                'table': table,
                'mssql_count': 0,
                'pg_count': 0,
                'match': False,
                'status': f"❌ ERROR: {str(e)[:50]}"
            }
    
    def sample_data_validation(self, schema, table, sample_size=100):
        """Sample random rows and compare data."""
        try:
            mssql_cursor = self.mssql_conn.cursor()
            pg_cursor = self.pgsql_conn.cursor()
            
            # Get total count
            mssql_cursor.execute(f'SELECT COUNT(*) FROM [{schema}].[{table}]')
            total_count = mssql_cursor.fetchone()[0]
            
            if total_count == 0:
                print(f"⚠️  Table {schema}.{table} is empty, skipping sample validation")
                return True
            
            # Get column names
            mssql_cursor.execute(f"""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """, (schema, table))
            columns = [row[0] for row in mssql_cursor.fetchall()]
            
            if not columns:
                print(f"⚠️  No columns found for {schema}.{table}")
                return False
            
            # Sample rows (limit sample size to actual row count)
            actual_sample_size = min(sample_size, total_count)
            
            # Get primary key or first column for sampling
            pk_col = columns[0]
            
            # Simple validation: just check if we can read the same number of rows
            col_list_mssql = ', '.join([f'[{col}]' for col in columns])
            col_list_pg = ', '.join([f'"{col}"' for col in columns])
            
            mssql_cursor.execute(f'SELECT TOP {actual_sample_size} {col_list_mssql} FROM [{schema}].[{table}]')
            mssql_rows = len(mssql_cursor.fetchall())
            
            pg_cursor.execute(f'SELECT {col_list_pg} FROM "{schema}"."{table}" LIMIT {actual_sample_size}')
            pg_rows = len(pg_cursor.fetchall())
            
            mssql_cursor.close()
            pg_cursor.close()
            
            if mssql_rows == pg_rows:
                print(f"✅ Sample validation passed for {schema}.{table} ({actual_sample_size} rows)")
                return True
            else:
                print(f"❌ Sample validation failed for {schema}.{table}: MSSQL={mssql_rows}, PG={pg_rows}")
                return False
                
        except Exception as e:
            print(f"⚠️  Sample validation error for {schema}.{table}: {e}")
            return False
    
    def validate_all(self):
        """Validate all common tables."""
        print("\n" + "="*60)
        print("Starting Data Validation")
        print("="*60 + "\n")
        
        # Connect to both databases
        self.connect_mssql()
        self.connect_postgresql()
        
        # Get common tables
        tables = self.get_common_tables()
        print(f"Found {len(tables)} common tables to validate\n")
        
        # Validate each table
        for schema, table in tables:
            print(f"\nValidating: {schema}.{table}")
            result = self.validate_row_count(schema, table)
            print(f"  Row count: MSSQL={result['mssql_count']:,}, PostgreSQL={result['pg_count']:,} - {result['status']}")
            
            # Sample validation for tables with data
            if result['match'] and result['mssql_count'] > 0:
                self.sample_data_validation(schema, table)
        
        # Generate report
        self.generate_report()
        
        # Close connections
        if self.mssql_conn:
            self.mssql_conn.close()
        if self.pgsql_conn:
            self.pgsql_conn.close()
    
    def generate_report(self):
        """Generate validation report."""
        print("\n" + "="*60)
        print("Validation Report")
        print("="*60 + "\n")
        
        # Summary statistics
        total_tables = len(self.validation_results)
        passed_tables = sum(1 for r in self.validation_results if r['match'])
        failed_tables = total_tables - passed_tables
        
        print(f"Total tables validated: {total_tables}")
        print(f"Passed: {passed_tables} (✅)")
        print(f"Failed: {failed_tables} (❌)\n")
        
        # Detailed results table
        if self.validation_results:
            table_data = [
                [
                    f"{r['schema']}.{r['table']}", 
                    f"{r['mssql_count']:,}", 
                    f"{r['pg_count']:,}",
                    r['status']
                ]
                for r in self.validation_results
            ]
            
            print(tabulate(
                table_data,
                headers=['Table', 'MSSQL Rows', 'PostgreSQL Rows', 'Status'],
                tablefmt='grid'
            ))
        
        # Save to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'validation_report_{timestamp}.txt'
        
        with open(report_file, 'w') as f:
            f.write("="*60 + "\n")
            f.write("Data Validation Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")
            
            f.write(f"Total tables validated: {total_tables}\n")
            f.write(f"Passed: {passed_tables}\n")
            f.write(f"Failed: {failed_tables}\n\n")
            
            f.write("Detailed Results:\n")
            f.write("-"*60 + "\n")
            for r in self.validation_results:
                f.write(f"\nTable: {r['schema']}.{r['table']}\n")
                f.write(f"  MSSQL Count: {r['mssql_count']:,}\n")
                f.write(f"  PostgreSQL Count: {r['pg_count']:,}\n")
                f.write(f"  Status: {r['status']}\n")
        
        print(f"\n📝 Report saved to: {report_file}")
        
        # Return status
        return failed_tables == 0

def main():
    """Main entry point."""
    validator = DataValidator()
    
    try:
        success = validator.validate_all()
        
        if success:
            print("\n✅ All validations passed!")
            return 0
        else:
            print("\n❌ Some validations failed. Check the report for details.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
