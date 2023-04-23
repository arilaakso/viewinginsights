import json
import logging
import os
import pandas as pd
from tqdm import tqdm
from dateutil.parser import parse

logger = logging.getLogger("app_logger")

JSON_FILENAME = "watch-history.json"


def convert_json_into_csv():

    csv_file =os.getenv("CSV_FILE")

    logger.info(f"Start converting {JSON_FILENAME} into {csv_file}...")
    
    with open(JSON_FILENAME, "r", encoding="UTF-8") as file:
        data = file.read()

    df = get_json_data_into_dataframe(data)
    
    # utf-8-sig includes emojis, not sure if needed.
    df.to_csv(csv_file, sep=";", index=False, encoding="utf-8-sig")
    
    logger.info(f"{len(df)} videos added in {csv_file}")


# Reads the JSON file into a pandas DataFrame. 
# The code expects that the JSON file contains only "Watched" actions.
def get_json_data_into_dataframe(json_data):
    json_list = json.loads(json_data)
    output = []
    unavailable_videos = 0
    videos_total = 0
    
    # Browse through the JSON entries and extract the relevant information.
    for item in tqdm(json_list):
        videos_total += 1
        
        formatted_datetime = parse(item["time"]).strftime("%Y-%m-%d %H:%M:%S")

        action = "Watched"
        video_title = item["title"]

        # Skip videos that have been removed or are not available. 
        if video_title in ["Watched a video that has been removed", "Visited YouTube Music"]:
            unavailable_videos += 1
            continue

        video_title = video_title.replace("Watched ", "")
        video_url = item["titleUrl"]

        if "subtitles" in item and len(item["subtitles"]) > 0:
            channel_name = item["subtitles"][0]["name"]
            channel_url = item["subtitles"][0]["url"]
        else:
            unavailable_videos += 1
            continue

        output.append({
            "Timestamp": formatted_datetime,
            "Action": action,
            "Title": video_title,
            "URL": video_url,
            "Channel": channel_name,
            "Channel URL": channel_url
        })

    if unavailable_videos > 0:
        logger.info(f"{unavailable_videos} unavailable videos skipped")
    
    return pd.DataFrame(output)