# MSSQL to PostgreSQL Migration Toolkit

Complete toolkit to migrate from Azure SQL Server to PostgreSQL with schema conversion, data validation, and error handling.

## Features
- ✅ Automatic schema conversion (MSSQL → PostgreSQL)
- ✅ Batch data migration with progress tracking
- ✅ Data validation and verification
- ✅ Error handling and detailed logging
- ✅ Rollback capability
- ✅ Support for all common MSSQL data types
- ✅ Parallel migration support
- ✅ Command-line interface with multiple options

## Prerequisites
- Ubuntu/Debian Linux
- Python 3.8+
- Access to source Azure SQL Server
- Access to target PostgreSQL database
- Sudo privileges (for installing ODBC driver)

## Quick Start

### 1. Installation
```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Install Microsoft ODBC Driver 18 for SQL Server
- Install required Python packages
- Create `.env` configuration file from template
- Make all scripts executable

### 2. Configuration
Edit `.env` file with your database credentials:
```bash
nano .env
```

Update the following values:
```bash
# Azure SQL Server
MSSQL_SERVER=tavabharat.database.windows.net
MSSQL_PORT=1433
MSSQL_DATABASE=TavaBharatDB_Prod
MSSQL_USER=your-email@domain.com
MSSQL_PASSWORD=your-password

# PostgreSQL
PGSQL_HOST=3.143.253.91
PGSQL_PORT=5432
PGSQL_DATABASE=tavabharatprod
PGSQL_USER=tavabharatprod
PGSQL_PASSWORD=your-password

# Migration Settings
BATCH_SIZE=1000
PARALLEL_WORKERS=4
```

### 3. Test Connections
```bash
python3 test_connection.py
```

This will verify connectivity to both databases and show:
- Database versions
- Table counts
- Sample table listings
- PostgreSQL extension status (uuid-ossp)

### 4. Export Schema (Optional)
```bash
python3 export_schema.py
```

This generates:
- `schema_mssql.sql` - Original MSSQL schema
- `schema_postgresql.sql` - PostgreSQL-compatible DDL
- `schema_postgresql_fkeys.sql` - Foreign key constraints
- `schema_postgresql_indexes.sql` - Index definitions

### 5. Run Migration
```bash
python3 migrate.py
```

The migration will:
1. Connect to both databases
2. Retrieve table schemas from MSSQL
3. Convert data types to PostgreSQL equivalents
4. Create tables in PostgreSQL
5. Migrate data in batches with progress bars
6. Create indexes and constraints
7. Validate row counts
8. Generate detailed logs

### 6. Validate Results
```bash
python3 validate.py
```

This performs:
- Row count comparison for all tables
- Sample data validation (100 random rows)
- Data type verification
- Generation of validation report

## Usage

### Basic Migration
```bash
python3 migrate.py
```

### Advanced Options

#### Custom Batch Size
```bash
python3 migrate.py --batch-size 5000
```

#### Migrate Specific Tables
```bash
python3 migrate.py --tables Users,Orders,Products
```

#### Exclude Tables
```bash
python3 migrate.py --exclude-tables Logs,TempData,Cache
```

#### Parallel Migration
```bash
python3 migrate.py --parallel 8
```

Use parallel workers to migrate multiple tables simultaneously. Good for databases with many small tables.

#### Drop Existing Tables
```bash
python3 migrate.py --drop-existing
```

**Warning:** This will drop existing tables in PostgreSQL before migration.

#### Combined Options
```bash
python3 migrate.py --batch-size 5000 --parallel 4 --exclude-tables Logs
```

### Rollback

If you need to rollback the migration:

```bash
python3 rollback.py
```

This provides interactive options to:
1. Drop specific tables
2. Drop all migrated tables
3. Drop entire schema
4. Create backup before rollback

**Important:** Always create a backup before performing rollback operations.

## Data Type Mapping

The toolkit automatically converts MSSQL data types to PostgreSQL equivalents:

| MSSQL Type | PostgreSQL Type | Notes |
|------------|-----------------|-------|
| `bit` | `boolean` | |
| `tinyint` | `smallint` | PostgreSQL doesn't have tinyint |
| `smallint` | `smallint` | |
| `int` | `integer` | |
| `bigint` | `bigint` | |
| `decimal(p,s)` | `numeric(p,s)` | Preserves precision and scale |
| `numeric(p,s)` | `numeric(p,s)` | Preserves precision and scale |
| `money` | `numeric(19,4)` | |
| `smallmoney` | `numeric(10,4)` | |
| `float` | `double precision` | |
| `real` | `real` | |
| `datetime` | `timestamptz` | With timezone |
| `datetime2` | `timestamptz` | With timezone |
| `smalldatetime` | `timestamptz` | With timezone |
| `date` | `date` | |
| `time` | `time` | |
| `char` | `text` | |
| `varchar` | `text` | PostgreSQL text is more efficient |
| `nchar` | `text` | |
| `nvarchar` | `text` | |
| `text` | `text` | |
| `ntext` | `text` | |
| `uniqueidentifier` | `uuid` | Requires uuid-ossp extension |
| `binary` | `bytea` | |
| `varbinary` | `bytea` | |
| `image` | `bytea` | |
| `xml` | `xml` | |

## Logging

The toolkit generates detailed logs:

### `migration.log`
Contains:
- Connection status
- Table creation progress
- Data migration progress
- Row counts
- Validation results
- Overall statistics

### `migration_errors.log`
Contains:
- Detailed error messages
- Stack traces
- Failed operations
- Troubleshooting information

### `validation_report_[timestamp].txt`
Contains:
- Row count comparisons
- Validation status for each table
- Discrepancy details

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to Azure SQL Server

**Solutions:**
- Verify firewall rules allow connections from your IP
- Check that server name and port are correct
- Ensure username format is correct (usually email address)
- Verify password doesn't have special characters that need escaping
- Check that Encrypt=yes and TrustServerCertificate=no are set

**Problem:** Cannot connect to PostgreSQL

**Solutions:**
- Verify PostgreSQL is accepting remote connections
- Check `pg_hba.conf` allows connections from your IP
- Ensure firewall allows port 5432
- Verify credentials are correct

### Migration Errors

**Problem:** "uuid-ossp extension not found"

**Solution:**
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

**Problem:** Foreign key constraint failures

**Solution:**
- Migrate parent tables before child tables
- Use `--drop-existing` flag to clear existing tables
- Manually disable foreign key checks during migration

**Problem:** Data type conversion errors

**Solution:**
- Check `migration_errors.log` for specific errors
- Some MSSQL-specific types may need manual handling
- Consider using `text` type for problematic columns

**Problem:** Out of memory during large table migration

**Solution:**
- Reduce `--batch-size` to 500 or 1000
- Migrate large tables separately
- Increase system memory or swap

### Performance Issues

**Problem:** Migration is very slow

**Solutions:**
- Increase `--batch-size` to 5000 or 10000
- Use `--parallel` for multi-threaded migration
- Ensure good network connectivity between databases
- Indexes are created AFTER data load (automatic)
- Consider migrating during off-peak hours

**Problem:** High memory usage

**Solutions:**
- Decrease `--batch-size`
- Reduce `--parallel` workers
- Monitor system resources during migration

### Validation Failures

**Problem:** Row counts don't match

**Solutions:**
- Check `migration_errors.log` for insert failures
- Verify no triggers or constraints preventing inserts
- Look for data that doesn't meet NOT NULL constraints
- Check for unique constraint violations

**Problem:** Data corruption or encoding issues

**Solutions:**
- Ensure both databases use UTF-8 encoding
- Check for null byte characters in text fields
- Verify binary data is handled correctly

## Best Practices

### Before Migration

1. **Backup both databases**
   ```bash
   # MSSQL backup (using SQL Server Management Studio or T-SQL)
   # PostgreSQL backup
   pg_dump -h host -U user -d database > backup.sql
   ```

2. **Test with sample tables first**
   ```bash
   python3 migrate.py --tables Users,Products
   ```

3. **Review schema differences**
   ```bash
   python3 export_schema.py
   # Review generated files
   ```

4. **Estimate migration time**
   - Small databases (<1GB): minutes
   - Medium databases (1-10GB): hours
   - Large databases (>10GB): many hours

### During Migration

1. **Monitor logs in real-time**
   ```bash
   tail -f migration.log
   ```

2. **Monitor system resources**
   ```bash
   htop
   ```

3. **Don't interrupt the process**
   - Let it complete or fail gracefully
   - Interruption may leave partial data

### After Migration

1. **Always validate**
   ```bash
   python3 validate.py
   ```

2. **Check application compatibility**
   - Test application with new database
   - Verify queries work correctly
   - Check for performance issues

3. **Update connection strings**
   - Point application to PostgreSQL
   - Update any hardcoded SQL Server syntax

4. **Monitor performance**
   - Run ANALYZE on PostgreSQL tables
   - Create additional indexes if needed
   - Tune PostgreSQL configuration

## Project Structure
```
.
├── migrate.py              # Main migration script
├── validate.py             # Validation script
├── test_connection.py      # Connection testing
├── export_schema.py        # Schema export utility
├── rollback.py             # Rollback utility
├── setup.sh                # Installation script
├── requirements.txt        # Python dependencies
├── .env.example            # Configuration template
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## Architecture

### Migration Process Flow

1. **Phase 1: Connection & Schema Analysis**
   - Connect to both MSSQL and PostgreSQL
   - Read INFORMATION_SCHEMA from MSSQL
   - Get tables, columns, data types, constraints, indexes

2. **Phase 2: Schema Creation**
   - Create schemas in PostgreSQL
   - Convert MSSQL DDL to PostgreSQL DDL
   - Create tables without indexes (for speed)
   - Add primary keys

3. **Phase 3: Data Migration**
   - For each table:
     - Read rows in batches from MSSQL
     - Transform data types as needed
     - Insert using `psycopg2.extras.execute_batch()`
     - Display progress bar with `tqdm`
     - Handle errors gracefully

4. **Phase 4: Indexes & Constraints**
   - Create indexes after data load
   - Add foreign key constraints
   - Create unique constraints

5. **Phase 5: Validation**
   - Compare row counts between databases
   - Sample random rows for data integrity
   - Generate validation report

### Error Handling

- All database operations wrapped in try/except blocks
- Errors logged to `migration_errors.log` with full context
- Migration continues to next table on error
- Summary report shows successful and failed tables
- Transactional inserts (batches committed together)

### Performance Optimizations

- **Batch processing**: Inserts done in configurable batches
- **execute_batch**: Uses psycopg2's optimized batch insert
- **Deferred indexes**: Indexes created after data load
- **Parallel processing**: Multiple tables migrated simultaneously
- **Connection pooling**: Reuses database connections
- **Progress tracking**: Visual feedback without performance impact

## Security Considerations

- **Never commit `.env` file** - Contains sensitive credentials
- **Use strong passwords** - Both databases should have secure passwords
- **Restrict network access** - Use firewalls and VPNs
- **Encrypt connections** - MSSQL uses Encrypt=yes, PostgreSQL supports SSL
- **Audit access** - Monitor who runs migrations
- **Backup before migration** - Always have a rollback plan

## Limitations

- **No stored procedures**: Stored procedures must be manually converted
- **No triggers**: Triggers must be recreated in PostgreSQL
- **No views**: Views must be manually recreated
- **No functions**: User-defined functions need manual conversion
- **Limited data type support**: Some MSSQL-specific types may need custom handling
- **No replication**: One-time migration, not continuous replication

## FAQ

**Q: Can I run the migration multiple times?**

A: Yes, use `--drop-existing` flag to drop tables before recreation. Be careful as this deletes existing data.

**Q: How long will migration take?**

A: Depends on:
- Database size
- Network speed
- Number of tables
- Batch size
- Parallel workers

Estimate: ~100,000 rows per minute for typical tables.

**Q: Can I migrate to a different schema name?**

A: Currently, the toolkit preserves schema names. Manual modification of the code would be needed for schema name changes.

**Q: What if migration fails midway?**

A: The toolkit logs all errors. You can:
1. Fix the issue
2. Use `--exclude-tables` to skip already migrated tables
3. Re-run migration for remaining tables

**Q: Does this support continuous replication?**

A: No, this is a one-time migration tool. For continuous replication, consider tools like:
- AWS DMS
- Debezium
- Striim

**Q: Can I migrate from on-premise SQL Server?**

A: Yes, just change `MSSQL_SERVER` in `.env` to your server address. Ensure network connectivity.

**Q: Does it migrate users and permissions?**

A: No, users and permissions must be manually recreated in PostgreSQL.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
1. Check `migration_errors.log` for detailed error messages
2. Review this README's Troubleshooting section
3. Open an issue on GitHub with:
   - Error messages
   - Migration configuration
   - Database versions
   - Steps to reproduce

## License

MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Acknowledgments

- Microsoft ODBC Driver for SQL Server
- psycopg2 PostgreSQL adapter
- tqdm for progress bars
- python-dotenv for configuration management

---

**Note:** Always test migrations in a development environment before running in production.