"""
THIS FILE IS USED FOR FIXED CLUSTERING ONLY
"""

import logging
import os

import openai
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from tqdm import tqdm

logger = logging.getLogger("app_logger")

# Channels that get easily misclassified. 
# These lists are processed first, then the KEYWORD_CATEGORY_MAP keywords.
FIXED_CHANNEL_CATEGORIES = {
    "Chess": 
        ["Magnus Carlsen"],
    "Podcasts":                 
        ["Lex Fridman", "Andrew Huberman", "PowerfulJRE", "JRE Clips"],
    "Science and Technology":   
        ["ColdFusion", "Neuralink", "NASA", "Arvin Ash", "SpaceX", "Up and Atom", "Cool Worlds", \
         "Everyday Astronaut", "Steve Mould"],
    "Entertainment":           
        ["MrBeast", "The Slow Mo Guys", "The Slow Mo Guys 2", "Top Fives", "FORMULA 1", "GoPro"],
    "Outdoor and Backpacking":  
        [""],
    "Building and DIY":         
        ["Mark Rober", "Erik Grankvist", "Martijn Doolaard"],
    "AI and Programming":       
        ["AI Explained", "Two Minute Papers", "Robert Miles", "Sebastian Lague", "Matthew Berman"],
    "Education and Learning":   
        ["Big Think", "UsefulCharts", "TED-Ed", "Geography Now",\
        "TEDx Talks", "Stanford", "Talks at Google", "WIRED",\
        "Kurzgesagt – In a Nutshell", "Be Smart"],
    "Tech Reviews":             
        ["Emmett Short", "Marques Brownlee", "Adam Savage’s Tested"],
    "Travel and Vlogs":
        [""],
    "Documentaries and Movies": 
        ["VICE News", "VICE", "Venture City", "Smithsonian Channel", "DUST"],
    "Music Videos":             
        ["Above & Beyond", "Violet Orlandi"],
    "News and Politics":        
        ["United Nations", "The White House"],
    "Psychology and Philosophy":
        ["Pursuit of Wonder", "Better Ideas", "Closer to Truth"]
}

# If the channel is not set by above rules, it is set by the following keywords. 
# Order of the list matters, put more specific keywords first and generic on the bottom.
KEYWORD_CATEGORY_MAP = [
    ("chess", "Chess"),
    ("outdoor,camping,backpacking,bushcraft", "Outdoor and Backpacking"),
    ("philosophy,exurb", "Psychology and Philosophy"),
    ("microsoft,data, AI ,python", "AI and Programming"),
    ("scientist,science", "Science and Technology"),
    ("university,education", "Education and Learning"),
    ("movie,history,documentary,trailers", "Documentaries and Movies"),
    ("primitive,woodworking", "Building and DIY"),
    ("podcast", "Podcasts"),
    ("virtual reality", "Tech Reviews"),
    ("music video", "Music Videos"),
    ("news,politics,bloomberg", "News and Politics"),
    ("travel,vlog", "Travel and Vlogs"),
]

# Insert the fixed categories into the database and set the category_id for some channels.
def set_fixed_categories(conn, c, delete_categories=True):

    # Delete all rows from the category table first for rerunning purposes.
    if delete_categories:
        c.execute("DELETE FROM category")
    
    c.execute("UPDATE channel SET category_id = NULL")

    # Insert the fixed categories into the database.
    for category, channel_names in FIXED_CHANNEL_CATEGORIES.items():

        if delete_categories:
            c.execute("INSERT INTO category (name) VALUES (?)", (category,))
            category_id = c.lastrowid
        else:
            category_id = c.execute("SELECT id FROM category WHERE name = ?", (category,)).fetchone()[0]
            
        for channel_name in channel_names:
            c.execute("UPDATE channel SET category_id = ? WHERE LOWER(name) = LOWER(?)", (category_id, channel_name.lower()))

    for keywords, category in KEYWORD_CATEGORY_MAP:
        set_categories_with_keyword(conn, c, keywords, category)

    conn.commit()

    logger.info("Fixed categories inserted into database")


# Set the category_id for channels that contain the specified keyword in their name.
def set_categories_with_keyword(conn, c, words, category):

    c.execute("SELECT id FROM category WHERE name = ?", (category,))
    category_id = c.fetchone()[0]

    word_list = words.split(",")

    # get all channels containing the specified keyword in their name.
    for word in word_list:
        c.execute(f"SELECT id, name FROM channel WHERE category_id IS NULL AND (LOWER(name) LIKE '%{word.lower()}%' OR LOWER(keywords) LIKE '%{word.lower()}%')")

        channels = c.fetchall()
        for channel in channels:
            channel_id = channel[0]

            c.execute("UPDATE channel SET category_id = ? WHERE id = ? AND channel.category_id IS NULL", (category_id, channel_id))

    conn.commit()


# Use Random Forest Classifier to predict the category for channels that have no category set.
# The model is trained with the channels that were set with the fixed names and keywords.
def categorize_remaining_channels(conn, c):
    
    labeled_channels = pd.read_sql_query("""
        SELECT c.id, c.category_id, GROUP_CONCAT(v.keywords, ' ') AS keywords
        FROM channel AS c
        INNER JOIN category AS cat ON cat.id = c.category_id
        INNER JOIN video AS v ON v.channel_id = c.id
        WHERE c.category_id IS NOT NULL
        GROUP BY c.id, c.category_id;
        """, conn)

    unlabeled_channels = pd.read_sql_query("""
        SELECT c.id, c.category_id, GROUP_CONCAT(v.keywords, ' ') AS keywords
        FROM channel AS c
        INNER JOIN video AS v ON v.channel_id = c.id
        WHERE c.category_id IS NULL
        GROUP BY c.id, c.category_id;
        """, conn)

    X = labeled_channels["keywords"]
    y = labeled_channels["category_id"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)

    classifiers = {
        "RandomForest": RandomForestClassifier(),
    }

    for name, classifier in classifiers.items():
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer()),
            (name, classifier),
        ])

        pipeline.fit(X_train, y_train)

        y_pred = pipeline.predict(X_test)
        logger.info(f"Accuracy: {accuracy_score(y_test, y_pred)}")

    unlabeled_X = unlabeled_channels["keywords"]
    unlabeled_pred = pipeline.predict(unlabeled_X)

    # Add the predicted categories to the unlabeled_channels DataFrame
    unlabeled_channels["predicted_category_id"] = unlabeled_pred

    for i, row in enumerate(unlabeled_channels.itertuples()):
        channel_id = row.id
        pred_cat_id = int(unlabeled_pred[i])

        c.execute("UPDATE channel SET category_id = ? WHERE id = ?", (pred_cat_id, channel_id))

    conn.commit()
    
    logger.info(f"Remaining {len(unlabeled_channels)} channels categorized")


# Ask OpenAI to provide keywords based on the category name.
import os

import openai
from tqdm import tqdm

def get_category_keywords_from_openai_api(conn, c, num_keywords=16, read_from_cache=False):

    openai.api_key = os.getenv("OPENAI_API_KEY")

    logger.info("Asking keywords for categories from OpenAI...")

    c.execute("SELECT id, name, cached_keywords FROM category")
    categories = c.fetchall()

    for row in tqdm(categories):
        cached_keywords = row[2]

        if read_from_cache and cached_keywords is not None:
            keywords = cached_keywords
        else:
            prompt = f"Generate {num_keywords} relevant keywords for categorizing YouTube channels. The keywords \
                should be like tags that often describe the content of the videos. Provide the words in a comma-separated list \
                without any other text. The category name: {row[1]}. Keywords:"

            response = openai.Completion.create(
                model="text-davinci-003",
                prompt=prompt,
                temperature=0.1,
                max_tokens=40,
                top_p=1.0,
                frequency_penalty=0.8,
                presence_penalty=0.0
            )

            keywords = response.choices[0].text.strip()

        c.execute(f'UPDATE category SET keywords = "{keywords}", cached_keywords = "{keywords}" WHERE id = {row[0]}')

    conn.commit()

    logger.info("Keywords from OpenAI saved in the category table")
    