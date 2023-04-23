import pandas as pd

def show_most_watched_categories(conn):
    print("\nMOST WATCHED CATEGORIES")
    
    s = """WITH channel_lengths AS (
            SELECT
                channel.id AS channel_id,
                channel.name AS channel_name,
                channel.category_id,
                SUM(video.length) AS total_length,
                COUNT(video.id) AS total_videos
            FROM channel
            JOIN video ON channel.id = video.channel_id
            JOIN activity ON video.id = activity.video_id
            WHERE channel.is_deleted IS NULL
                AND video.is_deleted IS NULL
                AND activity.action = "Watched"
            GROUP BY channel.id
            HAVING total_length IS NOT NULL
            ),
            channel_ranks AS (
            SELECT
                channel_id,
                channel_name,
                category_id,
                total_length,
                total_videos,
                RANK() OVER (PARTITION BY category_id ORDER BY total_length DESC) AS rank
            FROM channel_lengths
            )
            SELECT
            category.name AS 'Category',
            CAST(SUM(channel_lengths.total_length) / (86400) AS TEXT) || ':' ||
            printf('%02d', CAST((SUM(channel_lengths.total_length) % 86400) / 3600 AS TEXT)) || ':' ||
            printf('%02d', CAST(((SUM(channel_lengths.total_length) % 86400) % 3600) / 60 AS TEXT)) AS 'Total time (dd:hh:mm)',
            SUM(channel_lengths.total_videos) AS 'Total videos',
            GROUP_CONCAT(channel_ranks.channel_name, ', ') AS 'Top channels'
            FROM category
            JOIN channel ON category.id = channel.category_id
            JOIN channel_lengths ON channel.id = channel_lengths.channel_id
            JOIN channel_ranks ON channel.id = channel_ranks.channel_id
            WHERE channel_ranks.rank <= 4
            GROUP BY category.id
            HAVING SUM(channel_lengths.total_length) IS NOT NULL
            ORDER BY SUM(channel_lengths.total_length) DESC;"""

    print(pd.read_sql_query(s, conn).head(30).to_string(index=False))
    

def show_most_watched_channels(conn):
    print("\nMOST WATCHED CHANNELS")
    s = """SELECT channel.name AS "Channel name",
                category.name AS "Category",
                (SUM(video.length) / 86400) || ':' ||
                printf('%02d', (SUM(video.length) % 86400) / 3600) || ':' ||
                printf('%02d', (SUM(video.length) % 3600) / 60) AS "Total time",
                COUNT(video.id) AS "Total videos"
            FROM channel
            INNER JOIN video ON video.channel_id = channel.id
            INNER JOIN activity ON activity.video_id = video.id AND activity.action = 'Watched'
            INNER JOIN category ON category.id = channel.category_id
            WHERE video.length IS NOT NULL AND video.is_deleted IS NULL AND channel.is_deleted IS NULL
            GROUP BY channel.id
            ORDER BY SUM(video.length) DESC
            LIMIT 30;"""
           
    print(pd.read_sql_query(s, conn).head(30).to_string(index=False))
    
