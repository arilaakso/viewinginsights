import logging
import re
import string

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from tqdm import tqdm

logger = logging.getLogger("app_logger")

# Ramdom keywords to be excluded, not very useful in categorization.
CUSTOM_STOP_WORDS = "best,better,breaking,care,center,channel,check,clip,comment,contact,content,day,dont,\
drone,dw,el,email,en,enjoy,et,facebook,follow,free,gm,guy,help,hope,im,improve,inquiry,instagram,\
know,latest,life,like,line,live,look,los,love,medium,model,new,news,performance,official youtube,official,\
online,youtube,channel,people,place,product,que,scene,service,short,start,state,subscribe,subscriber,\
support,thanks,thing,tiktok,time,topic,tv,twitter,u,use,video,videos,want,watch,\
welcome,world,year,youtube,youtube channel"
       
nltk.download("punkt")
nltk.download("stopwords")
nltk.download("wordnet")

ENGLISH_STOPWORD = stopwords.words("english")
CUSTOM_STOPWORDS = CUSTOM_STOP_WORDS.split(",") # For easier modification above.


# Updates video.keywords from title and description fields.
def update_video_keywords(conn, c, batch_size=1000):
    c.execute("""SELECT id, title, description, tags FROM video WHERE title IS NOT NULL OR description IS NOT NULL""")
    videos = c.fetchall()

    # Use parameterized queries
    update_query = """UPDATE video SET keywords = ? WHERE id = ?"""

    # Use a single SQL statement with multiple rows
    data = []
    for video in tqdm(videos):
        video_id = video[0]
        taglist = video[3]

        # Use tags only if available
        if taglist is not None:
            tagwords = taglist.replace(",", " ")
            cleaned = tokenize_text(tagwords)
        else:
            title = video[1]
            description = video[2] or ""  # use empty string if description is None
            cleaned = tokenize_text(title + " " + description)

        data.append((cleaned, video_id))

    # Update the database in batches
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        c.executemany(update_query, batch)
        conn.commit()

    logger.info("Updated keywords for %d videos", len(data))


# Cleans the text from numbers, punctuation, stopwords, and lemmatizes the words
def tokenize_text(text):
    
    text = text.lower()

    # Remove special characters, numbers, and punctuation
    text = "".join(c for c in text if c not in string.punctuation and not c.isdigit())

    # Remove URLs
    text = re.sub(r"http\S+", "", text)

    tokens = word_tokenize(text)
    
    # Remove typical irrelevant words.
    tokens = [word for word in tokens if word not in ENGLISH_STOPWORD]

    # Remove single character words.
    tokens = [word for word in tokens if len(word) > 1]
    
    # Change words to their root form
    lemmatizer = WordNetLemmatizer()
    tokens = [lemmatizer.lemmatize(word) for word in tokens]

    # For some reason these words don't work well with the lemmatizer.
    tokens = [word for word in tokens if word not in CUSTOM_STOPWORDS]
    
    # Remove duplicates
    tokens = set(tokens)
    text = " ".join(tokens)
    return text


# Updates channel.keywords from video.keywords. 
# Browses through all videos of the channel and picks the most frequent words.
def update_channel_keywords(conn, c):
    c.execute("""SELECT c.id, GROUP_CONCAT(v.keywords, ' ') AS all_video_keywords 
                 FROM channel c LEFT JOIN video v ON c.id = v.channel_id 
                 GROUP BY c.id""")
    channel_data = c.fetchall()

    # Use parameterized queries
    update_query = """UPDATE channel SET keywords = ? WHERE id = ?"""

    total_rows_affected = 0
    for channel in tqdm(channel_data):
        channel_id = channel[0]
        all_video_keywords = channel[1]
        
        if all_video_keywords is None:
            logger.info("Channel %s has no videos", channel_id)
            continue
        
        # Get top keywords collected from all videos of the channel
        top_words = extract_top_keywords(all_video_keywords, max_keywords=7)

        # Use a parameterized query to update the channel keywords
        c.execute(update_query, (top_words, channel_id))
        rows_affected = c.rowcount
        total_rows_affected += rows_affected

    conn.commit()

    logger.info("Updated keywords for %d channels", total_rows_affected)


# Extracts most frequent words from the given text.
def extract_top_keywords(text, max_keywords=10):
    
    # Remove punctuation and convert to lowercase.
    text = re.sub(r"[^\w\s]", "", text).lower()

    # Split text into words and count frequencies.
    words = text.split()
    freq = {}
    for word in words:
        if word in freq:
            freq[word] += 1
        else:
            freq[word] = 1

    # Sort words by frequency and return the top n words.
    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    top_words = [word[0] for word in sorted_words[:max_keywords]]

    return " ".join(top_words)
