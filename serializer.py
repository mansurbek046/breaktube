import asyncio
from googleapiclient.discovery import build
import json
from extid import get_id
from youtube_transcript_api import YouTubeTranscriptApi
import re
from youtube_transcript_api.formatters import SRTFormatter
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import time
import pytz
from models import User, db
from credentials import API_KEY
import logging

x_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌', callback_data='x:')]])

languages = ''
with open('languages.json') as lang:
    languages = json.load(lang)

def error_handler(client, message):
    logging.error("Error: %s", message)

async def YtVideo(client, id, lang):
    try:
        youtube = build('youtube', 'v3', developerKey=API_KEY())
        req = youtube.videos().list(part='snippet,statistics', id=id)
        res = req.execute()
        video_info = res['items'][0]['snippet']
        like_count = res['items'][0]['statistics']['likeCount']
        msg_content = {
            'photo': video_info['thumbnails']['default']['url'],
            'name': video_info['title'],
            'description': video_info['description'],
            'created_at': video_info['publishedAt'].split('T')[0].replace('-','.'),
            'channel_id': video_info['channelId'],
            'channel_name': video_info['channelTitle'],
            'like_count': like_count,
            'id': id
        }
        return msg_content
    except Exception as e:
        error_handler(client, f"An error occurred while fetching YouTube video details: {e}")
        return None

async def YtVideoSubtitles(client, id, lang, download=False):
    try:
        youtube = build('youtube', 'v3', developerKey=API_KEY())
        if not download:
            transcript_list = YouTubeTranscriptApi.list_transcripts(id)

            subtitles=[]
            for item in transcript_list:
                subtitle={}
                language=item.language
                subtitle['language']=language.replace('(auto-generated)','(auto)'),
                subtitle['language_code']=item.language_code
                subtitle['video_id']=item.video_id
                subtitles.append(subtitle)
            return subtitles
        else:
            formatter=SRTFormatter()
            subtitle=YouTubeTranscriptApi.get_transcript(id, languages=[download])
            return formatter.format_transcript(subtitle)
            
    except Exception as e:
        error_handler(client, f"An error occurred while fetching YouTube video subtitles: {e}")
        return None

async def YtChannel(client, id, lang, is_name=False):
    try:
        youtube = build('youtube', 'v3', developerKey=API_KEY())
        if is_name:
            id = get_id(id)
        if id:
            req = youtube.channels().list(part='snippet,statistics', id=id)
            res = req.execute()
            if int(res['pageInfo']['totalResults']) > 0:
                channel_info = res['items'][0]['snippet']
                subscriber_count=res['items'][0]['statistics']['subscriberCount']
                video_count=res['items'][0]['statistics']['videoCount']
                view_count=res['items'][0]['statistics']['viewCount']
                msg_content = {
                    'photo': channel_info['thumbnails']['high']['url'],
                    'name': channel_info['title'],
                    'description': channel_info['description'],
                    'subscriber_count': subscriber_count,
                    'video_count': video_count,
                    'view_count': view_count,
                    'created_at': channel_info['publishedAt'].split('T')[0],
                    'id': id
                }
                return msg_content
            else:
                return languages[lang]['invalid_channel']
        else:
            return languages[lang]['invalid_channel']
    except Exception as e:
        error_handler(client, f"An error occurred while fetching YouTube channel details: {e}")
        return None


async def YtChannels(ids, client, chat_id, user):
    youtube = build('youtube', 'v3', developerKey=API_KEY())
    user_language=languages[user.lang]
    if ids:
        req = youtube.channels().list(
            part="snippet",
            id=",".join(ids),
            fields='items(id,snippet(title))'
        )
        res = req.execute()
        buttons=[]

        for data in res["items"]:
            channel=data['snippet']
            buttons.append([InlineKeyboardButton(channel['title'], callback_data=f'channel:{data["id"]}')])

        buttons.append([InlineKeyboardButton('❌', callback_data='x:')])

        reply_markup=InlineKeyboardMarkup(buttons)
        await client.send_message(chat_id=chat_id, text=user_language['subscribed_channels'], reply_markup=reply_markup)
    else:
        await client.send_message(chat_id=chat_id, text=user_language['empty_subscription'], reply_markup=x_markup)

async def YtPlaylist(client, id, lang):
    try:
        youtube = build('youtube', 'v3', developerKey=API_KEY())
        req = youtube.playlists().list(part='snippet,contentDetails', id=id)
        res = req.execute()

        playlist_info = res['items'][0]['snippet']
        video_count = res['items'][0]['contentDetails']['itemCount']
        msg_content = {
            'photo': playlist_info['thumbnails']['default']['url'],
            'name': playlist_info['title'],
            'description': playlist_info['description'],
            'created_at': playlist_info['publishedAt'].split('T')[0],
            'channel_id': playlist_info['channelId'],
            'channel_name': playlist_info['channelTitle'],
            'video_count': video_count,
            'id': id
        }
        if not msg_content['photo'].endswith('.jpg'):
            msg_content['photo']='splash.jpg'
        return msg_content
    except Exception as e:
        error_handler(client, f"An error occurred while fetching YouTube playlist details: {e}")
        return None

async def YtChannelPlaylists(client, channel_id, lang):
    try:
        youtube = build('youtube', 'v3', developerKey=API_KEY())
        req=youtube.playlists().list(part='snippet,contentDetails', channelId=channel_id)
        res=req.execute()
        msg_content=[]
        for playlist in res['items']:
            playlist_id=playlist['id']
            video_count = playlist['contentDetails']['itemCount']
            playlist=playlist['snippet']
            playlist_info={
                'photo': playlist['thumbnails']['default']['url'],
                'name': playlist['title'],
                'description': playlist['description'],
                'created_at': playlist['publishedAt'].split('T')[0],
                'video_count': video_count,
                'id': playlist_id
            }
            
            msg_content.append(playlist_info)
        
        return msg_content

    except Exception as e:
        error_handler(client, f"An error occurred while fetching playlists of Channel: {e}")
        return None


async def YtChannelVideos(client, id, lang):
    try:
        youtube = build('youtube', 'v3', developerKey=API_KEY())
        videos = []
        next_page_token = None
        
        while True:
            request = youtube.search().list(
                part='snippet',
                channelId=id,
                maxResults=50,
                fields='items(id/videoId,snippet(title,publishedAt,thumbnails(default(url))))',
                pageToken=next_page_token
            )
            response = request.execute()
        
            videos.extend(response['items'])
        
            next_page_token = response.get('nextPageToken')
        
            if not next_page_token:
                break
        return videos

    except Exception as e:
        error_handler(client, f"An error occurred while fetching YouTube channel videos: {e}")
        return None



def compare_dates(last, video):
    last_date=str(last).replace("T"," ").replace("Z","")
    video_date=str(video).replace("T"," ").replace("Z","")
    print(f'COMPARE DATES: {last_date} .. {video_date}')
    return last_date <= video_date

async def YtUpdate(client, id, chat_id):
    while True:
        user = User.select().where(User.id == id).first()
        # print('While is working...')
        user_language=languages[user.lang]
        if user.get_channels():
            # print('User has channels...')
            for channel_id in user.get_channels():
                # print(f'One channel taken...{channel_id}')
                youtube = build('youtube', 'v3', developerKey=API_KEY())
                req = youtube.search().list(
                    part="snippet",
                    channelId=channel_id,
                    order="date",
                    type="video",
                    maxResults=4
                )
                res = req.execute()
                # print(res)
                for video_info in res['items']:
                    video_id = video_info['id']['videoId']
                    video_info = video_info['snippet']

                    # print(user.updated_at, video_info['publishedAt'])
                    if compare_dates(user.updated_at, video_info['publishedAt']):
                        # print("NEW VIDEO")
                        video_url = f'https://www.youtube.com/watch?v='
                        caption = user_language['new_video_caption'].format(
                            video_info['title'],
                            video_url + video_id,
                            video_info['channelId'],
                            video_info['channelTitle']
                        )
                        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(user_language['view_video'], callback_data=f"view:{video_id}")]])
                        await client.send_photo(photo=video_info['thumbnails']['high']['url'], caption=caption, chat_id=chat_id, reply_markup=reply_markup)
        if user.premium:
            end_date=str(user.premium).split(' ')[0]
            now=str(datetime.now().strftime('%Y-%m-%d'))
            if end_date==now:
                user.premium=None
                user.save()
                await client.send_message(chat_id=chat_id, text=languages[user.lang]['premium_finished'])

        user.updated_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        user.save()
        await asyncio.sleep(60*60)
    return None
