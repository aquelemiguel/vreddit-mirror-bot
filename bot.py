import time
import configparser
import sys
import praw
import json
import urllib.request
import ffmpy

from gfycat.client import GfycatClient
from gfycat.error import GfycatClientError
from imgurpython import ImgurClient

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

for submission in reddit.subreddit('all').stream.submissions():
    if submission.domain == 'v.redd.it' and submission.media['reddit_video']['is_gif']:
        print("Match found: " + submission.url)

        media_url = submission.media['reddit_video']['fallback_url']
        gif_json = {}

        # Attempts to upload three times, while gfycat doesn't fix their shit.
        for i in range(0, 3):
            try:
                gif_json = gfycat.query_gfy(gfycat.upload_from_url(media_url)['gfyname'])
                break
            except GfycatClientError:
                print("Encoding errors...")
                time.sleep(30)

        # Checks whether the upload was successful.
        if gif_json == {}:
            print("Ignoring: " + submission.url)
            continue

        # TODO: Find a better place for this mess.
        line1 = "This post appears to be using Reddit's own video player.  \n"
        line2 = "If your current device does not support v.redd.it, try these mirrors hosted over at Gfycat!  \n\n"
        line3 = "* [**Desktop** (.webm)](" + gif_json['gfyItem']['webmUrl'] + ")  \n* [**Mobile** (.mp4)](" + gif_json['gfyItem']['mobileUrl'] + ")  \n\n***\n"
        line4 = "^(i'm a beepboop made by /u/blinkroot.) ^(pm him for suggestions and issues. )^[github.](https://github.com/aquelemiguel) ^[donate!](https://www.paypal.me/aquelemiguel/)"

        while True:
            try:
                submission.reply(line1 + line2 + line3 + line4)
                print("Done!\n")
                break
            except praw.exceptions.APIException as e:
                print("Hit rate limit: " + e.message)
                time.sleep(30)
                continue
