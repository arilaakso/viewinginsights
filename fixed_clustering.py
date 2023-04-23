# THIS FILE IS USED FOR FIXED CLUSTERING ONLY

import logging
import os
import numpy as np
import openai
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

logger = logging.getLogger("app_logger")

# Channels that get easily misclassified. The rest are classified by keywords and cosine similarity.
FIXED_CHANNEL_CATEGORIES = {
    "Chess":                    ["Magnus Carlsen"],
    "Podcasts":                 ["Lex Fridman", "Andrew Huberman"],
    "Science and Technology":   ["TheBackyardScientist", "ColdFusion", "Neuralink", "NASA", "Arvin Ash", "SpaceX", \
                                 "Up and Atom", "Cool Worlds"],
    "Outdoor and Backbacking":  ["Ali Leiniö"],
    "Building and DIY":         ["Mark Rober", "Erik Grankvist", "Martijn Doolaard", "Primitive Skills"],
    "AI and Programming":       ["AI Explained", "Two Minute Papers", "Microsoft Visual Studio","Sebastian Lague"],
    "Tech Reviews":             ["Emmett Short", "Marques Brownlee", "Adam Savage’s Tested"],
    "Documentaries and Movies": ["HUMAN the movie", "Pecos Hank", "VICE News"],
}

# You can also set the category if a specific word appears in the channel title.
KEYWORD_CATEGORY_MAP = [
    ("movie", "Documentaries and Movies"),
    ("chess", "Chess"),
]

# Insert the fixed categories into the database and set the category_id for some channels.
def set_fixed_categories(conn, c):

    # Delete all rows from the category table first (for rerunning purposes).
    c.execute("DELETE FROM category")
    c.execute("UPDATE channel SET category_id = NULL")

    # Insert the fixed categories into the database.
    for category, channel_names in FIXED_CHANNEL_CATEGORIES.items():

        c.execute("INSERT INTO category (name) VALUES (?)", (category,))
        category_id = c.lastrowid

        for channel_name in channel_names:
            c.execute("UPDATE channel SET category_id = ? WHERE name = ?", (category_id, channel_name))

    # Set category choices based on keywords so that they don't need to be guessed later.
    for keyword, category in KEYWORD_CATEGORY_MAP:
        set_categories_with_keyword(conn, c, keyword, category)

    conn.commit()

    logger.info("Fixed categories inserted into database")
    
    
# Ask OpenAI to provide keywords based on the category name.
def get_category_keywords_from_openai_api(conn, c, num_keywords=15):
    
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
    logger.info("Asking keywords for categories from OpenAI...")
    
    c.execute(f"SELECT id, name FROM category WHERE keywords IS NULL")
    categories = c.fetchall()
    
    for row in tqdm(categories):
        
        prompt = f"I provide you a name for a YouTube video category. Provide { num_keywords } keywords that describe the category. \
                   Provide only the keywords in a comma-separated list without other text. The category name is: {row[1]}"
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            temperature=0.0,
            max_tokens=30,
            top_p=1.0,
            frequency_penalty=0.8,
            presence_penalty=0.0
        )
        
        keywords = response.choices[0].text.strip()
        
        c.execute(f"UPDATE category SET keywords = '{keywords}' WHERE id = {row[0]}")
    
    conn.commit()
    logger.info("Keywords from OpenAI saved in the DB")


# Match the channels to the categories based on their keywords.
def select_category_for_remaining_channels(conn, c):
    c.execute("SELECT id, name, keywords FROM channel WHERE is_deleted IS NULL AND category_id IS NULL")
    channels = c.fetchall()

    c.execute("SELECT id, keywords FROM category")
    categories = c.fetchall()

    for channel in tqdm(channels):
        channel_id = channel[0]
        channel_name = channel[1]
        channel_keywords = channel[2].split()
        
        best_category_id = find_best_category(channel_keywords, [(str(category[0]), category[1]) for category in categories])

        c.execute("UPDATE channel SET category_id = ? WHERE id = ?", (best_category_id, channel_id))

    conn.commit()


# Set the category_id for channels that contain the specified keyword in their name.
def set_categories_with_keyword(conn, c, word, category):

    c.execute("SELECT id FROM category WHERE name = ?", (category,))
    category_id = c.fetchone()[0]

    # get all channels containing the specified keyword in their name.
    c.execute("SELECT id, name FROM channel WHERE LOWER(name) LIKE ?", ('%{}%'.format(word.lower()),))
    channels = c.fetchall()

    for channel in tqdm(channels):
        channel_id = channel[0]
        
        c.execute("UPDATE channel SET category_id = ? WHERE id = ?", (category_id, channel_id))

    conn.commit()


# Find the best matching category for a channel based on the channel keywords and the category keywords.
def find_best_category(channel_keywords, category_keywords):
    
    # Combine channel keywords with category keywords.
    all_keywords = [' '.join(channel_keywords)] + [' '.join(category) for category in category_keywords]

    # Calculate TF-IDF matrix.
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(all_keywords)

    # Calculate cosine similarity.
    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])
    
    # Get the index of the category with the highest similarity score.
    best_category_index = np.argmax(similarities)

    # Return the category ID of the best matching category.
    return int(category_keywords[best_category_index][0])
