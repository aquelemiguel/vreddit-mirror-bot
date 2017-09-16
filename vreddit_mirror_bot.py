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

config = configparser.ConfigParser()
config.read('config.ini') # File isn't available on GitHub, for obvious reasons.

username = config.get('reddit', 'username')
password = config.get('reddit', 'password')

reddit = praw.Reddit(
    client_id=config.get('reddit', 'client_id'),
    client_secret=config.get('reddit', 'client_secret'),
    username=username,
    password=password,
    user_agent='vredditmirrorbot by /u/blinkroot'
)
gfycat = GfycatClient()

ini_semaphore = threading.Semaphore() # For .ini file synchronization.
log_semaphore = threading.Semaphore() # For .log file synchronization.

# Increments 'conversions' stat in .ini file.
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
    s = '&#32;'

    if is_gif:
        try:
            webm_size = str(round(int(gfy_field('webmSize'))/1000000, 2))
            mp4_size = str(round(int(gfy_field('mp4Size'))/1000000, 2))
            webm_url = gfy_field('webmUrl')
            mp4_url = gfy_field('mp4Url')
            num_of_conversions = config.get('stats', 'conversions')
        except KeyError:
            print("Key error...")
            log_url(submission.url, 3)
            return

        reply = f"""This post's using **v.redd.it**, Reddit's native video player.{s}{s}\x20\x20
If your device isn't supported or the quality's subpar, try these mirrors hosted over at **Gfycat!**  \n
* [**WEBM** ({webm_size} MB, Android)]({webm_url})\n* [**MP4** ({mp4_size} MB, iOS)]({mp4_url})  \n\n***
^^I'm{s}a{s}beep-boop.{s}**{num_of_conversions}**{s}mirrors{s}so{s}far!{s}|{s}[source](https://github.com/aquelemiguel){s}|{s}[faq](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/FAQ){s}|{s}[feedback](https://www.reddit.com/message/compose?to=blinkroot){s}|{s}[banned{s}subs](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Banned-subreddits){s}|{s}[support{s}me{s}♥️](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Donations)
"""
    if not is_gif:
        try:
            #mp4_size = str(round(os.stat("cached/" + gif_json['title']).st_size /1000000, 2))
            mp4_size = str(round(int(strmbl_field('mp4', 'size'))/1000000, 2))
            mp4_url = "https://" + gif_json['url']
            num_of_conversions = config.get('stats', 'conversions')
        except KeyError:
            print("Key error...")
            log_url(submission.url, 3)

        reply = f"""This post's using **v.redd.it**, Reddit's native video player.\x20\x20
If your device isn't supported or the quality's subpar, try this mirror hosted over at **Streamable!**  \n
* [**MP4** ({mp4_size} MB)]({mp4_url})  \n\n***
^^I'm{s}a{s}beep-boop.{s}**{num_of_conversions}**{s}mirrors{s}so{s}far!{s}|{s}[source](https://github.com/aquelemiguel){s}|{s}[faq](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/FAQ){s}|{s}[feedback](https://www.reddit.com/message/compose?to=blinkroot){s}|{s}[banned{s}subs](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Banned-subreddits){s}|{s}[support{s}me{s}♥️](https://github.com/aquelemiguel/vreddit-mirror-bot/wiki/Donations)
"""

    while True:
        try:
            submission.reply(reply)
            print("Upload complete!\n")
            log_url(submission.url, 4)
            break
        except praw.exceptions.APIException as e: # Hit Reddit's submission limit.
            print("Hit rate limit: " + e.message)
            time.sleep(30)
        except prawcore.exceptions.Forbidden as e: # Probably got banned while converting the video.
            print("Wasn't able to comment on: " + submission.url)
            break
    return

def upload_to_streamable(submission):
    media_url = submission.media['reddit_video']['fallback_url']

    while True:
        mp4_path = "cached/" + submission.id + ".mp4"
        mp3_path = "cached/" + submission.id + ".mp3"
        output_path = "cached/OUT" + submission.id + ".mp4"

        try:
            urllib.request.urlretrieve(media_url, mp4_path)
            urllib.request.urlretrieve(media_url[:media_url.find('/', 18)] + "/audio", mp3_path)
        except urllib.error.HTTPError: # A 'muted sound' video.
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

    ini_semaphore.acquire()
    update_conversions_ini()
    ini_semaphore.release()

    reply_to_submission(submission, gif_json, False)

    try:
        os.remove(mp4_path)
        os.remove(mp3_path)
        #os.remove(output_path)
    except FileNotFoundError: # If this gets caught, I deleted the file.
        pass

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
            log_url(submission.url, 2)
        except KeyError:
            print("Key error!")
            log_url(submission.url, 3)

    ini_semaphore.acquire()
    update_conversions_ini()
    ini_semaphore.release()

    reply_to_submission(submission, gif_json, True)

    try:
        os.remove("cached/" + submission.id + ".mp4")
    except FileNotFoundError: # If this gets caught, I deleted the file.
        pass

    return

def log_url(url, status):
    log_semaphore.acquire()

    with open("log.txt", "a") as log_file:

        if status == 1: # Found status.
            log_file.write("Found: " + url + "\n")
        elif status == 2: # Upload error.
            log_file.write("Upload error: " + url + "\n")
        elif status == 3: # Key error.
            log_file.write("Key error: " + url + "\n")
        elif status == 4: # Success status.
            log_file.write("Success: " + url + "\n")

    log_semaphore.release()


while True:
    try:
        for submission in reddit.subreddit('all').stream.submissions():
            try:
                # If user is banned from the sub, skip it.
                if submission.subreddit.user_is_banned:
                    continue

                # Handles video submissions.
                elif submission.domain == 'v.redd.it' and not submission.media['reddit_video']['is_gif']:
                    print("Video match found: " + submission.url)
                    log_url(submission.url, 1)
                    thread = threading.Thread(target=upload_to_streamable, args=(submission,))
                    thread.start()

                # Handles .gif submissions.
                elif submission.domain == 'v.redd.it' and submission.media['reddit_video']['is_gif']:
                    print("Gif match found: " + submission.url)
                    log_url(submission.url, 1)
                    thread = threading.Thread(target=upload_to_gfycat, args=(submission,))
                    thread.start()

            except TypeError:
                print("This submission is NoneType. Dodging...")
                continue
            except prawcore.exceptions.NotFound:
                print("Submission not found.")
                continue
    except prawcore.exceptions.ServerError:
        print("Issue on submission stream...")
    except prawcore.exceptions.RequestException:
        print("Reddit might be down...")
    except prawcore.exceptions.Forbidden:
        print("Forbidden!")
