import logging
import os

logger = logging.getLogger("app_logger")


def create_database(conn, c):
    
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()

    if len(tables) > 0:
        logger.info("Database already exists, not creating a new one")
        return
        
    create_category_table(c)
    create_channel_table(c)
    create_video_table(c)
    create_video_stat_table(c)
    create_channel_stat_table(c)
    create_activity_table(c)
    
    conn.commit()
    
    filename = os.getenv("SQLITE_DB_FILE")
    
    logger.info(f"Database created successfully ({filename})")
    
    
def create_category_table(c):
    c.execute("""CREATE TABLE IF NOT EXISTS category (
                    id INTEGER PRIMARY KEY,
                    cluster_number INTEGER,
                    name TEXT,
                    keywords TEXT
                )""")


def create_channel_table(c):
    c.execute("""CREATE TABLE IF NOT EXISTS channel (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    url TEXT,
                    description TEXT,
                    keywords TEXT,
                    is_deleted BOOLEAN,
                    category_id INTEGER,
                    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE CASCADE
                )""")


def create_video_table(c):
    c.execute("""CREATE TABLE IF NOT EXISTS video (
                    id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    title TEXT,
                    url TEXT,
                    length INTEGER,
                    description TEXT,
                    tags TEXT,
                    keywords TEXT,
                    published_at DATETIME,
                    is_deleted BOOLEAN,
                    FOREIGN KEY (channel_id) REFERENCES channel(id) ON DELETE CASCADE
                )""")

def create_video_stat_table(c):
    c.execute("""CREATE TABLE IF NOT EXISTS video_stat (
                    id INTEGER PRIMARY KEY,
                    video_id INTEGER,
                    timestamp DATE,
                    view_count INTEGER,
                    like_count INTEGER,
                    comment_count INTEGER,
                    FOREIGN KEY (video_id) REFERENCES video(id) ON DELETE CASCADE
                )""")

def create_channel_stat_table(c):
    c.execute("""CREATE TABLE IF NOT EXISTS channel_stat (
                    id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    timestamp DATETIME,
                    subscriber_count INTEGER,
                    video_count INTEGER,
                    view_count INTEGER,
                    FOREIGN KEY (channel_id) REFERENCES channel(id) ON DELETE CASCADE
                )""")


def create_activity_table(c):
    c.execute("""CREATE TABLE IF NOT EXISTS activity (
                    id INTEGER PRIMARY KEY,
                    action TEXT,
                    timestamp DATETIME,
                    video_id INTEGER,
                    channel_id INTEGER,
                    FOREIGN KEY (video_id) REFERENCES video(id) ON DELETE CASCADE,
                    FOREIGN KEY (channel_id) REFERENCES channel(id) ON DELETE CASCADE
                )""")