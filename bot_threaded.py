import time
import configparser
import sys
import praw
import json
import threading
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

# Confirms that the converted URL matches the provided.
def verify_matching_urls(gif_json, media_url):
    print("Verifying URLs...")
    if not gif_json['gfyItem']['url'] == media_url:
        print(gif_json['gfyItem']['url'] + " doesn't match " + media_url + " on post " + submission.url + "\n")
        return False
    return True

# Increment 'conversions' stat in .ini file.
def update_conversions_ini():
    print("Updating .ini file...")

    config.set('stats', 'conversions', str(int(config.get('stats', 'conversions')) + 1))
    with open('config.ini', 'w') as config_file:
        config.write(config_file)
        config_file.close()

def reply_to_submission(submission, gif_json):
    print("Replying...")

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

def upload_to_gfycat(submission):
    media_url = submission.media['reddit_video']['fallback_url']

    try:
        gif_json = gfycat.query_gfy(gfycat.upload_from_url(media_url)['gfyname'])
    except GfycatClientError:
        print("Upload error, sending back to cache.")
        return 'retry'

    if not verify_matching_urls(gif_json, media_url):
        #print("Error! Gfycat's URL doesn't match the submission URL.")
        return 'remove'

    update_conversions_ini()
    reply_to_submission(submission, gif_json)
    return 'remove'

t1 = threading.Thread(target=cached_links_handler)
t1.start()

for submission in reddit.subreddit('all').stream.submissions():
    try:
        if submission.domain == 'v.redd.it' and submission.media['reddit_video']['is_gif']:
            print("Match found: " + submission.url)
            cached_submissions.append(submission)
    except TypeError:
        print("This submission is NoneType. Dodging...")
        continue
