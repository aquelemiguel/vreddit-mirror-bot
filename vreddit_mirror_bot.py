import os
import time
import configparser
import sys
import praw
import prawcore
import json
import threading
import requests
import urllib
import ffmpy

from gfycat.client import GfycatClient
from gfycat.error import GfycatClientError

# ConfigParser setup.
config = configparser.ConfigParser()
config.read('config.ini')

username = config.get('reddit', 'username')
password = config.get('reddit', 'password')

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

def reply_to_submission(submission, gif_json, is_gif):

    def gfy_field(prop):
        return gif_json['gfyItem'][prop]

    def strmbl_field(extension, prop):
        return gif_json['files'][extension][prop]

    reply = ""

    if is_gif:
        try:
            webm_size = str(round(int(gfy_field('webmSize'))/1000000, 2))
            mp4_size = str(round(int(gfy_field('mp4Size'))/1000000, 2))
            webm_url = gfy_field('webmUrl')
            mp4_url = gfy_field('mp4Url')
            num_of_conversions = config.get('stats', 'conversions')
        except KeyError:
            print("Key error...")
            return

        reply = f"""This post appears to be using Reddit's native video player.
If your current device does not support v.redd.it, try one of these mirrors hosted over at **Gfycat**!  \n
* [**WEBM** ({webm_size} MB)]({webm_url})  \n\n* [**MP4** ({mp4_size} MB)]({mp4_url})  \n\n***
^(^I'm ^a ^beep-boop. ^**{num_of_conversions}** ^conversions ^so ^far!)
[^^Github ](https://github.com/aquelemiguel)^^|
[^^Banned ^^subs ](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Banned-subreddits)^^|
[^^Support ^^me ^^♥️](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Donations)
"""

    if not is_gif:
        try:
            mp4_size = str(round(int(strmbl_field('mp4', 'size'))/1000000, 2))
            mp4_url = "https://www." + gif_json['url']
            #mobile_size = str(round(int(strmbl_field('mp4-mobile', 'size'))/1000000, 2))
            #mobile_url = strmbl_field('mp4-mobile', 'url')
            num_of_conversions = config.get('stats', 'conversions')
        except KeyError:
            print("Key error...")
            return

        reply = f"""This post appears to be using Reddit's native video player.
If your current device does not support v.redd.it, try this mirror hosted over at **Streamable**!  \n
* [**MP4** ({mp4_size} MB)]({mp4_url})  \n\n***
^(^I'm ^a ^beep-boop. ^**{num_of_conversions}** ^conversions ^so ^far!)
[^^Github ](https://github.com/aquelemiguel)^^|
[^^Banned ^^subs ](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Banned-subreddits)^^|
[^^Support ^^me ^^♥️](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Donations)
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

def upload_to_streamable(submission):
    media_url = submission.media['reddit_video']['fallback_url']

    while True:
        mp4_path = "cached/" + submission.id + ".mp4"
        mp3_path = "cached/" + submission.id + ".mp3"
        output_path = "cached/OUT" + submission.id + ".mp4"

        try:
            urllib.request.urlretrieve(media_url, mp4_path)
            urllib.request.urlretrieve(media_url[:media_url.find('/', 18)] + "/audio", mp3_path)
        except urllib.error.HTTPError: # Probably a 'muted sound' video.
            print("Muted sound video found...")
            thread = threading.Thread(target=upload_to_gfycat, args=(submission,))
            thread.start()
            return

        try:
            ff = ffmpy.FFmpeg(inputs={mp4_path: None, mp3_path: None}, outputs={output_path: None})
            ff.run()
        except ffmpy.FFRuntimeError:
            pass

        files = [('file', open(output_path, 'rb'))]
        os.system('cls') # Clears all the FFMPEG verbose.

        response = requests.post('https://api.streamable.com/upload', files=files, auth=(username, password))
        short_code = json.loads(response.text)['shortcode']

        response = requests.get('https://api.streamable.com/videos/' + short_code)

        print("Uploading file...")
        while not json.loads(requests.get('https://api.streamable.com/videos/' + short_code).text)['status'] == 2:
            time.sleep(1)
            continue

        gif_json = json.loads(requests.get('https://api.streamable.com/videos/' + short_code).text)
        break

    semaphore.acquire()
    update_conversions_ini()
    semaphore.release()

    reply_to_submission(submission, gif_json, False)
    #os.remove(mp4_path)
    #os.remove(mp3_path)
    #os.remove(output_path)

    return

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

    reply_to_submission(submission, gif_json, True)
    os.remove("cached/" + submission.id + ".mp4")

    return

while True:
    try:
        for submission in reddit.subreddit('all').stream.submissions():
            try:
                # Handles video submissions.
                if submission.domain == 'v.redd.it' and not submission.media['reddit_video']['is_gif'] and not submission.subreddit.user_is_banned:
                    print("Video match found: " + submission.url)
                    thread = threading.Thread(target=upload_to_streamable, args=(submission,))
                    thread.start()

                # Handles .gif submissions.
                elif submission.domain == 'v.redd.it' and submission.media['reddit_video']['is_gif'] and not submission.subreddit.user_is_banned:
                    print("Gif match found: " + submission.url)
                    thread = threading.Thread(target=upload_to_gfycat, args=(submission,))
                    thread.start()

            except TypeError:
                print("This submission is NoneType. Dodging...")
                continue
    except prawcore.exceptions.ServerError:
        print("Issue on submission stream...")
