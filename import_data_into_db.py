import csv
import logging
import os

logger = logging.getLogger("app_logger")


# Channels with extra long videos messing up the stats and to be deleted, 
# or other channels you just don't want to include.
CHANNELS_NOT_TO_IMPORT = ["4k SCREENSAVERS", "Nature Relaxation Films", "4K Relaxation Channel"]

# Some extra long videos can be deleted but in that case these channels won't be touched.
IMPORTANT_CHANNELS = ["Lex Fridman", "Andrew Huberman"]


# Insert the data from the CSV file into the database.
def insert_data_into_database(conn, c):
    
    csv_file = os.path.abspath(os.getenv("CSV_FILE"))
    
    with open(csv_file, "r", encoding="UTF-8-sig") as csvfile:
        
        reader = csv.DictReader(csvfile, delimiter=";")

        inserted_videos = 0
        inserted_channels = 0
        inserted_actions = 0
        skipped_videos = 0
        
        logger.info("Inserting data into the database...")
        
        # Loop over each row in the CSV file.
        for row in reader:
            
            if  row["Channel"] in CHANNELS_NOT_TO_IMPORT:
                skipped_videos += 1
                continue
                
            c.execute("SELECT id FROM activity WHERE action = ? AND timestamp = ?",
                    (row["Action"], row["Timestamp"]))
            activity = c.fetchone()

            # If the action is already in the activity table, this is not the first time the script is run.
            if activity:
                continue
            
            c.execute("SELECT id, url FROM channel WHERE url = ?", (row["Channel URL"],))
            channel = c.fetchone()
            
            # If the channel doesn"t exist, insert it into the channels table.
            if not channel:
                channel_name = row["Channel"].strip()
                
                c.execute("""INSERT INTO channel (name, url)
                            VALUES (?, ?)""", (channel_name , row["Channel URL"],))
                channel_id = c.lastrowid
                inserted_channels += 1
            else:
                channel_id = channel[0]

            if "Title" in row and "URL" in row:
                c.execute("SELECT id FROM video WHERE title = ? AND url = ?", (row["Title"], row["URL"]))
                video = c.fetchone()

                # If the video doesn"t exist, insert it into the videos table.
                if not video:
                    c.execute("""INSERT INTO video (title, url, channel_id)
                                VALUES (?, ?, ?)""", (row.get("Title", None), row["URL"], channel_id))
                    video_id = c.lastrowid
                    inserted_videos += 1
                else:
                    video_id = video[0]

            c.execute("""INSERT INTO activity (action, timestamp, video_id, channel_id)
                        VALUES (?, ?, ?, ?)""", (row["Action"], row["Timestamp"], video_id, channel_id))
            inserted_actions += 1

        conn.commit()
        
        logger.info(f"Actions inserted: {inserted_actions}")
        logger.info(f"Unique videos inserted: {inserted_videos}")
        logger.info(f"Unique channels inserted: {inserted_channels}")

        if skipped_videos > 0:
            logger.info(f"{skipped_videos} videos skipped because channels were defined as excluded")


# Many streams are 10+ hours which mess up the watch time stats. 4 hours seemed to be a good average for me. 
def delete_extra_long_videos(conn, c, max_length=4):
    
    min_length = max_length * 3600
    excluded_condition = ''
    
    if IMPORTANT_CHANNELS:
        excluded_condition = f"AND channel.name NOT IN ({','.join('?' for _ in IMPORTANT_CHANNELS)})"
    else:
        excluded_condition = ''

    query = f"""
        DELETE FROM video
        WHERE id IN (
            SELECT video.id
            FROM video
            JOIN channel ON video.channel_id = channel.id
            WHERE video.length > ?
            {excluded_condition}
            ORDER BY video.length DESC)
    """

    c.execute(query, [min_length] + IMPORTANT_CHANNELS)
    conn.commit()
    
    if c.rowcount > 0:
        logger.info(f"Deleted {c.rowcount} extra long videos.")


# Delete channels that have no videos and vice versa.
def delete_orphans(conn, c):
    
    c.execute("DELETE FROM channel WHERE id NOT IN (SELECT DISTINCT channel_id FROM video)")
    
    rowcount = c.rowcount
    
    c.execute("DELETE FROM activity WHERE channel_id NOT IN (SELECT id FROM channel)")
    c.execute("DELETE FROM video WHERE channel_id NOT IN (SELECT id FROM channel)")
    c.execute("DELETE FROM video_stat WHERE video_id NOT IN (SELECT id FROM video)")
    c.execute("DELETE FROM channel_stat WHERE channel_id NOT IN (SELECT id FROM channel)")
    conn.commit()
    
    if rowcount > 0:
        logger.info(f"Deleted {c.rowcount} empty channels.")