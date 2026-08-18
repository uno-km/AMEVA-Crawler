"""
AMEVA-Crawler Database Module
SQLite3 database manager with schema initialization and CRUD helper functions.
"""
import sqlite3
import json
import datetime
from contextlib import contextmanager
from config import DB_PATH, DEFAULT_TELEGRAM_BOT_TOKEN, DEFAULT_TELEGRAM_CHAT_ID, DEFAULT_TELEGRAM_ENABLED

@contextmanager
def get_db():
    """Context manager for SQLite database connection."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize database tables and default settings."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Targets Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'GET',
            headers TEXT DEFAULT '{}',
            body TEXT DEFAULT '',
            content_type TEXT DEFAULT 'application/json',
            interval_type TEXT NOT NULL DEFAULT 'interval',
            interval_value TEXT NOT NULL DEFAULT '300',
            detect_mode TEXT DEFAULT 'all',
            selector_rule TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            last_checked_at TEXT DEFAULT NULL,
            last_status_code INTEGER DEFAULT NULL,
            last_content_hash TEXT DEFAULT NULL,
            last_change_detected_at TEXT DEFAULT NULL,
            consecutive_errors INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        
        # Crawl History Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawl_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            status_code INTEGER,
            response_time_ms INTEGER,
            is_changed INTEGER DEFAULT 0,
            content_hash TEXT,
            extracted_text TEXT,
            extracted_links TEXT,
            diff_summary TEXT,
            new_links TEXT,
            removed_links TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (target_id) REFERENCES targets(id) ON DELETE CASCADE
        )
        """)
        
        # Settings Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        
        # Telegram Logs Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS telegram_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            target_name TEXT,
            message TEXT,
            status TEXT,
            error_message TEXT,
            sent_at TEXT NOT NULL
        )
        """)
        
        # System Logs Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        
        # Initialize default settings if not exists (empty placeholders)
        default_settings = {
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "telegram_enabled": "false",
            "global_user_agent": "",
            "crawler_timeout": "20",
            "max_history_per_target": "50"
        }
        
        for k, v in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
            
        # Create indexes for fast query
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_target ON crawl_history(target_id, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_targets_active ON targets(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_logs(created_at DESC)")

# ----------------- Target Operations -----------------

def get_all_targets():
    """Get all targets."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM targets ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

def get_active_targets():
    """Get all active targets."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM targets WHERE is_active = 1 ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]

def get_target_by_id(target_id):
    """Get a single target by ID."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
        return dict(row) if row else None

def create_target(data):
    """Create a new crawl target."""
    now = datetime.datetime.now().isoformat()
    headers_val = data.get("headers", "{}")
    if isinstance(headers_val, dict):
        headers_val = json.dumps(headers_val, ensure_ascii=False)
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO targets (
            name, url, method, headers, body, content_type,
            interval_type, interval_value, detect_mode, selector_rule,
            is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("name", "New Target").strip(),
            data.get("url", "").strip(),
            data.get("method", "GET").upper(),
            headers_val,
            data.get("body", ""),
            data.get("content_type", "application/json"),
            data.get("interval_type", "interval"),
            str(data.get("interval_value", "300")),
            data.get("detect_mode", "all"),
            data.get("selector_rule", ""),
            1 if data.get("is_active", True) else 0,
            now,
            now
        ))
        return cursor.lastrowid

def update_target(target_id, data):
    """Update an existing target."""
    now = datetime.datetime.now().isoformat()
    headers_val = data.get("headers", "{}")
    if isinstance(headers_val, dict):
        headers_val = json.dumps(headers_val, ensure_ascii=False)
        
    with get_db() as conn:
        conn.execute("""
        UPDATE targets SET
            name = ?,
            url = ?,
            method = ?,
            headers = ?,
            body = ?,
            content_type = ?,
            interval_type = ?,
            interval_value = ?,
            detect_mode = ?,
            selector_rule = ?,
            is_active = ?,
            updated_at = ?
        WHERE id = ?
        """, (
            data.get("name", "").strip(),
            data.get("url", "").strip(),
            data.get("method", "GET").upper(),
            headers_val,
            data.get("body", ""),
            data.get("content_type", "application/json"),
            data.get("interval_type", "interval"),
            str(data.get("interval_value", "300")),
            data.get("detect_mode", "all"),
            data.get("selector_rule", ""),
            1 if data.get("is_active", True) else 0,
            now,
            target_id
        ))

def delete_target(target_id):
    """Delete a target and its history."""
    with get_db() as conn:
        conn.execute("DELETE FROM crawl_history WHERE target_id = ?", (target_id,))
        conn.execute("DELETE FROM targets WHERE id = ?", (target_id,))

def toggle_target_active(target_id):
    """Toggle is_active status of a target."""
    with get_db() as conn:
        target = conn.execute("SELECT is_active FROM targets WHERE id = ?", (target_id,)).fetchone()
        if target:
            new_status = 0 if target["is_active"] == 1 else 1
            conn.execute("UPDATE targets SET is_active = ?, updated_at = ? WHERE id = ?", 
                         (new_status, datetime.datetime.now().isoformat(), target_id))
            return new_status
    return None

def update_target_crawl_status(target_id, status_code, content_hash, is_changed, has_error=False):
    """Update target runtime status after a crawl."""
    now = datetime.datetime.now().isoformat()
    with get_db() as conn:
        if has_error:
            conn.execute("""
            UPDATE targets SET 
                last_checked_at = ?,
                last_status_code = ?,
                consecutive_errors = consecutive_errors + 1,
                updated_at = ?
            WHERE id = ?
            """, (now, status_code, now, target_id))
        else:
            if is_changed:
                conn.execute("""
                UPDATE targets SET 
                    last_checked_at = ?,
                    last_status_code = ?,
                    last_content_hash = ?,
                    last_change_detected_at = ?,
                    consecutive_errors = 0,
                    updated_at = ?
                WHERE id = ?
                """, (now, status_code, content_hash, now, now, target_id))
            else:
                conn.execute("""
                UPDATE targets SET 
                    last_checked_at = ?,
                    last_status_code = ?,
                    consecutive_errors = 0,
                    updated_at = ?
                WHERE id = ?
                """, (now, status_code, now, target_id))

# ----------------- History Operations -----------------

def add_crawl_history(record):
    """Insert a new crawl execution history item."""
    now = datetime.datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO crawl_history (
            target_id, status_code, response_time_ms, is_changed,
            content_hash, extracted_text, extracted_links,
            diff_summary, new_links, removed_links, error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.get("target_id"),
            record.get("status_code"),
            record.get("response_time_ms", 0),
            1 if record.get("is_changed") else 0,
            record.get("content_hash", ""),
            record.get("extracted_text", ""),
            record.get("extracted_links", "[]"),
            record.get("diff_summary", ""),
            record.get("new_links", "[]"),
            record.get("removed_links", "[]"),
            record.get("error_message", ""),
            now
        ))
        
        # Prune old history per target to save disk space
        max_h = int(get_setting("max_history_per_target", "50"))
        cursor.execute("""
        DELETE FROM crawl_history 
        WHERE target_id = ? AND id NOT IN (
            SELECT id FROM crawl_history WHERE target_id = ? ORDER BY id DESC LIMIT ?
        )
        """, (record.get("target_id"), record.get("target_id"), max_h))
        
        return cursor.lastrowid

def get_target_history(target_id, limit=30):
    """Get history entries for a specific target."""
    with get_db() as conn:
        rows = conn.execute("""
        SELECT id, target_id, status_code, response_time_ms, is_changed,
               content_hash, diff_summary, new_links, removed_links,
               error_message, created_at
        FROM crawl_history 
        WHERE target_id = ? 
        ORDER BY id DESC LIMIT ?
        """, (target_id, limit)).fetchall()
        return [dict(r) for r in rows]

def get_latest_successful_crawl(target_id):
    """Get the most recent successful crawl history with content for diffing."""
    with get_db() as conn:
        row = conn.execute("""
        SELECT * FROM crawl_history 
        WHERE target_id = ? AND status_code >= 200 AND status_code < 400 AND content_hash IS NOT NULL AND content_hash != ''
        ORDER BY id DESC LIMIT 1
        """, (target_id,)).fetchone()
        return dict(row) if row else None

# ----------------- Settings Operations -----------------

def get_all_settings():
    """Get all system settings as a dictionary."""
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

def get_setting(key, default=None):
    """Get a single setting value."""
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key, value):
    """Set a setting value."""
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

def set_settings_bulk(settings_dict):
    """Update multiple settings at once."""
    with get_db() as conn:
        for k, v in settings_dict.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))

# ----------------- Logging Operations -----------------

def log_telegram(target_id, target_name, message, status, error_message=""):
    """Log telegram notification attempt."""
    now = datetime.datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
        INSERT INTO telegram_logs (target_id, target_name, message, status, error_message, sent_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (target_id, target_name, message, status, error_message, now))

def get_telegram_logs(limit=50):
    """Get recent telegram notification logs."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM telegram_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

def log_system(level, message):
    """Log a system message."""
    now = datetime.datetime.now().isoformat()
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO system_logs (level, message, created_at) VALUES (?, ?, ?)", (level, message, now))
            # Keep only last 500 logs
            conn.execute("DELETE FROM system_logs WHERE id NOT IN (SELECT id FROM system_logs ORDER BY id DESC LIMIT 500)")
    except Exception as e:
        print(f"Failed to log system message: {e}")

def get_system_logs(limit=100):
    """Get recent system logs."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

def get_dashboard_stats():
    """Compute summary statistics for dashboard."""
    with get_db() as conn:
        total_targets = conn.execute("SELECT COUNT(*) as c FROM targets").fetchone()["c"]
        active_targets = conn.execute("SELECT COUNT(*) as c FROM targets WHERE is_active = 1").fetchone()["c"]
        
        # Changes in last 24 hours
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        recent_changes = conn.execute("""
        SELECT COUNT(*) as c FROM crawl_history WHERE is_changed = 1 AND created_at >= ?
        """, (yesterday,)).fetchone()["c"]
        
        # Telegram sent count
        telegram_sent = conn.execute("SELECT COUNT(*) as c FROM telegram_logs WHERE status = 'SUCCESS'").fetchone()["c"]
        
        return {
            "total_targets": total_targets,
            "active_targets": active_targets,
            "recent_changes_24h": recent_changes,
            "telegram_sent_count": telegram_sent
        }
