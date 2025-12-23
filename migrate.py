#!/usr/bin/env python3
"""
Main migration script to migrate data from Azure SQL Server to PostgreSQL.
"""

import os
import sys
import argparse
import logging
import pyodbc
import psycopg2
import psycopg2.extras
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)

error_logger = logging.getLogger('errors')
error_handler = logging.FileHandler('migration_errors.log')
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
error_logger.addHandler(error_handler)
error_logger.setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

# Data type mapping from MSSQL to PostgreSQL
TYPE_MAPPING = {
    'datetime': 'timestamptz',
    'datetime2': 'timestamptz',
    'smalldatetime': 'timestamptz',
    'date': 'date',
    'time': 'time',
    'nvarchar': 'text',
    'varchar': 'text',
    'nchar': 'text',
    'char': 'text',
    'text': 'text',
    'ntext': 'text',
    'bit': 'boolean',
    'uniqueidentifier': 'uuid',
    'tinyint': 'smallint',
    'smallint': 'smallint',
    'int': 'integer',
    'bigint': 'bigint',
    'decimal': 'numeric',
    'numeric': 'numeric',
    'money': 'numeric(19,4)',
    'smallmoney': 'numeric(10,4)',
    'float': 'double precision',
    'real': 'real',
    'image': 'bytea',
    'varbinary': 'bytea',
    'binary': 'bytea',
    'xml': 'xml',
}

class DatabaseMigration:
    """Handle database migration from MSSQL to PostgreSQL."""
    
    def __init__(self, batch_size=1000, parallel_workers=1, drop_existing=False):
        """Initialize migration with configuration."""
        self.batch_size = batch_size
        self.parallel_workers = parallel_workers
        self.drop_existing = drop_existing
        self.mssql_conn = None
        self.pgsql_conn = None
        self.migration_stats = {
            'total_tables': 0,
            'successful_tables': 0,
            'failed_tables': 0,
            'total_rows': 0,
            'start_time': None,
            'end_time': None
        }
    
    def connect_mssql(self) -> pyodbc.Connection:
        """Connect to Azure SQL Server."""
        try:
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
            
            logger.info(f"Connecting to MSSQL: {server}/{database}")
            self.mssql_conn = pyodbc.connect(conn_str)
            logger.info("✅ Connected to MSSQL")
            return self.mssql_conn
            
        except Exception as e:
            logger.error(f"Failed to connect to MSSQL: {e}")
            error_logger.error(f"MSSQL connection error: {e}", exc_info=True)
            raise
    
    def connect_postgresql(self) -> psycopg2.extensions.connection:
        """Connect to PostgreSQL."""
        try:
            host = os.getenv('PGSQL_HOST')
            port = os.getenv('PGSQL_PORT', '5432')
            database = os.getenv('PGSQL_DATABASE')
            username = os.getenv('PGSQL_USER')
            password = os.getenv('PGSQL_PASSWORD')
            
            logger.info(f"Connecting to PostgreSQL: {host}/{database}")
            self.pgsql_conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=username,
                password=password,
                connect_timeout=30
            )
            self.pgsql_conn.autocommit = False
            logger.info("✅ Connected to PostgreSQL")
            return self.pgsql_conn
            
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            error_logger.error(f"PostgreSQL connection error: {e}", exc_info=True)
            raise
    
    def get_tables(self, include_tables: Optional[List[str]] = None, 
                   exclude_tables: Optional[List[str]] = None) -> List[Tuple[str, str]]:
        """Get list of tables to migrate from MSSQL."""
        cursor = self.mssql_conn.cursor()
        
        query = """
            SELECT TABLE_SCHEMA, TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
        """
        
        if include_tables:
            placeholders = ','.join(['?' for _ in include_tables])
            query += f" AND TABLE_NAME IN ({placeholders})"
            cursor.execute(query, include_tables)
        else:
            cursor.execute(query)
        
        tables = [(row[0], row[1]) for row in cursor.fetchall()]
        
        if exclude_tables:
            tables = [(schema, table) for schema, table in tables 
                     if table not in exclude_tables]
        
        cursor.close()
        return tables
    
    def get_table_schema(self, schema: str, table: str) -> List[Dict]:
        """Get column definitions for a table."""
        cursor = self.mssql_conn.cursor()
        
        query = """
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """
        
        cursor.execute(query, (schema, table))
        
        columns = []
        for row in cursor.fetchall():
            col_name = row[0]
            data_type = row[1].lower()
            max_length = row[2]
            precision = row[3]
            scale = row[4]
            is_nullable = row[5] == 'YES'
            default_value = row[6]
            
            # Map data type
            pg_type = TYPE_MAPPING.get(data_type, data_type)
            
            # Handle types with precision/scale
            if data_type in ('decimal', 'numeric') and precision:
                pg_type = f"numeric({precision},{scale if scale else 0})"
            
            columns.append({
                'name': col_name,
                'mssql_type': data_type,
                'pg_type': pg_type,
                'nullable': is_nullable,
                'default': default_value
            })
        
        cursor.close()
        return columns
    
    def get_primary_key(self, schema: str, table: str) -> Optional[List[str]]:
        """Get primary key columns for a table."""
        cursor = self.mssql_conn.cursor()
        
        query = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            AND CONSTRAINT_NAME IN (
                SELECT CONSTRAINT_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                AND CONSTRAINT_TYPE = 'PRIMARY KEY'
            )
            ORDER BY ORDINAL_POSITION
        """
        
        cursor.execute(query, (schema, table, schema, table))
        pk_columns = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        return pk_columns if pk_columns else None
    
    def get_indexes(self, schema: str, table: str) -> List[Dict]:
        """Get indexes for a table."""
        cursor = self.mssql_conn.cursor()
        
        query = """
            SELECT 
                i.name AS index_name,
                i.is_unique,
                COL_NAME(ic.object_id, ic.column_id) AS column_name
            FROM sys.indexes i
            INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            INNER JOIN sys.tables t ON i.object_id = t.object_id
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = ? AND t.name = ?
            AND i.is_primary_key = 0
            AND i.type > 0
            ORDER BY i.name, ic.key_ordinal
        """
        
        cursor.execute(query, (schema, table))
        
        indexes = {}
        for row in cursor.fetchall():
            idx_name = row[0]
            is_unique = row[1]
            col_name = row[2]
            
            if idx_name not in indexes:
                indexes[idx_name] = {
                    'name': idx_name,
                    'unique': is_unique,
                    'columns': []
                }
            indexes[idx_name]['columns'].append(col_name)
        
        cursor.close()
        return list(indexes.values())
    
    def create_schema(self, schema: str):
        """Create schema in PostgreSQL if it doesn't exist."""
        cursor = self.pgsql_conn.cursor()
        try:
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            self.pgsql_conn.commit()
            logger.info(f"Created schema: {schema}")
        except Exception as e:
            self.pgsql_conn.rollback()
            logger.warning(f"Schema creation warning: {e}")
        finally:
            cursor.close()
    
    def create_table(self, schema: str, table: str, columns: List[Dict], 
                     primary_key: Optional[List[str]] = None):
        """Create table in PostgreSQL."""
        cursor = self.pgsql_conn.cursor()
        
        try:
            # Drop if exists and flag is set
            if self.drop_existing:
                cursor.execute(f'DROP TABLE IF EXISTS "{schema}"."{table}" CASCADE')
                logger.info(f"Dropped existing table: {schema}.{table}")
            
            # Build CREATE TABLE statement
            col_defs = []
            for col in columns:
                col_def = f'"{col["name"]}" {col["pg_type"]}'
                if not col['nullable']:
                    col_def += ' NOT NULL'
                col_defs.append(col_def)
            
            # Add primary key constraint
            if primary_key:
                pk_cols = ', '.join([f'"{col}"' for col in primary_key])
                col_defs.append(f'PRIMARY KEY ({pk_cols})')
            
            create_sql = f'''
                CREATE TABLE IF NOT EXISTS "{schema}"."{table}" (
                    {', '.join(col_defs)}
                )
            '''
            
            cursor.execute(create_sql)
            self.pgsql_conn.commit()
            logger.info(f"Created table: {schema}.{table}")
            
        except Exception as e:
            self.pgsql_conn.rollback()
            logger.error(f"Failed to create table {schema}.{table}: {e}")
            error_logger.error(f"Table creation error for {schema}.{table}: {e}", exc_info=True)
            raise
        finally:
            cursor.close()
    
    def migrate_table_data(self, schema: str, table: str, columns: List[Dict]) -> int:
        """Migrate data from MSSQL table to PostgreSQL table."""
        mssql_cursor = self.mssql_conn.cursor()
        pg_cursor = self.pgsql_conn.cursor()
        
        try:
            # Get total row count
            mssql_cursor.execute(f'SELECT COUNT(*) FROM [{schema}].[{table}]')
            total_rows = mssql_cursor.fetchone()[0]
            
            if total_rows == 0:
                logger.info(f"Table {schema}.{table} is empty, skipping data migration")
                return 0
            
            # Prepare column names
            col_names = [col['name'] for col in columns]
            col_list = ', '.join([f'[{col}]' for col in col_names])
            pg_col_list = ', '.join([f'"{col}"' for col in col_names])
            placeholders = ', '.join(['%s' for _ in col_names])
            
            # Fetch and insert in batches
            insert_sql = f'INSERT INTO "{schema}"."{table}" ({pg_col_list}) VALUES ({placeholders})'
            
            rows_migrated = 0
            batch = []
            
            # Query all data
            select_sql = f'SELECT {col_list} FROM [{schema}].[{table}]'
            mssql_cursor.execute(select_sql)
            
            # Progress bar
            with tqdm(total=total_rows, desc=f"Migrating {schema}.{table}", unit="rows") as pbar:
                while True:
                    rows = mssql_cursor.fetchmany(self.batch_size)
                    if not rows:
                        break
                    
                    # Convert rows to list of tuples
                    batch = [tuple(row) for row in rows]
                    
                    # Insert batch using execute_batch for performance
                    psycopg2.extras.execute_batch(pg_cursor, insert_sql, batch)
                    self.pgsql_conn.commit()
                    
                    rows_migrated += len(batch)
                    pbar.update(len(batch))
            
            logger.info(f"✅ Migrated {rows_migrated} rows for {schema}.{table}")
            return rows_migrated
            
        except Exception as e:
            self.pgsql_conn.rollback()
            logger.error(f"Failed to migrate data for {schema}.{table}: {e}")
            error_logger.error(f"Data migration error for {schema}.{table}: {e}", exc_info=True)
            raise
        finally:
            mssql_cursor.close()
            pg_cursor.close()
    
    def create_indexes(self, schema: str, table: str, indexes: List[Dict]):
        """Create indexes on PostgreSQL table."""
        cursor = self.pgsql_conn.cursor()
        
        for idx in indexes:
            try:
                idx_name = f"{table}_{idx['name']}"
                col_list = ', '.join([f'"{col}"' for col in idx['columns']])
                unique = 'UNIQUE' if idx['unique'] else ''
                
                create_idx_sql = f'''
                    CREATE {unique} INDEX IF NOT EXISTS "{idx_name}" 
                    ON "{schema}"."{table}" ({col_list})
                '''
                
                cursor.execute(create_idx_sql)
                self.pgsql_conn.commit()
                logger.info(f"Created index: {idx_name} on {schema}.{table}")
                
            except Exception as e:
                self.pgsql_conn.rollback()
                logger.warning(f"Failed to create index {idx['name']} on {schema}.{table}: {e}")
                error_logger.error(f"Index creation error: {e}", exc_info=True)
        
        cursor.close()
    
    def validate_table(self, schema: str, table: str) -> bool:
        """Validate row counts match between source and target."""
        try:
            mssql_cursor = self.mssql_conn.cursor()
            pg_cursor = self.pgsql_conn.cursor()
            
            # Get MSSQL count
            mssql_cursor.execute(f'SELECT COUNT(*) FROM [{schema}].[{table}]')
            mssql_count = mssql_cursor.fetchone()[0]
            
            # Get PostgreSQL count
            pg_cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
            pg_count = pg_cursor.fetchone()[0]
            
            mssql_cursor.close()
            pg_cursor.close()
            
            if mssql_count == pg_count:
                logger.info(f"✅ Validation passed for {schema}.{table}: {mssql_count} rows")
                return True
            else:
                logger.error(f"❌ Validation failed for {schema}.{table}: MSSQL={mssql_count}, PostgreSQL={pg_count}")
                return False
                
        except Exception as e:
            logger.error(f"Validation error for {schema}.{table}: {e}")
            error_logger.error(f"Validation error: {e}", exc_info=True)
            return False
    
    def migrate_table(self, schema: str, table: str) -> bool:
        """Migrate a single table with full process."""
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Starting migration: {schema}.{table}")
            logger.info(f"{'='*60}")
            
            # Get schema
            columns = self.get_table_schema(schema, table)
            primary_key = self.get_primary_key(schema, table)
            indexes = self.get_indexes(schema, table)
            
            # Create schema if needed
            self.create_schema(schema)
            
            # Create table
            self.create_table(schema, table, columns, primary_key)
            
            # Migrate data
            rows_migrated = self.migrate_table_data(schema, table, columns)
            self.migration_stats['total_rows'] += rows_migrated
            
            # Create indexes
            if indexes:
                logger.info(f"Creating {len(indexes)} indexes for {schema}.{table}")
                self.create_indexes(schema, table, indexes)
            
            # Validate
            if self.validate_table(schema, table):
                self.migration_stats['successful_tables'] += 1
                logger.info(f"✅ Successfully migrated: {schema}.{table}")
                return True
            else:
                self.migration_stats['failed_tables'] += 1
                logger.error(f"❌ Validation failed: {schema}.{table}")
                return False
                
        except Exception as e:
            self.migration_stats['failed_tables'] += 1
            logger.error(f"❌ Failed to migrate {schema}.{table}: {e}")
            error_logger.error(f"Table migration error for {schema}.{table}: {e}", exc_info=True)
            return False
    
    def migrate_all(self, include_tables: Optional[List[str]] = None,
                   exclude_tables: Optional[List[str]] = None):
        """Migrate all tables."""
        try:
            self.migration_stats['start_time'] = datetime.now()
            
            # Connect to databases
            self.connect_mssql()
            self.connect_postgresql()
            
            # Get tables to migrate
            tables = self.get_tables(include_tables, exclude_tables)
            self.migration_stats['total_tables'] = len(tables)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Found {len(tables)} tables to migrate")
            logger.info(f"{'='*60}\n")
            
            if self.parallel_workers > 1:
                # Parallel migration
                logger.info(f"Using {self.parallel_workers} parallel workers")
                with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                    futures = {
                        executor.submit(self.migrate_table, schema, table): (schema, table)
                        for schema, table in tables
                    }
                    
                    for future in as_completed(futures):
                        schema, table = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"Exception in parallel migration of {schema}.{table}: {e}")
            else:
                # Sequential migration
                for schema, table in tables:
                    self.migrate_table(schema, table)
            
            self.migration_stats['end_time'] = datetime.now()
            self.print_summary()
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            error_logger.error(f"Migration error: {e}", exc_info=True)
            raise
        finally:
            # Close connections
            if self.mssql_conn:
                self.mssql_conn.close()
            if self.pgsql_conn:
                self.pgsql_conn.close()
    
    def print_summary(self):
        """Print migration summary."""
        duration = self.migration_stats['end_time'] - self.migration_stats['start_time']
        
        logger.info(f"\n{'='*60}")
        logger.info("Migration Summary")
        logger.info(f"{'='*60}")
        logger.info(f"Total tables: {self.migration_stats['total_tables']}")
        logger.info(f"Successful: {self.migration_stats['successful_tables']}")
        logger.info(f"Failed: {self.migration_stats['failed_tables']}")
        logger.info(f"Total rows migrated: {self.migration_stats['total_rows']:,}")
        logger.info(f"Duration: {duration}")
        logger.info(f"{'='*60}\n")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Migrate data from Azure SQL Server to PostgreSQL',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=int(os.getenv('BATCH_SIZE', 1000)),
        help='Number of rows per batch (default: 1000)'
    )
    
    parser.add_argument(
        '--tables',
        type=str,
        help='Comma-separated list of specific tables to migrate'
    )
    
    parser.add_argument(
        '--exclude-tables',
        type=str,
        help='Comma-separated list of tables to exclude'
    )
    
    parser.add_argument(
        '--parallel',
        type=int,
        default=int(os.getenv('PARALLEL_WORKERS', 1)),
        help='Number of parallel workers (default: 1)'
    )
    
    parser.add_argument(
        '--drop-existing',
        action='store_true',
        help='Drop existing tables before migration'
    )
    
    args = parser.parse_args()
    
    # Parse table lists
    include_tables = [t.strip() for t in args.tables.split(',')] if args.tables else None
    exclude_tables = [t.strip() for t in args.exclude_tables.split(',')] if args.exclude_tables else None
    
    # Create migration instance
    migration = DatabaseMigration(
        batch_size=args.batch_size,
        parallel_workers=args.parallel,
        drop_existing=args.drop_existing
    )
    
    # Run migration
    try:
        logger.info("🚀 Starting MSSQL to PostgreSQL Migration")
        migration.migrate_all(include_tables, exclude_tables)
        logger.info("✅ Migration completed successfully!")
        return 0
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
