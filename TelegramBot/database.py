import sqlite3
import json
from typing import List, Dict, Any, Optional, Tuple

class Database:
    def __init__(self, db_path="user_data.db"):
        self.db_path = db_path
        self._create_tables()

    def _create_tables(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            keywords TEXT,
            price_filters TEXT,
            price_min INTEGER DEFAULT 0,
            notifications_enabled INTEGER DEFAULT 0,
            last_sent_id TEXT
        )
        ''')
        
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'price_filter' in columns and 'price_filters' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN price_filters TEXT DEFAULT '[]'")
            
            cursor.execute("SELECT user_id, price_filter FROM users")
            rows = cursor.fetchall()
            
            for user_id, price_filter in rows:
                price_filters = [price_filter] if price_filter else []
                cursor.execute(
                    "UPDATE users SET price_filters = ? WHERE user_id = ?",
                    (json.dumps(price_filters), user_id)
                )
        
        conn.commit()
        conn.close()

    def add_user(self, user_id: int) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, keywords, price_filters, notifications_enabled, last_sent_id) 
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, json.dumps([]), json.dumps(['any']), 0, ''))
        
        conn.commit()
        conn.close()
    
    def user_exists(self, user_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone() is not None
        
        conn.close()
        return result
    
    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return {}
        
        settings = dict(row)
        settings['keywords'] = json.loads(settings['keywords'])
        
        if 'price_filters' in settings:
            settings['price_filters'] = json.loads(settings['price_filters'])
        else:
            old_filter = settings.get('price_filter', 'any')
            settings['price_filters'] = [old_filter] if old_filter else ['any']
        
        return settings
    
    def update_keywords(self, user_id: int, keywords: List[str]) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE users SET keywords = ? WHERE user_id = ?', 
            (json.dumps(keywords), user_id)
        )
        
        conn.commit()
        conn.close()
    
    def update_price_filters(self, user_id: int, price_filters: List[str], price_min: int = 0) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE users SET price_filters = ?, price_min = ? WHERE user_id = ?', 
            (json.dumps(price_filters), price_min, user_id)
        )
        
        conn.commit()
        conn.close()
    
    def toggle_notifications(self, user_id: int, enabled: bool) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE users SET notifications_enabled = ? WHERE user_id = ?', 
            (1 if enabled else 0, user_id)
        )
        
        conn.commit()
        conn.close()
    
    def update_last_sent_id(self, user_id: int, task_id: str) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE users SET last_sent_id = ? WHERE user_id = ?', 
            (task_id, user_id)
        )
        
        conn.commit()
        conn.close()
    
    def get_users_with_notifications(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE notifications_enabled = 1')
        rows = cursor.fetchall()
        
        users = []
        for row in rows:
            user = dict(row)
            user['keywords'] = json.loads(user['keywords'])
            
            if 'price_filters' in user:
                user['price_filters'] = json.loads(user['price_filters'])
            else:
                old_filter = user.get('price_filter', 'any')
                user['price_filters'] = [old_filter] if old_filter else ['any']
            
            users.append(user)
        
        conn.close()
        return users