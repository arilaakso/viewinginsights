import pandas as pd

def show_most_watched_categories(conn):
    print("\nMOST WATCHED CATEGORIES")
    
    s = """
    SELECT 
        c.id,
        c.name,
        printf('%02d:%02d:%02d', SUM(v.length) / 86400, (SUM(v.length) % 86400) / 3600, (SUM(v.length) % 3600) / 60) AS 'dd:hh:mm',
        COUNT(v.id) AS video_count,
        (
            SELECT GROUP_CONCAT(ch_most_watched.name, ', ') 
            FROM (
                    SELECT ch2.name, COUNT(a2.video_id) AS watched_count
                    FROM channel ch2
                    JOIN video v2 ON ch2.id = v2.channel_id
                    JOIN activity a2 ON a2.video_id = v2.id
                    WHERE a2.action = 'Watched'
                    AND ch2.category_id = c.id
                    GROUP BY ch2.id
                    ORDER BY watched_count DESC, ch2.name
                    LIMIT 15
                    ) AS ch_most_watched
        ) AS top_5_watched_channels
    FROM category c
    JOIN channel ch ON c.id = ch.category_id
    JOIN video v ON ch.id = v.channel_id
    JOIN activity a ON a.video_id = v.id
    WHERE a.action = 'Watched'
    GROUP BY c.id, c.name
    ORDER BY c.id;
        """

    print(pd.read_sql_query(s, conn).head(30).to_string(index=False))
    

def show_most_watched_channels(conn):
    print("\nMOST WATCHED CHANNELS")
    s = """
    SELECT ROW_NUMBER() OVER (ORDER BY COUNT(video.id) DESC) AS "#",
        channel.name AS "Channel name", 
        category.name AS "Category",
        (SUM(video.length) / 86400) || ' days ' || 
        ((SUM(video.length) % 86400) / 3600) || ' hours' as 'Total time',
        COUNT(video.id) as 'Total videos',
        printf('%02d:%02d', AVG(video.length) / 3600, (AVG(video.length) % 3600) / 60) AS 'Avg video length'
    FROM channel
    INNER JOIN video ON video.channel_id = channel.id
    INNER JOIN activity ON activity.video_id = video.id AND activity.action = 'Watched'
    INNER JOIN category ON category.id = channel.category_id
    GROUP BY channel.name
    ORDER BY COUNT(video.id) DESC
    LIMIT 30;
    """
            
    print(pd.read_sql_query(s, conn).head(30).to_string(index=False))
