# Scripts Directory

Utility scripts for managing the Reddit Discord Bot.

## Migration Scripts (`migration/`)
- `migrate_firestore_to_sqlite.py` - Migrate data from Firestore to SQLite
- `verify_migration.py` - Verify migration completed successfully  
- `enhance_database.py` - Add new database columns/tables

## Database Management (`database/`)
- `db_manager.py` - CLI tool for database operations
- `stats_dashboard.py` - Interactive statistics dashboard

## Utilities (`utils/`)
- `show_current_settings.py` - Display current bot configuration
- `check_firestore_simple.py` - Check Firestore data structure
- `check_firestore.py` - Advanced Firestore checker

## Usage Examples

```bash
# Database management
python scripts/database/db_manager.py status
python scripts/database/stats_dashboard.py

# Migration (run once)
python scripts/migration/migrate_firestore_to_sqlite.py
python scripts/migration/verify_migration.py

# Utilities
python scripts/utils/show_current_settings.py
```