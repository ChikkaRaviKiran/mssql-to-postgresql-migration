#!/usr/bin/env python3
"""
Schema export script to export MSSQL schema and generate PostgreSQL-compatible DDL.
"""

import os
import sys
import pyodbc
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Data type mapping
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

class SchemaExporter:
    """Export database schema from MSSQL and generate PostgreSQL DDL."""
    
    def __init__(self):
        """Initialize exporter."""
        self.conn = None
    
    def connect(self):
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
        
        self.conn = pyodbc.connect(conn_str)
        print("✅ Connected to MSSQL")
    
    def get_tables(self):
        """Get all tables from MSSQL."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        tables = [(row[0], row[1]) for row in cursor.fetchall()]
        cursor.close()
        return tables
    
    def get_table_columns(self, schema, table):
        """Get column definitions for a table."""
        cursor = self.conn.cursor()
        cursor.execute("""
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
        """, (schema, table))
        
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'name': row[0],
                'data_type': row[1],
                'max_length': row[2],
                'precision': row[3],
                'scale': row[4],
                'nullable': row[5] == 'YES',
                'default': row[6]
            })
        
        cursor.close()
        return columns
    
    def get_primary_key(self, schema, table):
        """Get primary key for a table."""
        cursor = self.conn.cursor()
        cursor.execute("""
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
        """, (schema, table, schema, table))
        
        pk_columns = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return pk_columns
    
    def get_foreign_keys(self, schema, table):
        """Get foreign keys for a table."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                fk.name AS FK_NAME,
                COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS COLUMN_NAME,
                OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS REF_SCHEMA,
                OBJECT_NAME(fk.referenced_object_id) AS REF_TABLE,
                COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS REF_COLUMN
            FROM sys.foreign_keys AS fk
            INNER JOIN sys.foreign_key_columns AS fkc 
                ON fk.object_id = fkc.constraint_object_id
            INNER JOIN sys.tables AS t 
                ON fk.parent_object_id = t.object_id
            INNER JOIN sys.schemas AS s 
                ON t.schema_id = s.schema_id
            WHERE s.name = ? AND t.name = ?
            ORDER BY fk.name, fkc.constraint_column_id
        """, (schema, table))
        
        foreign_keys = {}
        for row in cursor.fetchall():
            fk_name = row[0]
            if fk_name not in foreign_keys:
                foreign_keys[fk_name] = {
                    'name': fk_name,
                    'columns': [],
                    'ref_schema': row[2],
                    'ref_table': row[3],
                    'ref_columns': []
                }
            foreign_keys[fk_name]['columns'].append(row[1])
            foreign_keys[fk_name]['ref_columns'].append(row[4])
        
        cursor.close()
        return list(foreign_keys.values())
    
    def get_indexes(self, schema, table):
        """Get indexes for a table."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                i.name AS index_name,
                i.is_unique,
                COL_NAME(ic.object_id, ic.column_id) AS column_name
            FROM sys.indexes i
            INNER JOIN sys.index_columns ic 
                ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            INNER JOIN sys.tables t 
                ON i.object_id = t.object_id
            INNER JOIN sys.schemas s 
                ON t.schema_id = s.schema_id
            WHERE s.name = ? AND t.name = ?
            AND i.is_primary_key = 0
            AND i.type > 0
            ORDER BY i.name, ic.key_ordinal
        """, (schema, table))
        
        indexes = {}
        for row in cursor.fetchall():
            idx_name = row[0]
            if idx_name not in indexes:
                indexes[idx_name] = {
                    'name': idx_name,
                    'unique': row[1],
                    'columns': []
                }
            indexes[idx_name]['columns'].append(row[2])
        
        cursor.close()
        return list(indexes.values())
    
    def export_mssql_schema(self, filename='schema_mssql.sql'):
        """Export MSSQL schema to SQL file."""
        print(f"\n📝 Exporting MSSQL schema to {filename}...")
        
        tables = self.get_tables()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"-- MSSQL Schema Export\n")
            f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Database: {os.getenv('MSSQL_DATABASE')}\n")
            f.write(f"-- Total Tables: {len(tables)}\n\n")
            
            for schema, table in tables:
                f.write(f"\n-- Table: [{schema}].[{table}]\n")
                f.write("-" * 60 + "\n")
                
                columns = self.get_table_columns(schema, table)
                primary_key = self.get_primary_key(schema, table)
                foreign_keys = self.get_foreign_keys(schema, table)
                indexes = self.get_indexes(schema, table)
                
                # Table definition
                f.write(f"CREATE TABLE [{schema}].[{table}] (\n")
                
                col_defs = []
                for col in columns:
                    col_def = f"    [{col['name']}] {col['data_type']}"
                    
                    if col['data_type'] in ('varchar', 'nvarchar', 'char', 'nchar'):
                        if col['max_length'] and col['max_length'] > 0:
                            if col['max_length'] == -1:
                                col_def += "(MAX)"
                            else:
                                length = col['max_length'] // 2 if col['data_type'].startswith('n') else col['max_length']
                                col_def += f"({length})"
                    
                    if col['data_type'] in ('decimal', 'numeric') and col['precision']:
                        col_def += f"({col['precision']},{col['scale']})"
                    
                    if not col['nullable']:
                        col_def += " NOT NULL"
                    
                    if col['default']:
                        col_def += f" DEFAULT {col['default']}"
                    
                    col_defs.append(col_def)
                
                # Primary key
                if primary_key:
                    pk_cols = ', '.join([f"[{col}]" for col in primary_key])
                    col_defs.append(f"    PRIMARY KEY ({pk_cols})")
                
                f.write(',\n'.join(col_defs))
                f.write("\n);\n")
                
                # Foreign keys
                for fk in foreign_keys:
                    fk_cols = ', '.join([f"[{col}]" for col in fk['columns']])
                    ref_cols = ', '.join([f"[{col}]" for col in fk['ref_columns']])
                    f.write(f"\nALTER TABLE [{schema}].[{table}]\n")
                    f.write(f"ADD CONSTRAINT [{fk['name']}] FOREIGN KEY ({fk_cols})\n")
                    f.write(f"REFERENCES [{fk['ref_schema']}].[{fk['ref_table']}] ({ref_cols});\n")
                
                # Indexes
                for idx in indexes:
                    unique = "UNIQUE " if idx['unique'] else ""
                    idx_cols = ', '.join([f"[{col}]" for col in idx['columns']])
                    f.write(f"\nCREATE {unique}INDEX [{idx['name']}] ON [{schema}].[{table}] ({idx_cols});\n")
                
                f.write("\n")
        
        print(f"✅ MSSQL schema exported to {filename}")
    
    def export_postgresql_schema(self, filename='schema_postgresql.sql'):
        """Export PostgreSQL-compatible schema."""
        print(f"\n📝 Generating PostgreSQL schema in {filename}...")
        
        tables = self.get_tables()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"-- PostgreSQL Schema (converted from MSSQL)\n")
            f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Source Database: {os.getenv('MSSQL_DATABASE')}\n")
            f.write(f"-- Total Tables: {len(tables)}\n\n")
            
            f.write("-- Enable UUID extension\n")
            f.write('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";\n\n')
            
            # Collect all schemas
            schemas = set(schema for schema, _ in tables)
            
            # Create schemas
            for schema in sorted(schemas):
                f.write(f'CREATE SCHEMA IF NOT EXISTS "{schema}";\n')
            f.write("\n")
            
            # Create tables
            for schema, table in tables:
                f.write(f'\n-- Table: "{schema}"."{table}"\n')
                f.write("-" * 60 + "\n")
                
                columns = self.get_table_columns(schema, table)
                primary_key = self.get_primary_key(schema, table)
                
                # Table definition
                f.write(f'CREATE TABLE IF NOT EXISTS "{schema}"."{table}" (\n')
                
                col_defs = []
                for col in columns:
                    # Map data type
                    mssql_type = col['data_type'].lower()
                    pg_type = TYPE_MAPPING.get(mssql_type, mssql_type)
                    
                    # Handle precision/scale
                    if mssql_type in ('decimal', 'numeric') and col['precision']:
                        pg_type = f"numeric({col['precision']},{col['scale'] if col['scale'] else 0})"
                    
                    col_def = f'    "{col["name"]}" {pg_type}'
                    
                    if not col['nullable']:
                        col_def += " NOT NULL"
                    
                    col_defs.append(col_def)
                
                # Primary key
                if primary_key:
                    pk_cols = ', '.join([f'"{col}"' for col in primary_key])
                    col_defs.append(f"    PRIMARY KEY ({pk_cols})")
                
                f.write(',\n'.join(col_defs))
                f.write("\n);\n")
        
            # Foreign keys (in separate file for easier management)
            fk_filename = filename.replace('.sql', '_fkeys.sql')
            with open(fk_filename, 'w', encoding='utf-8') as fk_file:
                fk_file.write(f"-- PostgreSQL Foreign Keys\n")
                fk_file.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for schema, table in tables:
                    foreign_keys = self.get_foreign_keys(schema, table)
                    
                    for fk in foreign_keys:
                        fk_cols = ', '.join([f'"{col}"' for col in fk['columns']])
                        ref_cols = ', '.join([f'"{col}"' for col in fk['ref_columns']])
                        fk_name = f"{table}_{fk['name']}"
                        
                        fk_file.write(f'ALTER TABLE "{schema}"."{table}"\n')
                        fk_file.write(f'ADD CONSTRAINT "{fk_name}" FOREIGN KEY ({fk_cols})\n')
                        fk_file.write(f'REFERENCES "{fk["ref_schema"]}"."{fk["ref_table"]}" ({ref_cols});\n\n')
            
            # Indexes (in separate file)
            idx_filename = filename.replace('.sql', '_indexes.sql')
            with open(idx_filename, 'w', encoding='utf-8') as idx_file:
                idx_file.write(f"-- PostgreSQL Indexes\n")
                idx_file.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for schema, table in tables:
                    indexes = self.get_indexes(schema, table)
                    
                    for idx in indexes:
                        unique = "UNIQUE " if idx['unique'] else ""
                        idx_cols = ', '.join([f'"{col}"' for col in idx['columns']])
                        idx_name = f"{table}_{idx['name']}"
                        
                        idx_file.write(f'CREATE {unique}INDEX IF NOT EXISTS "{idx_name}" ')
                        idx_file.write(f'ON "{schema}"."{table}" ({idx_cols});\n')
        
        print(f"✅ PostgreSQL schema exported to {filename}")
        print(f"✅ Foreign keys exported to {fk_filename}")
        print(f"✅ Indexes exported to {idx_filename}")
    
    def export_all(self):
        """Export both MSSQL and PostgreSQL schemas."""
        print("\n" + "="*60)
        print("Schema Export")
        print("="*60)
        
        self.connect()
        self.export_mssql_schema()
        self.export_postgresql_schema()
        
        if self.conn:
            self.conn.close()
        
        print("\n✅ Schema export completed!")

def main():
    """Main entry point."""
    exporter = SchemaExporter()
    
    try:
        exporter.export_all()
        return 0
    except Exception as e:
        print(f"\n❌ Schema export failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
