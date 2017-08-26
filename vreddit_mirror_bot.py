import os
import time
import configparser
import sys
import praw
import prawcore
import json
import threading
import urllib

from gfycat.client import GfycatClient
from gfycat.error import GfycatClientError

# ConfigParser setup.
config = configparser.ConfigParser()
config.read('config.ini')

reddit = praw.Reddit(
    client_id=config.get('reddit', 'client_id'),
    client_secret=config.get('reddit', 'client_secret'),
    username=config.get('reddit', 'username'),
    password=config.get('reddit', 'password'),
    user_agent='vredditmirrorbot by /u/blinkroot'
)
gfycat = GfycatClient()

cached_submissions = []

# TODO: Open a thread for every link.
def cached_links_handler():
    while True:
        for i, submission in enumerate(cached_submissions):
            print("Handling: " + submission.url)
            if upload_to_gfycat(submission) == 'remove':
                cached_submissions.remove(submission)
            time.sleep(10)

# Increment 'conversions' stat in .ini file.
def update_conversions_ini():
    config.set('stats', 'conversions', str(int(config.get('stats', 'conversions')) + 1))
    with open('config.ini', 'w') as config_file:
        config.write(config_file)

def reply_to_submission(submission, gif_json):

    # TODO: Find a better place for this mess.
    def gfy_field(prop):
        return gif_json['gfyItem'][prop]

    webm_size = str(round(int(gfy_field('webmSize'))/1000000, 2))
    mp4_size = str(round(int(gfy_field('mp4Size'))/1000000, 2))

    webm_url = gfy_field('webmUrl')
    mp4_url = gfy_field('mp4Url')

    num_of_conversions = config.get('stats', 'conversions')

    reply = f"""\
            This post appears to be using Reddit's own video player.
            If your current device does not support v.redd.it, try these mirrors hosted over at Gfycat!  \n
            * [**WEBM** (${webm_size} MB)](${webm_url})  \n\n* [**MP4** (${mp4_size} MB)](${mp4_url})  \n\n***
            ^(^I'm ^a ^beep-boop ^made ^by ^/u/blinkroot. ^So ^far, ^I've ^converted ^**${num_of_conversions}** ^videos!)\
             [^^github. ](https://github.com/aquelemiguel) [^^support ^^me. ^^♥️](https://www.paypal.me/aquelemiguel/)
            """

    while True:
        try:
            submission.reply(reply)
            print("Upload complete!\n")
            break
        except praw.exceptions.APIException as e:
            print("Hit rate limit: " + e.message)
            time.sleep(30)
            continue

        # Probably banned from this subreddit.
        except prawcore.exceptions.Forbidden as e:
            print("Wasn't able to comment on: " + submission.url)
            break

def upload_to_gfycat(submission):
    media_url = submission.media['reddit_video']['fallback_url']

    try:
        urllib.request.urlretrieve(media_url, "cached/" + submission.id + ".mp4")
    except urllib.error.HTTPError:
        print("URL retrieval forbidden, retrying...")
        return 'retry'

    try:
        id = gfycat.upload_from_file("cached/" + submission.id + ".mp4")['gfyname']
    except GfycatClientError:
        print("Upload error, sending back to cache.")
        return 'retry'
    except KeyError:
        print("Key error!")
        return 'retry'

    gif_json = {}

    # Ensures the video has already been uploaded.
    while True:
        gif_json = gfycat.query_gfy(id)
        if not gif_json == None:
            break

        print("Upload still isn't complete.")
        time.sleep(5)

    update_conversions_ini()

    reply_to_submission(submission, gif_json)
    os.remove("cached/" + submission.id + ".mp4")

    return 'remove'

t1 = threading.Thread(target=cached_links_handler)
t1.start()

try:
    stream = reddit.subreddit('all').stream.submissions()
except prawcore.exceptions.ServerError:
    print("Temporary issue extracting new submissions...")

for submission in stream:
    try:
        if submission.domain == 'v.redd.it' and submission.media['reddit_video']['is_gif']:
            print("Match found: " + submission.url)
            cached_submissions.append(submission)
    except TypeError:
        print("This submission is NoneType. Dodging...")
        continue
