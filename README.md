## Viewing Insights - Analyze your YouTube watching history

You can download your YouTube watching history from Google in JSON format.
The app categories the data and stores it in an SQLite database for further analysis.

This first version only categorizes and cleans the data. Data visualisation may be added later.
I have tested this with only my own data, and some tweaking may be needed to make it work with yours. Let me know if you have any issues.

## KNOWN LIMITATIONS
YouTube logs videos watched even if you don't watch them till the end. Therefore, total durations, and other statistics are affected by that. I don't think there is a good workaround for it.

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
  - Select OAuth client ID.
  - Select Application Type as Desktop app.
  - Select any name and click Create.
  - From the popup window that opens, click Download JSON. Close the window.
  - Take the JSON file you downloaded, rename it to `credentials.json` and place it in the app folder.
  - When you start the app, and the Youtube client object is created for the first time, the browser opens. 
    - In the browser, select your Google account and click Continue (not "Back to safety"). 
    - Grant access for your account to your newly created app.
    - It creates a `token.json` file in the app folder. It should be valid at least a few weeks.

3. **OpenAI API key**
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
    - `python3 -m venv venv`
    - `venv\Scripts\activate`
  - Install the required libraries:
    - `pip install -r requirements.txt`

## START THE APP from `main.py`
  - You can test it with the `watch-history.json` file included in the repo.
  - When you run the app the first time, you need to authenticate for Google API as 
    mentioned in prerequisites.
  - The app should:
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
 - The app creates additional tables like `video_stat` and `channel_stat` which are planned to use later. Statistics data is available when we call the YouTube API anyway, so why not store the data for the future. 
- In the `csv_data_into_db.py` file with `CHANNELS_NOT_TO_IMPORT` and `IMPORTANT_CHANNELS`, you can streer the import process. Youtube has streaming channels and other crazy long videos which may alter the watching stats. You can delete extra long videos with a `max_length` parameter.

STEP 3: Retrieve video and channel details from YouTube API.
 - The first time when you run the code, you need to authenticate with your Google account in a browser, see prerequisites.
 - In this step, the code browses through all channels from the DB and retrieves details from YouTube API.
 - After channels are done, the code browses through all videos. 
 - NOTE! The YouTube API has a daily quota limit of 10 000 requests. You may have to retrieve the data over a few days. Use `MAX_RESULTS` parameter for limiting the requests when testing. The code avoids retrieving the same data twice.
 - View counts, like counts, comment counts and video counts are also stored for future analysis.

STEP 4: Find suitable keywords for videos and channels.
 - The code collects keywords for videos from the title and description fields. I tried a few different approaches, not sure which one is the best.
 - For channel keywords, it first combines all channel's video keywords together and picks the most common ones.
 - You can rerun this step multiple times and exclude some words by adding them in `update_keywords.by` file's `CUSTOM_STOP_WORDS` list.

STEP 5, Dividing channels into categories. You have two options:
DYNAMIC CATEGORY OPTION
 - The code uses KMeans clustering to find out how many categories would be optimal. It does a decent job but may not be what you wanted.
 - Then it creates a recommended amount of categories into DB.
 - Next, it finds the best keywords to describe the category using keywords from channels the belong to that category.
 - Lastly, it asks from OpenAI API names for the categories based on the keywords.
 - This way, using the API won't get too expensive, getting all 10-20 category names will cost maybe $0.01.
 - It's likely you don't agree all categorizations done by the app. You can try to play with it by:
   - Setting up the `cluster_size` manually 
   - Adding or removing words from `CUSTOM_STOP_WORDS` list
   - Adjusting the keyword count in the code.

If you want to have more control over the categories, you can do it manually with
FIXED CATEGORY OPTION
 - Define fixed categories at the beginning of the `fixed_clustering.py` file.
 - You can first define only category names, run it, and see how well the code categorizes the channels.
 - It calls OpenAI API to get possible keywords based on the category name.
 - Then it compares those keywords to channels' keywords and finds the best match using cosine similarity.
 - You check the results by executing `show_most_watched_categories()` method in the end. 
   If some channels are in a wrong category, you can fix it by defining it in the `FIXED_CHANNEL_CATEGORIES` structure. 
   That may require 10-100 iterations, depends on how perfect you want to be.

All comments and improvements are welcomed!

Some examples from the data (more analysis and visualizations to come):

![Most watched channels](images/most_watched_channels.png?raw=true)

![Most watched categories](images/most_watched_categories.png?raw=true)