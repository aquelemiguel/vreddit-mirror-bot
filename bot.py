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

'''
imgur = ImgurClient(config.get('imgur', 'client_id'), config.get('imgur', 'client_secret'))
#urllib.request.urlretrieve('https://v.redd.it/d5vdyq8qv9hz/DASH_9_6_M', 'video.mp4')
#ff = ffmpy.FFmpeg(inputs={'video.mp4': None}, outputs={'out.gif': None})
#ff.run()

print("done")
#i = imgur.upload_from_path('out.gif')
i = gfycat.upload_from_file('video.mp4')
print("done2")
print(i)

sys.exit()
'''

gfycat = GfycatClient()
#json_gfy = gfycat.query_gfy(gfycat.upload_from_url('https://v.redd.it/d5vdyq8qv9hz/DASH_9_6_M')['gfyname'])
#print(json_gfy)
#print(gfycat.upload_from_file('video.mp4'))
#sys.exit()

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

        line1 = "This post appears to be using Reddit's own video player.  \n"
        line2 = "If your current device does not support v.redd.it, try this mirror!  \n\n"
        line3 = "* [**Desktop** (Gfycat)](" + gif_json['webmUrl'] + ")  \n* [**Mobile** (Gfycat)](" + gif_json['webpUrl'] + ")  \n\n***\n"
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
