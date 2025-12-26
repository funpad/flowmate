import sqlite3
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name="flowmate.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, task_name TEXT, start_time TEXT, end_time TEXT, duration_minutes INTEGER, status TEXT, distraction_count INTEGER DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS distractions (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, timestamp TEXT, app_name TEXT, reason TEXT)''')
        self.conn.commit()

    def start_session(self, task_name, duration):
        cursor = self.conn.cursor()
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO sessions (task_name, start_time, duration_minutes, status, distraction_count) VALUES (?, ?, ?, 'RUNNING', 0)", (task_name, start_time, duration))
        self.conn.commit()
        return cursor.lastrowid

    def end_session(self, session_id, status="COMPLETED"):
        cursor = self.conn.cursor()
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE sessions SET end_time = ?, status = ? WHERE id = ?", (end_time, status, session_id))
        self.conn.commit()

    def log_distraction(self, session_id, app_name, reason):
        cursor = self.conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO distractions (session_id, timestamp, app_name, reason) VALUES (?, ?, ?, ?)", (session_id, timestamp, app_name, reason))
        cursor.execute("UPDATE sessions SET distraction_count = distraction_count + 1 WHERE id = ?", (session_id,))
        self.conn.commit()

    def get_today_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.conn.cursor()
        cursor.execute("SELECT task_name, duration_minutes, status, distraction_count FROM sessions WHERE start_time LIKE ?", (f'{today}%',))
        tasks = cursor.fetchall()
        cursor.execute("SELECT reason, count(*) as cnt FROM distractions WHERE timestamp LIKE ? GROUP BY reason ORDER BY cnt DESC LIMIT 3", (f'{today}%',))
        distractions = cursor.fetchall()
        return tasks, distractions