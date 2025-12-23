#!/usr/bin/env python3
"""
Rollback script to remove migrated tables from PostgreSQL.
"""

import os
import sys
import subprocess
from datetime import datetime
import psycopg2
from dotenv import load_dotenv
from tabulate import tabulate

# Load environment variables
load_dotenv()

class DatabaseRollback:
    """Handle rollback of migrated tables in PostgreSQL."""
    
    def __init__(self):
        """Initialize rollback handler."""
        self.conn = None
    
    def connect(self):
        """Connect to PostgreSQL."""
        host = os.getenv('PGSQL_HOST')
        port = os.getenv('PGSQL_PORT', '5432')
        database = os.getenv('PGSQL_DATABASE')
        username = os.getenv('PGSQL_USER')
        password = os.getenv('PGSQL_PASSWORD')
        
        self.conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password
        )
        print("✅ Connected to PostgreSQL")
    
    def get_tables(self):
        """Get all tables in PostgreSQL (excluding system tables)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT table_schema, table_name, 
                   pg_size_pretty(pg_total_relation_size('"' || table_schema || '"."' || table_name || '"')) as size
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            AND table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name
        """)
        
        tables = []
        for row in cursor.fetchall():
            tables.append({
                'schema': row[0],
                'table': row[1],
                'size': row[2]
            })
        
        cursor.close()
        return tables
    
    def create_backup(self, backup_file=None):
        """Create a backup of PostgreSQL database using pg_dump."""
        if backup_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f'backup_{timestamp}.sql'
        
        print(f"\n📦 Creating backup: {backup_file}")
        
        host = os.getenv('PGSQL_HOST')
        port = os.getenv('PGSQL_PORT', '5432')
        database = os.getenv('PGSQL_DATABASE')
        username = os.getenv('PGSQL_USER')
        
        # Set password in environment for pg_dump
        env = os.environ.copy()
        env['PGPASSWORD'] = os.getenv('PGSQL_PASSWORD')
        
        try:
            cmd = [
                'pg_dump',
                '-h', host,
                '-p', port,
                '-U', username,
                '-d', database,
                '-f', backup_file,
                '--no-owner',
                '--no-privileges'
            ]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Backup created successfully: {backup_file}")
                return backup_file
            else:
                print(f"❌ Backup failed: {result.stderr}")
                return None
                
        except FileNotFoundError:
            print("⚠️  pg_dump not found. Backup skipped.")
            print("   Install PostgreSQL client tools to enable backup.")
            return None
        except Exception as e:
            print(f"❌ Backup error: {e}")
            return None
    
    def drop_table(self, schema, table):
        """Drop a specific table."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(f'DROP TABLE IF EXISTS "{schema}"."{table}" CASCADE')
            self.conn.commit()
            print(f"✅ Dropped table: {schema}.{table}")
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Failed to drop {schema}.{table}: {e}")
            return False
        finally:
            cursor.close()
    
    def drop_schema(self, schema):
        """Drop an entire schema."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            self.conn.commit()
            print(f"✅ Dropped schema: {schema}")
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Failed to drop schema {schema}: {e}")
            return False
        finally:
            cursor.close()
    
    def interactive_rollback(self):
        """Interactive rollback with user selection."""
        print("\n" + "="*60)
        print("PostgreSQL Rollback Tool")
        print("="*60)
        
        # Connect
        self.connect()
        
        # Get tables
        tables = self.get_tables()
        
        if not tables:
            print("\n⚠️  No tables found in PostgreSQL database.")
            return
        
        print(f"\nFound {len(tables)} tables in PostgreSQL:\n")
        
        # Display tables
        table_data = [
            [i+1, t['schema'], t['table'], t['size']]
            for i, t in enumerate(tables)
        ]
        print(tabulate(
            table_data,
            headers=['#', 'Schema', 'Table', 'Size'],
            tablefmt='grid'
        ))
        
        print("\n⚠️  WARNING: This operation cannot be undone!")
        print("\nOptions:")
        print("  1. Drop specific tables (enter comma-separated numbers)")
        print("  2. Drop all tables")
        print("  3. Drop entire schema")
        print("  4. Create backup only (no deletion)")
        print("  5. Cancel")
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == '1':
            # Drop specific tables
            table_nums = input("\nEnter table numbers (comma-separated): ").strip()
            try:
                indices = [int(n.strip()) - 1 for n in table_nums.split(',')]
                selected_tables = [tables[i] for i in indices if 0 <= i < len(tables)]
                
                if not selected_tables:
                    print("❌ No valid table numbers provided.")
                    return
                
                print(f"\nYou are about to drop {len(selected_tables)} table(s):")
                for t in selected_tables:
                    print(f"  - {t['schema']}.{t['table']}")
                
                # Create backup
                create_backup = input("\nCreate backup before dropping? (y/n): ").strip().lower()
                if create_backup == 'y':
                    self.create_backup()
                
                confirm = input("\nType 'DELETE' to confirm: ").strip()
                if confirm == 'DELETE':
                    for t in selected_tables:
                        self.drop_table(t['schema'], t['table'])
                    print("\n✅ Rollback completed!")
                else:
                    print("\n❌ Rollback cancelled.")
                    
            except (ValueError, IndexError) as e:
                print(f"❌ Invalid input: {e}")
        
        elif choice == '2':
            # Drop all tables
            print(f"\nYou are about to drop ALL {len(tables)} table(s)!")
            
            # Create backup
            create_backup = input("\nCreate backup before dropping? (y/n): ").strip().lower()
            if create_backup == 'y':
                self.create_backup()
            
            confirm = input("\nType 'DELETE ALL' to confirm: ").strip()
            if confirm == 'DELETE ALL':
                success_count = 0
                for t in tables:
                    if self.drop_table(t['schema'], t['table']):
                        success_count += 1
                print(f"\n✅ Dropped {success_count}/{len(tables)} tables")
            else:
                print("\n❌ Rollback cancelled.")
        
        elif choice == '3':
            # Drop schema
            schemas = set(t['schema'] for t in tables)
            print(f"\nAvailable schemas: {', '.join(schemas)}")
            schema_name = input("Enter schema name to drop: ").strip()
            
            if schema_name in schemas:
                schema_tables = [t for t in tables if t['schema'] == schema_name]
                print(f"\nThis will drop schema '{schema_name}' and all {len(schema_tables)} table(s) in it:")
                for t in schema_tables:
                    print(f"  - {t['table']}")
                
                # Create backup
                create_backup = input("\nCreate backup before dropping? (y/n): ").strip().lower()
                if create_backup == 'y':
                    self.create_backup()
                
                confirm = input(f"\nType 'DELETE SCHEMA' to confirm: ").strip()
                if confirm == 'DELETE SCHEMA':
                    self.drop_schema(schema_name)
                    print("\n✅ Schema dropped!")
                else:
                    print("\n❌ Rollback cancelled.")
            else:
                print(f"❌ Schema '{schema_name}' not found.")
        
        elif choice == '4':
            # Backup only
            self.create_backup()
        
        elif choice == '5':
            print("\n❌ Rollback cancelled.")
        
        else:
            print("\n❌ Invalid choice.")
        
        # Close connection
        if self.conn:
            self.conn.close()

def main():
    """Main entry point."""
    rollback = DatabaseRollback()
    
    try:
        rollback.interactive_rollback()
        return 0
    except Exception as e:
        print(f"\n❌ Rollback failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
