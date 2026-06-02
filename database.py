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
                pir       INTEGER NOT NULL,
                distance  REAL,
                gas       INTEGER NOT NULL,
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
        conn.commit()
    logger.info("SQLite database ready at %s", DB_PATH)


def insert_reading(pir, distance, gas, temp, humidity):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sensor_readings (timestamp, pir, distance, gas, temp, humidity) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, int(pir), distance, int(gas), temp, humidity),
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


def get_daily_report(day: str | None = None) -> dict:
    """
    Returns a summary for a given day (YYYY-MM-DD).
    Defaults to today if day is not provided.
    """
    if day is None:
        day = date.today().isoformat()

    with get_connection() as conn:
        # Sensor averages for the day
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

        # Event breakdown
        events = conn.execute("""
            SELECT event_type, COUNT(*) AS cnt
            FROM safety_events
            WHERE timestamp LIKE ?
            GROUP BY event_type
        """, (day + "%",)).fetchall()

        # Hourly temperature trend
        hourly = conn.execute("""
            SELECT
                SUBSTR(timestamp, 12, 2) AS hour,
                ROUND(AVG(temp), 1)      AS avg_temp
            FROM sensor_readings
            WHERE timestamp LIKE ?
            GROUP BY hour
            ORDER BY hour
        """, (day + "%",)).fetchall()

    return {
        "date": day,
        "stats": dict(stats) if stats else {},
        "events": [dict(e) for e in events],
        "hourly_temp": [dict(h) for h in hourly],
    }


def get_available_days() -> list[str]:
    """Returns list of distinct days that have sensor data."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT DISTINCT SUBSTR(timestamp, 1, 10) AS day
            FROM sensor_readings
            ORDER BY day DESC
            LIMIT 30
        """).fetchall()
    return [r["day"] for r in rows]
