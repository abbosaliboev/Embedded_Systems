import logging
import pymysql
import pymysql.cursors
from datetime import datetime
import config

logger = logging.getLogger(__name__)


def get_connection():
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id        INT          AUTO_INCREMENT PRIMARY KEY,
                    timestamp DATETIME     NOT NULL,
                    pir       TINYINT(1)   NOT NULL,
                    distance  FLOAT,
                    gas       TINYINT(1)   NOT NULL,
                    temp      FLOAT,
                    humidity  FLOAT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS safety_events (
                    id         INT          AUTO_INCREMENT PRIMARY KEY,
                    timestamp  DATETIME     NOT NULL,
                    event_type VARCHAR(20)  NOT NULL,
                    details    TEXT
                )
            """)
        conn.commit()
    logger.info("MySQL database initialized (%s@%s/%s)", config.DB_USER, config.DB_HOST, config.DB_NAME)


def insert_reading(pir, distance, gas, temp, humidity):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sensor_readings (timestamp, pir, distance, gas, temp, humidity) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (ts, int(pir), distance, int(gas), temp, humidity),
            )
        conn.commit()


def insert_event(event_type, details=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO safety_events (timestamp, event_type, details) VALUES (%s, %s, %s)",
                (ts, event_type, details),
            )
        conn.commit()
    logger.warning("Safety event: [%s] %s", event_type, details)


def get_latest_reading():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
    return row


def get_recent_readings(limit=60):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT %s", (limit,)
            )
            rows = cur.fetchall()
    return rows


def get_recent_events(limit=50):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM safety_events ORDER BY id DESC LIMIT %s", (limit,)
            )
            rows = cur.fetchall()
    return rows
