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

semaphore = threading.Semaphore() # For .ini file synchronization.

# Increment 'conversions' stat in .ini file.
def update_conversions_ini():
    config.set('stats', 'conversions', str(int(config.get('stats', 'conversions')) + 1))
    with open('config.ini', 'w') as config_file:
        config.write(config_file)

def reply_to_submission(submission, gif_json):

    def gfy_field(prop):
        return gif_json['gfyItem'][prop]

    try:
        webm_size = str(round(int(gfy_field('webmSize'))/1000000, 2))
        mp4_size = str(round(int(gfy_field('mp4Size'))/1000000, 2))
        webm_url = gfy_field('webmUrl')
        mp4_url = gfy_field('mp4Url')
        num_of_conversions = config.get('stats', 'conversions')
    except KeyError:
        print("Key error...")
        return

    reply = f"""This post appears to be using Reddit's native video player.  \n
If your current device does not support v.redd.it, try one of these mirrors hosted over at Gfycat!  \n
* [**WEBM** ({webm_size} MB)]({webm_url})  \n\n* [**MP4** ({mp4_size} MB)]({mp4_url})  \n\n***
^(^I'm ^a ^beep-boop. ^**{num_of_conversions}** ^conversions ^so ^far!)
[^^[Github] ](https://github.com/aquelemiguel)
[^^[Banned ^^subs] ](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Banned-subreddits)
[^^[Support ^^me ^^♥️]](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Donations)
"""
    while True:
        try:
            submission.reply(reply)
            print("Upload complete!\n")
            break
        except praw.exceptions.APIException as e:
            print("Hit rate limit: " + e.message)
            time.sleep(30)
        except prawcore.exceptions.Forbidden as e: # Probably got banned while converting the video.
            print("Wasn't able to comment on: " + submission.url)
            break

def upload_to_gfycat(submission):
    media_url = submission.media['reddit_video']['fallback_url']

    try:
        urllib.request.urlretrieve(media_url, "cached/" + submission.id + ".mp4")
    except urllib.error.HTTPError:
        print("Post deleted!") # Probably the post was deleted.
        return

    while True:
        try:
            id = gfycat.upload_from_file("cached/" + submission.id + ".mp4")['gfyname']
            gif_json = gfycat.query_gfy(id)
            break
        except GfycatClientError:
            print("Upload error, sending back to cache.")
        except KeyError:
            print("Key error!")

    semaphore.acquire()
    update_conversions_ini()
    semaphore.release()

    reply_to_submission(submission, gif_json)
    os.remove("cached/" + submission.id + ".mp4")

    return

while True:
    try:
        for submission in reddit.subreddit('all').stream.submissions():
            try:
                if submission.domain == 'v.redd.it' and submission.media['reddit_video']['is_gif']:

                    # Checks whether bot is banned from this subreddit.
                    if submission.subreddit.user_is_banned:
                        print("Bot is banned from " + str(submission.subreddit) + ".")
                        continue

                        print("Match found: " + submission.url)
                        token = threading.Thread(target=upload_to_gfycat, args=(submission,))
                        token.start()

            except TypeError:
                print("This submission is NoneType. Dodging...")
                continue
    except prawcore.exceptions.ServerError:
        print("Issue on submission stream...")
