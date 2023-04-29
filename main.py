import os
import sqlite3

from convert_json_into_csv import convert_json_into_csv
from create_database import create_database
from dynamic_clustering import (clusterize, find_optimal_cluster_size,
                                get_category_names_from_openai,
                                update_category_keywords)
from fixed_clustering import (categorize_remaining_channels,
                              get_category_keywords_from_openai_api,
                              set_fixed_categories)
from import_data_into_db import (delete_extra_long_videos, delete_orphans,
                                 insert_data_into_database)
from logger_setup import setup_logger
from sql_queries import (show_most_watched_categories,
                         show_most_watched_channels)
from update_keywords import update_channel_keywords, update_video_keywords
from youtube_api import (get_youtube_client, save_channel_details,
                         save_video_details)

logger = setup_logger()


def main():
    
    logger.info("=" * 30)
    logger.info("Starting the process...")
    
    conn = sqlite3.connect(os.getenv("SQLITE_DB_FILE"))
    c = conn.cursor()

    #============================================================
    # STEP 1: Convert JSON file into CSV.
    #=============================================================
    convert_json_into_csv()
    #============================================================
    
    
    #============================================================
    # STEP 2: Create SQLite database and load CSV data there.
    #=============================================================
    create_database(conn, c)
    insert_data_into_database(conn, c)
    delete_extra_long_videos(conn, c, max_length=4)
    delete_orphans(conn, c)
    #============================================================
    
    
    #=============================================================
    # STEP 3. RETRIEVE VIDEO AND CHANNEL DETAILS FROM YOUTUBE API 
    #=============================================================
    youtube = get_youtube_client()     
    save_channel_details(youtube, conn, c)
    save_video_details(youtube, conn, c)
    #=============================================================
    
    
    #=============================================================
    # STEP 4. FIND SUITABLE KEYWORDS FOR VIDEOS AND CHANNELS
    #=============================================================
    update_video_keywords(conn, c)
    update_channel_keywords(conn, c)
    #=============================================================
    
    
    #=============================================================
    # STEP 5 DYNAMIC CATEGORIZATION
    # You can let the app to divide the channels into categories 
    #=============================================================
    cluster_size = find_optimal_cluster_size(c, k_max=10)
    clusterize(conn, c, cluster_size) 
    update_category_keywords(conn, c)
    get_category_names_from_openai(conn, c)
    #=============================================================
    
    #==========================================================
    # STEP 5 FIXED CATEGORIZATION
    # If you are not happy with the dynamically created 
    # categories, you can define them manually.
    #=============================================================
    #set_fixed_categories(conn, c)
    #get_category_keywords_from_openai_api(conn, c)    
    #categorize_remaining_channels(conn, c)
    #==========================================================
    
    show_most_watched_categories(conn)
    show_most_watched_channels(conn)
    
    conn.close()
    logger.info("Process completed.")
    
if __name__ == "__main__":
    main()
    