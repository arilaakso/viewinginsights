import logging
import os
from datetime import date

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from tqdm import tqdm

logger = logging.getLogger("app_logger")

# YouTube API has a quota of 10,000 units per day, you may want to check that everything works before consuming it all.
MAX_RESULTS = 10

def get_youtube_client():
    
    # Set up the OAuth2.0 credentials
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/youtube.force-ssl"])
    else:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", ["https://www.googleapis.com/auth/youtube.force-ssl"])
        creds = flow.run_local_server(port=0)
        with open("token.json", "w", encoding="UTF-8") as token:
            token.write(creds.to_json())

    # Set up the YouTube API client
    youtube = build("youtube", "v3", credentials=creds)
    
    return youtube


# Get channel URL from DB and call YouTube API to get more information to be stored in the DB.
# The method can be run multiple times, it will only update the channels that are missing some information.
def save_channel_details(youtube, conn, c):
    
    c.execute("SELECT id, url FROM channel WHERE description IS NULL LIMIT " + str(MAX_RESULTS))
    channels = c.fetchall()

    total_channels = 0
    deleted_channels = 0
    for channel in tqdm(channels):
        db_id = channel[0]
        channel_url = channel[1]
        
        channel_id = channel_url.replace("https://www.youtube.com/channel/", "")

        try:
            response = youtube.channels().list(
                part="snippet,contentDetails,statistics",
                id=channel_id
            ).execute()

            # If channel is not found from YouTube, delete it.
            if response is None or response.get("items") is None or len(response["items"]) == 0:
                c.execute("DELETE FROM channel WHERE id = ?", (db_id,))
                deleted_channels += 1
                conn.commit()
                continue
            
            channel_title = response["items"][0]["snippet"]["title"]
            channel_description = response["items"][0]["snippet"]["description"]
            
            stats = response["items"][0]["statistics"]
            
            c.execute("UPDATE channel SET name = ?, description = ? WHERE id = ?", 
                      (channel_title, channel_description, db_id))
                 
            # Store also other channel stats into DB for future analysis.       
            save_channel_stats(c, db_id, stats)
            
            conn.commit()
            total_channels += 1

        except IndexError:
            logger.error(f"Channel {channel_url} could not be retrieved from YouTube")
            
    logger.info(f"Updated {total_channels} channels from YouTube API")
    
    c.execute("SELECT COUNT(id) FROM channel WHERE description IS NULL")
   
    count = c.fetchone()[0]
    
    if deleted_channels > 0:
        logger.info(f"Deleted {deleted_channels} unavailable channels from DB")
        
    if count > 0:
        logger.info(f"Channels not yet updated: {count}")


# Insert channel stats into DB.
def save_channel_stats(c, db_id, stats):
    
    today = date.today()
    c.execute("""SELECT id FROM channel_stat WHERE channel_id = ? AND timestamp = ?""", (db_id, today))
    existing_stats = c.fetchone()

    # Update stats only max once a day.
    if existing_stats:
        return

    subscriber_count = stats["subscriberCount"]
    video_count = stats["videoCount"]
    view_count = stats["viewCount"]
    
    c.execute("INSERT INTO channel_stat (channel_id, timestamp, subscriber_count, video_count, view_count) VALUES (?, date(\"now\"), ?, ?, ?)",
        (db_id, subscriber_count, video_count, view_count))


# Get video URL from DB and call YouTube API to retrieve video details.
def save_video_details(youtube, conn, c):
    
    # If video length is available, the data has already been retrieved.
    # You can play with the LIMIT value when debugging.
    c.execute("SELECT id, url FROM video WHERE length IS NULL LIMIT " + str(MAX_RESULTS))
    
    videos = c.fetchall()

    deleted_videos = 0
    total_videos = 0
    for video in tqdm(videos):
        video_id = video[0]
        video_url = video[1]

        try:
            response = youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=video_url.split("=")[1]
            ).execute()

            # If video is not available in YouTube anymore, mark it as such in the DB.
            if response is None or len(response["items"]) == 0:
                deleted_videos += 1
                c.execute("DELETE FROM video WHERE id = ?", (video_id,))
                conn.commit()
                continue
            
            video = response["items"][0]
            duration = video["contentDetails"]["duration"]
            description = video["snippet"]["description"]
            published_at = video["snippet"]["publishedAt"]
            
            tags_list = None
            tags = None
            
            if "tags" in video["snippet"]:
                tags_list = video["snippet"]["tags"]
            
            if tags_list is not None:
                tags = ",".join(tags_list)
                
            duration_tmp = parse_duration(duration)
            length = time_to_seconds(duration_tmp)

            c.execute("UPDATE video SET length = ?, description = ?, published_at = ?, tags = ? WHERE id = ?", (length, description, published_at, tags, video_id))

            conn.commit()

            save_video_stats(c, video_id, video["statistics"])
            total_videos += 1
            
        except IndexError:
            deleted_videos += 1
    
    # Commit the last row too
    conn.commit()
    
    logger.info(f"Updated {total_videos} videos from YouTube API")

    c.execute("SELECT COUNT(id) FROM video WHERE length IS NULL")
    
    count = c.fetchone()[0]
    
    if count > 0:
        logger.info(f"Videos not yet updated: {count}")



# Additional status from the video, can maybe analysed later.
def save_video_stats(c, video_id, stats):
    
    # Check if video stats for today have already been retrieved.
    today = date.today()
    c.execute("""SELECT id FROM video_stat WHERE video_id = ? AND timestamp = ?""", (video_id, today))
    existing_stats = c.fetchone()

    # Update stats only max once a day.
    if not existing_stats:
        
        view_count = stats.get("viewCount", 0)
        like_count = stats.get("likeCount", 0)
        comment_count = stats.get("commentCount", 0)
        
        c.execute("""INSERT INTO video_stat (video_id, timestamp, view_count, like_count, comment_count)
                    VALUES (?, date("now"), ?, ?, ?)""", (video_id, view_count, like_count, comment_count))
        
    
# Convert YouTube "P54DT22H32M59S" duration format into HH:MM:SS format
def parse_duration(duration_raw):
    try:
        time_str = duration_raw[2:]
        hours = 0
        minutes = 0
        seconds = 0

        if 'H' in time_str:
            hours_str, time_str = time_str.split('H')
            hours = int(hours_str)

        if 'M' in time_str:
            minutes_str, time_str = time_str.split('M')
            minutes = int(minutes_str)

        if 'S' in time_str:
            seconds_str = time_str[:-1]
            seconds = int(seconds_str)

        time_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return time_formatted
    except ValueError:
        return "10:00" #P54DT22H32M59S!? Days long streams?
    

#convert 4:27:46 time format into seconds
def time_to_seconds(time_str):
    if ':' not in time_str:
        return int(time_str)  # Return seconds directly if input is in "xx" format
    else:
        time_components = time_str.split(':')
        if len(time_components) == 2:
            m, s = map(int, time_components)
            total_seconds = m * 60 + s
        else:
            h, m, s = map(int, time_components)
            total_seconds = h * 3600 + m * 60 + s
        return total_seconds
