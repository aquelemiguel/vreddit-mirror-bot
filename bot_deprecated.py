import time
import configparser
import sys
import praw
import json
import threading
from gfycat.client import GfycatClient
from gfycat.error import GfycatClientError

# ConfigParser setup.
config.read('config.ini')

reddit = praw.Reddit(
    client_id=config.get('reddit', 'client_id'),
    client_secret=config.get('reddit', 'client_secret'),
    username=config.get('reddit', 'username'),
    password=config.get('reddit', 'password'),
    user_agent='vredditmirrorbot by /u/blinkroot'
)
gfycat = GfycatClient()

s = gfycat.query_gfy(gfycat.upload_from_url('https://v.redd.it/qhnd50meeohz/DASH_9_6_M')['gfyname'])
print(str(s['gfyItem']))
sys.exit()

for submission in reddit.subreddit('all').stream.submissions():

    # Avoids sudden 'None' objects crawling in.
    if submission == None:
        continue

    elif submission.domain == 'v.redd.it' and submission.media['reddit_video']['is_gif']:

        print("Match found: " + submission.url)
        media_url = submission.media['reddit_video']['fallback_url']

        # Attempts to upload. Gfycat's API doesn't cooperate, sometimes.
        try:
            gif_json = gfycat.query_gfy(gfycat.upload_from_url(media_url)['gfyname'])
        except GfycatClientError:
            cached_submissions.append(submission)
            print("Caching: " + submission.url + "\n")
            continue

        # Confirms that the converted URL matches the provided.
        if not gif_json['gfyItem']['url'] == media_url:
            print(gif_json['gfyItem']['url'] + " doesn't match " + media_url + " on post " + submission.url + "\n")
            continue

        # Increment 'conversions' stat in .ini file.
        config.set('stats', 'conversions', str(int(config.get('stats', 'conversions')) + 1))
        with open('config.ini', 'w') as config_file:
            config.write(config_file)
            config_file.close()

        # TODO: Find a better place for this mess.
        line1 = "This post appears to be using Reddit's own video player.  \n"
        line2 = "If your current device does not support v.redd.it, try these mirrors hosted over at Gfycat!  \n\n"
        line3 = "* [**Desktop** (.webm)](" + gif_json['gfyItem']['webmUrl'] + ")  \n\n* [**Mobile** (.mp4)](" + gif_json['gfyItem']['mobileUrl'] + ")  \n\n***\n"
        line4 = "^(^I'm ^a ^beep-boop ^made ^by ^/u/blinkroot. ^So ^far, ^I've ^converted ^**" + config.get('stats', 'conversions') + "** ^videos!) [^^github. ](https://github.com/aquelemiguel) [^^help ^^me ^^stay ^^online.](https://www.paypal.me/aquelemiguel/)"

        while True:
            try:
                submission.reply(line1 + line2 + line3 + line4)
                print("Upload complete!\n")
                break
            except praw.exceptions.APIException as e:
                print("Hit rate limit: " + e.message)
                time.sleep(30)
                continue
