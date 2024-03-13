import time
import json
import math
import pickle
import logging
import asyncio
import datetime
from pytube import YouTube
from itertools import chain
from telegraph import Telegraph
from urllib.error import URLError
from credentials import telegraph_access_token
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from serializer import YtChannelPlaylists
from io import BytesIO
import requests

telegraph=Telegraph(telegraph_access_token)

def error_handler(client, message):
    logging.error("Error: %s", message)

def convert_bytes(byte_num):
    gigabytes = byte_num / (1024 * 1024 * 1024)
    if gigabytes >= 1:
        return f'{gigabytes:.2f}GB'
    megabytes = byte_num / (1024 * 1024)
    if megabytes >= 1:
        return f'{megabytes:.2f}MB'
    kilobytes = byte_num / 1024
    return f'{kilobytes:.2f}KB'

languages = ''
with open('languages.json') as lang:
    languages = json.load(lang)

x_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌', callback_data='x:')]])

async def send_video_info(client, chat_id, id, user):
    try:
        user_language=languages[user.lang]
        video_url = f'https://www.youtube.com/watch?v={id}'
        yt = None
        loop = asyncio.get_event_loop()
        yt = await loop.run_in_executor(None, lambda: YouTube(video_url))

        if yt:
            video_streams = yt.streams.filter(adaptive=True)
            buttons = []
            mpf_buttons = []
            webm_buttons = []
            unique_video_formats = set()
            
            for stream in video_streams:
                filesize=convert_bytes(stream.filesize)
                video_mark_mpf='📹'
                video_mark_webm='🎞'
                huge='false'
                
                if 'GB' in filesize and math.ceil(float(filesize.split('G')[0]))>2:
                    video_mark_webm=video_mark_mpf='💔'
                    huge='true'
                if (stream.mime_type.startswith('video/mp4') or stream.mime_type.startswith('video/webm')) and (stream.mime_type + stream.resolution) in unique_video_formats:
                    continue
                elif stream.mime_type.startswith('video/mp4'):
                    unique_video_formats.add(stream.mime_type + stream.resolution)
                    mpf_buttons.append(
                        InlineKeyboardButton(f'{video_mark_mpf} {stream.resolution} {filesize}', callback_data=f'video:{id}:mp4:{stream.resolution}:{huge}')
                    )
                elif stream.mime_type.startswith('video/webm'):
                    unique_video_formats.add(stream.mime_type + stream.resolution)
                    webm_buttons.append(
                        InlineKeyboardButton(f'{video_mark_webm} {stream.resolution} {filesize}', callback_data=f'video:{id}:webm:{stream.resolution}:{huge}')
                    )
            chunk_size=2
            if len(mpf_buttons) and len(webm_buttons):
                buttons = [[mpf, webm] for mpf, webm in zip(mpf_buttons, webm_buttons)]
                buttons.insert(0, [InlineKeyboardButton('⬇️ MP4 ', callback_data='disabled'),
                                    InlineKeyboardButton('MKV ⬇️', callback_data='disabled')])
            elif len(mpf_buttons):
                for i in range(0, len(mpf_buttons), chunk_size):
                    chunk = mpf_buttons[i:i + chunk_size]
                    buttons.append(chunk)
            elif len(webm_buttons):
                for i in range(0, len(webm_buttons), chunk_size):
                    chunk = webm_buttons[i:i + chunk_size]
                    buttons.append(chunk)                

            buttons.append([InlineKeyboardButton('🎧 MP3', callback_data=f'mp3:{id}'), 
                            InlineKeyboardButton('🗣', callback_data=f'channel:{yt.channel_id}'), 
                            InlineKeyboardButton('💬', callback_data=f'subtitles:{id}')])
            buttons.append([InlineKeyboardButton('🔍', switch_inline_query_current_chat=yt.title), InlineKeyboardButton('❌', callback_data='x:')])
            

            reply_markup = InlineKeyboardMarkup(buttons)

            # saving keyboards for back functionality
            with open(f'Keyboards/{chat_id}_back_keyboard.pkl', 'wb') as file:
                pickle.dump(reply_markup, file)
            video_description=yt.description.replace("\n","<br>")

            caption = user_language['caption_video'].format(
                yt.title,
                video_url,
                datetime.timedelta(seconds=yt.length),
                f'{yt.views:,}',
                str(yt.publish_date).split(' ')[0].replace('-', '.'),
                yt.channel_id,
                yt.author)

            if video_description:
                try:
                    page = telegraph.create_page(yt.title, html_content=f'{video_description}')
                    caption = caption.replace('DESC', f'\n📖 [{user_language["description"]}]({page["url"]})')
                except Exception as e:
                    caption=caption.replace('DESC', video_description)
                    print(f"An error occurred while creating to Telegraph page: {e}")
            else:
                caption=caption.replace('DESC','')

            msg=await client.send_photo(photo=yt.thumbnail_url, caption=caption, chat_id=chat_id, reply_markup=reply_markup)

            
            
    except Exception as e:
        error_handler(client, f"An error occurred in send_video_info: {e}")
        await client.send_message(chat_id, user_language['err_video_info'], reply_markup=x_markup)


async def send_channel_info(client, chat_id, channel_info, user):
    user_language=languages[user.lang]

    # Fetching playlists
    playlists=await YtChannelPlaylists(client, channel_info['id'], user.lang)
    playlist_url='https://youtube.com/playlist?list='
    message=f''
    for playlist in playlists:

        response = requests.get(playlist['photo'])
        image_bytes = BytesIO(response.content)
        image_path = telegraph.upload(image_bytes)['src']
    
        text=user_language['caption_playlists'].format(
            playlist_url+playlist['id'],
            playlist['name'],
            playlist['created_at'].replace('-','.'),
            playlist['video_count'])
        if playlist['description']:
            text=text.replace('DESC', f'\n📖 {playlist["description"]}')
        else:
            text=text.replace('DESC', '')
        message+=(f'<img src="{image_path}"><br>'+text)
    playlists_page=telegraph.create_page(channel_info['name'], html_content=f'{message}')

    channels=user.get_channels()
    channel_url = f"https://www.youtube.com/channel/{channel_info['id']}"

    try:
        video_count = int(channel_info['video_count'])
        view_count = int(channel_info['view_count'])
        subscriber_count = int(channel_info['subscriber_count'])
        channel_description=channel_info["description"].replace("\n","<br>")
        caption = user_language['caption_channel'].format(
            channel_url,
            channel_info['name'],
            channel_info['created_at'].replace('-','.'),
            f"{video_count:,}",
            f"{view_count:,}",
            f"{subscriber_count:,}"
        )
        if channel_description:
            page=telegraph.create_page(channel_info['name'], html_content=f'{channel_description}')
            caption=caption.replace('DESC', f'\n📖 <a href="{page["url"]}">{user_language["description"]}</a>')
        else:
            caption=caption.replace('DESC', channel_description)
            caption=caption.replace('DESC','')

        buttons=[[]]
        buttons[0].append(InlineKeyboardButton(user_language['view_playlists'], url=playlists_page["url"]))
        if channel_info['id'] not in channels:
            buttons[0].append(InlineKeyboardButton(user_language['subscribe'], callback_data=f'subscribe:{channel_info["id"]}'))
        else:
            buttons[0].append(InlineKeyboardButton(user_language['unsubscribe'], callback_data=f'unsubscribe:{channel_info["id"]}'))

        buttons.append([InlineKeyboardButton('❌', callback_data='x:')])

        reply_markup=InlineKeyboardMarkup(buttons)
        
        await client.send_photo(photo=channel_info['photo'], caption=caption, chat_id=chat_id, reply_markup=reply_markup)

    except Exception as e:
        error_handler(client, f"An error occurred in send_channel_info: {e}")
        await client.send_message(chat_id, user_language['err_channel_info'], reply_markup=x_markup)

async def send_playlist_info(client, chat_id, playlist_info, user):
    user_language=languages[user.lang]
    try:
        playlist_url=f"https://www.youtube.com/playlist?list={playlist_info['id']}"
        channel_url = f"https://www.youtube.com/channel/{playlist_info['channel_id']}"
        playlist_description=playlist_info["description"].replace("\n","<br>")
        caption=user_language['caption_playlist'].format(
            playlist_url,
            playlist_info['name'],
            playlist_info['created_at'].replace('-','.'),
            f"{int(playlist_info['video_count']):,}",
            channel_url,
            playlist_info['channel_name']
        )
        if playlist_description:
            page=telegraph.create_page(playlist_info['name'], html_content=f'{playlist_description}')
            caption=caption.replace('DESC', f'\n📖 <a href="{page["url"]}">{user_language["description"]}</a>')
        else:
            caption=caption.replace('DESC', playlist_description)
            caption=caption.replace('DESC','')

        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📹 720p', callback_data=f'playlist:mp4:{playlist_info["id"]}'),
        InlineKeyboardButton('🎧 MP3', callback_data=f'playlist:mp3:{playlist_info["id"]}')], [InlineKeyboardButton('🔍', switch_inline_query_current_chat=f".p {playlist_info['name']}"), InlineKeyboardButton('❌', callback_data='x:')]])
        print(playlist_info['photo'])
        await client.send_photo(photo=playlist_info['photo'], caption=caption, chat_id=chat_id, reply_markup=reply_markup)

    except Exception as e:
        error_handler(client, f"An error occurred in send_playlist_info: {e}")
        await client.send_message(chat_id, user_language['err_playlist_info'], reply_markup=x_markup)
