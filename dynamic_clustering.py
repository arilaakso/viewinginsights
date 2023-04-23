# THIS FILE IS USED FOR DYNAMIC CLUSTERING ONLY

import logging
import os
from matplotlib import pyplot as plt

import openai
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm import tqdm

from update_keywords import extract_top_keywords

logger = logging.getLogger("app_logger")
             
 
# Gets the most often used keywords from all channels of the category
def get_top_channel_keywords(conn, cluster, max_keywords=20):
    cursor = conn.cursor()

    # Get all channel keywords for a given cluster number
    cursor.execute("""
        SELECT c.keywords
        FROM channel c
        INNER JOIN category cat ON c.category_id = cat.id
        WHERE cat.cluster_number = ?
    """, (cluster,))

    rows = cursor.fetchall()

    # Combine all keywords from all channels into a single string
    all_keywords = " ".join([row[0] for row in rows])
    
    # Extract the most frequent words
    top_words = extract_top_keywords(all_keywords, max_keywords=max_keywords)
    
    return top_words


# Updates the category.keywords field based on the most used words in that category videos.
def update_category_keywords(conn, c):

    c.execute("SELECT cluster_number FROM category")
    cluster_numbers = c.fetchall()

    # Loop over the cluster numbers and process the corresponding data
    for cluster in tqdm(cluster_numbers):
        
        number = cluster[0]
        
        top_channel_keywords = get_top_channel_keywords(conn, number, max_keywords=20)
        
        c.execute("UPDATE category SET keywords = ? WHERE cluster_number = ?", (top_channel_keywords, cluster[0]))
        
    conn.commit()
    
    logger.info(f"Keywords updated for {len(cluster_numbers)} channels")
    
    
# Divides channels in categories using KMeans clustering
def clusterize(conn, c, cluster_count):
    
    # Delete the contents so that we can start from scratch
    c.execute("DELETE FROM category")
    
    # get all keywords from all channels
    c.execute("SELECT id, keywords FROM channel WHERE is_deleted IS NULL AND keywords IS NOT NULL")

    # Fetch all the channel ids and keywords as a list of tuples
    ids_and_keywords = c.fetchall()

    # Extract the ids and tokens (keywords) from the list of tuples
    ids = [row[0] for row in ids_and_keywords]
    tokens = [row[1] for row in ids_and_keywords]

    vectorizer = TfidfVectorizer()

    # Fit the vectorizer using the combined preprocessed data (keywords from all channels)
    vectorizer.fit(tokens)

    # Transform the keywords to a tf-idf matrix
    tfidf_matrix = vectorizer.transform(tokens)

    # Kmeans groups similar data points together.
    kmeans = KMeans(n_clusters=cluster_count, n_init=10, random_state=0).fit(tfidf_matrix)

    # The cluster_labels list contains a suitable cluster number for each channel.
    cluster_labels = kmeans.labels_
    
    # Loop over the categories and update the database
    for i, cluster in enumerate(cluster_labels):
        
        # Check if a category with the given cluster number already exists in the table.
        c.execute(f"SELECT id FROM category WHERE cluster_number = {cluster}")
        result = c.fetchone()

        if result is not None:
            # If the category exists, use its id to update the category_id field in the channels table
            category_id = result[0]
        else:
            # If the category doesn't exist, insert a new row in the categories table with the new cluster number
            c.execute(f"INSERT INTO category (cluster_number) VALUES ('{cluster}')")
            
            # Get the id of the newly inserted row
            category_id = c.lastrowid
            
        # Update the category_id for the current channel
        c.execute(f"UPDATE channel SET category_id = {category_id} WHERE id = {ids[i]}")

    # Commit the changes to the database
    conn.commit()

    logger.info(f"Categories created: {cluster_count}")
    logger.info(f"Category set for {len(cluster_labels)} channels")
    

# Plots a graph to find the optimal number of categories
def find_optimal_cluster_size(c, k_max):
    c.execute("""SELECT id, keywords
             FROM channel 
             WHERE is_deleted IS NULL 
             AND keywords IS NOT NULL""")

    ids_and_words = c.fetchall()

    ids = [row[0] for row in ids_and_words]
    words = [row[1] for row in ids_and_words]

    vectorizer = TfidfVectorizer()

    # Fit the vectorizer using the combined preprocessed data
    vectorizer.fit(words)

    tfidf_matrix = vectorizer.transform(words)

    inertias = []
    for k in tqdm(range(1, k_max+1)):
        kmeans = KMeans(n_clusters=k, n_init=10, random_state=0).fit(tfidf_matrix)
        inertias.append(kmeans.inertia_)

    # Find elbow point
    diff = [inertias[i] - inertias[i-1] for i in range(1, len(inertias))]
    elbow_index = diff.index(max(diff)) + 1

    # You can plot the elbow curve on the screen to find optimal number of clusters
    '''
    plt.plot(range(1, k_max+1), inertias)
    plt.xlabel("Number of clusters")
    plt.ylabel("Inertia")
    plt.title("Elbow Curve")
    plt.show()
    '''
    logger.info(f"Optimal cluster size calculated to be {elbow_index} (max limit was {k_max})")
    
    return elbow_index


# Asks the OpenAI API to generate a name for each category based on the keywords.
def get_category_names_from_openai(conn, c):

    openai.api_key = os.getenv("OPENAI_API_KEY")

    c.execute(f"SELECT id, keywords FROM category")
    categories = c.fetchall()
    
    for row in tqdm(categories):
        
        prompt = f"Summarize a formal category title of a YouTube channels in 1-4 words, using these keywords as a guide: {row[1]}"
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            temperature=0.0,
            max_tokens=32,
            top_p=1.0,
            frequency_penalty=0.8,
            presence_penalty=0.0
        )
        
        name = response.choices[0].text.strip()
        
        #The model returns often a dot at the end of the name, which is not wanted
        name = name[:-1] if name.endswith(".") else name
        
        c.execute(f"UPDATE category SET name = '{name}' WHERE id = {row[0]}")
    
    conn.commit()
    
    logger.info(f"Keywords updated from OpenAI API for {len(categories)} categories")
    