## Viewing Insights - Analyze your YouTube watching history

You can download your YouTube watching history from Google in JSON format.
The app categories the data and stores it in an SQLite database for further analysis.

Some graphs are plotted in Jupyter notebooks in 'plots' folder.
I have tested this with only my own data, and some tweaking may be needed to make it work with yours. 

## KNOWN LIMITATIONS
- YouTube logs videos watched soon after you have started watching it. Calculating total watch time from that data is not really realistic. I don't think there is a good workaround for it.


## PREREQUISITES
1. **YouTube `watch-history.json` file from Google Takeout**
  - Go to https://takeout.google.com/
  - From the "Create a new export" unselect all except "YouTube and YouTube Music".
  - Select JSON format and from the other list select "History".
  - Click "Next step" and select Export once, ZIP and any file size.
  - Click "Create export".
  - In a moment, you'll get the data as an email. 
  - Download the ZIP file and extract the `watch-history.json` file to the app directory.

2. **Google API key**
  - Create a new project in Google Cloud Platform: https://console.cloud.google.com/
  - Go to your project page and click "+CREATE CREDENTIALS".
  - Under "Create credentials", select "API key" and then click "Create".
  - Copy the newly created API key.

3. **OpenAI API key**
  - App asks names/keywords for categories from OpenAI's LLM. 
  - Create an account at https://openai.com/
  - You need to add credit card details but you may get free credits for $20(?) valid for a month.
  - Asking names or keywords with this app for 20 categories may cost around $0.01.
  - In the app folder, rename `.env_template` file to `.env`.
  - Create a new API key and update it in the `.env` file. 

4. **SQLite-web app (optional)**
  - If you want to query your data in the database, you can install SQLite-web app. https://github.com/coleifer/sqlite-web
  - It runs locally on a Flask web server, and you can browse the tables with a browser while iterating the data with this app. 
  - `sql_queries.py` has some example queries which you can output in the console, but I recommend 
    using SQLite-web app and copy-paste the queries there. It's much easier to read the results and write your own SQL queries.


## INSTALLATION with VSCode and Windows:
  - Pull the data from GitHub using `git clone http://github.com/arilaakso/viewinginsights.git`
  - Open the folder in VSCode
  - Create and activate a virtual environment:
    - `python -m venv venv`
    - `venv\Scripts\activate`
  - Install the required libraries:
    - `pip install -r requirements.txt`
  - Rename `.env_template` to `.env` and add your OpenAI API and GOOGLE API keys.
  - You can test the app with the `watch-history.json` file included in the repo.
  
## START THE APP from `main.py`
  - By default, the app should:
    - Convert the JSON file into CSV.
    - Create an SQLite database, insert the CSV data.
    - Retrieve video and channel details from YouTube API.
    - Find suitable keywords for videos and channels.
    - Categorize channels into 10-20 categories.
    - Show the most watched categories in the console.
    - The app writes a log in `app.log` file.

If that works, you can start playing with your own data. 

Below is a more detailed description of the steps:

## STEP DESCRIPTIONS
STEP 1: Convert JSON file into CSV.
 - The data could be inserted directly from JSON into DB, but for debugging purposes, CSV is nice format have.

STEP 2: Create an SQLite database and import the data.
 - The app creates additional tables like `video_stat` and `channel_stat` which are planned to use later. Statistics data is available when the YouTube API is called anyway, so why not store the data for the future. 
- In the `csv_data_into_db.py` file with `CHANNELS_NOT_TO_IMPORT` and `IMPORTANT_CHANNELS`, you can streer the import process. Youtube has streaming channels and other crazy long videos which may alter the watching stats. You can delete extra long videos with a `max_length` parameter.

STEP 3: Retrieve video and channel details from YouTube API.
 - The code browses through all channels from the DB and retrieves details from YouTube API.
 - NOTE! The YouTube API has a daily quota limit of 10 000 requests. You may have to retrieve the data over a few days. Use `MAX_RESULTS` parameter for limiting the requests when testing. The code avoids retrieving the same data twice.
 - View counts, like counts, comment counts and video counts are also stored for future analysis.

STEP 4: Find suitable keywords for videos and channels.
 - The code collects keywords for videos from the title and description fields. 
 - For channel keywords, it first combines all channel's video keywords together and picks the most common ones.
 - You can rerun this step multiple times and exclude some words by adding them in `update_keywords.by` file's `CUSTOM_STOP_WORDS` list.

STEP 5, Dividing channels into categories. You have two options:
DYNAMIC CATEGORY OPTION
 - This does not provide good results but it's automatic.
 - The code uses KMeans clustering to find out how many categories would be optimal. It does a decent job but may not be what you wanted.
 - Next, it finds the best keywords to describe the category using keywords from channels the belong to that category.
 - Lastly, it asks from OpenAI API names for the categories based on the keywords.
 - This way, using the API won't get too expensive, getting all 10-20 category names will cost maybe $0.01.
 - It's likely you don't agree all categorizations done by the app. You can try to play with it by:
   - Setting up the `cluster_size` manually 
   - Adding or removing words from `CUSTOM_STOP_WORDS` list
   - Adjusting the keyword count in the code.

If you want to have more control over the categories, you can do it manually with
FIXED CATEGORY OPTION (recommended)
 - Define fixed categories and some channels at the beginning of the `fixed_clustering.py` file in `FIXED_CHANNEL_CATEGORIES`.
 - `In KEYWORD_CATEGORY_MAP` keywords are used for the channels that are not yet mapped to any category. 
 - It calls OpenAI API to get keywords based on the category name.
 - The code uses fixed categories as a training material for categorizing the remaining channels.
 - You check the results by executing `show_most_watched_categories()` method in the end, although I recommend using SQLite-web app or similar for querying the data.
   Getting the categorization right may require 10-100 reruns, depending on how perfect you want it to be.
 - You can cache OpenAI results with `read_from_cache` parameter if you get tired of waiting for the API.

Some examples from the data:

![Views by weekday hours](images/views_by_weekday_hours.png?raw=true)

![Views by hour](images/views_by_hour.png?raw=true)

![Video lengths and counts](images/video_lengths.png?raw=true)