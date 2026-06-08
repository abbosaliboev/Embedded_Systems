import sqlite3
import logging
from datetime import datetime, date
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                pir       INTEGER NOT NULL DEFAULT 0,
                distance  REAL,
                gas       INTEGER NOT NULL DEFAULT 0,
                temp      REAL,
                humidity  REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS safety_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details    TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vision_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                person_detected INTEGER NOT NULL DEFAULT 0,
                in_danger_zone  INTEGER NOT NULL DEFAULT 0,
                confidence      REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT NOT NULL,
                trigger      TEXT NOT NULL,
                threat_level TEXT NOT NULL,
                scene_desc   TEXT,
                risk         TEXT,
                action       TEXT,
                summary      TEXT
            )
        """)
        conn.commit()
    logger.info("SQLite database ready at %s", DB_PATH)


def insert_reading(pir, distance, gas, temp, humidity):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sensor_readings (timestamp, pir, distance, gas, temp, humidity) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, int(pir or 0), distance, int(gas or 0), temp, humidity),
        )
        conn.commit()


def insert_event(event_type, details=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO safety_events (timestamp, event_type, details) VALUES (?, ?, ?)",
            (ts, event_type, details),
        )
        conn.commit()
    logger.warning("Safety event: [%s] %s", event_type, details)


def insert_vision_event(person_detected, in_danger_zone, confidence):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO vision_events (timestamp, person_detected, in_danger_zone, confidence) "
            "VALUES (?, ?, ?, ?)",
            (ts, int(bool(person_detected)), int(bool(in_danger_zone)), float(confidence or 0)),
        )
        conn.commit()


def insert_ai_analysis(trigger, threat_level, scene_desc, risk, action, summary):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO ai_analyses (timestamp, trigger, threat_level, scene_desc, risk, action, summary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, trigger, threat_level, scene_desc, risk, action, summary),
        )
        conn.commit()
    logger.info("AI analysis saved: [%s] threat=%s", trigger, threat_level)


def get_latest_reading():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_recent_readings(limit=60):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_events(limit=50):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM safety_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_latest_ai_analysis():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ai_analyses ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_recent_ai_analyses(limit=10):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_analyses ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_daily_report(day=None):
    if day is None:
        day = date.today().isoformat()

    with get_connection() as conn:
        stats = conn.execute("""
            SELECT
                COUNT(*)            AS total_readings,
                ROUND(AVG(temp), 1) AS avg_temp,
                ROUND(MAX(temp), 1) AS max_temp,
                ROUND(MIN(temp), 1) AS min_temp,
                ROUND(AVG(humidity), 1) AS avg_humidity,
                ROUND(MIN(distance), 1) AS min_distance,
                SUM(pir)            AS motion_count,
                SUM(gas)            AS gas_count
            FROM sensor_readings
            WHERE timestamp LIKE ?
        """, (day + "%",)).fetchone()

        events = conn.execute("""
            SELECT event_type, COUNT(*) AS cnt
            FROM safety_events
            WHERE timestamp LIKE ?
            GROUP BY event_type
        """, (day + "%",)).fetchall()

        hourly = conn.execute("""
            SELECT
                SUBSTR(timestamp, 12, 2) AS hour,
                ROUND(AVG(temp), 1)      AS avg_temp
            FROM sensor_readings
            WHERE timestamp LIKE ?
            GROUP BY hour
            ORDER BY hour
        """, (day + "%",)).fetchall()

        ai_threats = conn.execute("""
            SELECT threat_level, COUNT(*) AS cnt
            FROM ai_analyses
            WHERE timestamp LIKE ?
            GROUP BY threat_level
            ORDER BY cnt DESC
        """, (day + "%",)).fetchall()

    return {
        "date": day,
        "stats": dict(stats) if stats else {},
        "events": [dict(e) for e in events],
        "hourly_temp": [dict(h) for h in hourly],
        "ai_threats": [dict(a) for a in ai_threats],
    }


def get_available_days():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT DISTINCT SUBSTR(timestamp, 1, 10) AS day
            FROM sensor_readings
            ORDER BY day DESC
            LIMIT 30
        """).fetchall()
    return [r["day"] for r in rows]
