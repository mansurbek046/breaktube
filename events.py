from models import User, Video, Audio, db
import json
from serializer import YtVideoSubtitles, YtChannel, YtChannelPlaylists
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from emoji_dict import flags_emoji_dict
import pickle
from io import BytesIO
import datetime
from pytube import YouTube, Playlist
import sender
import uploader
import subprocess
import asyncio
import os
from telegraph import Telegraph
from urllib.parse import urlparse, parse_qs
from dateutil.relativedelta import relativedelta
from credentials import CHANNEL_ID, telegraph_access_token
from concurrent.futures import ThreadPoolExecutor

telegraph=Telegraph(telegraph_access_token)

languages = ''
with open('languages.json') as lang:
    languages = json.load(lang)

def on_complete(stream, file_path):
    return file_path

def download_video(video_url, callback_data, stream_resolution, stream_type, user_language, telegraph, app, chat_id, downloading):
    yt=YouTube(video_url+callback_data[1], on_complete_callback=on_complete)
    stream=yt.streams.filter(res=stream_resolution, file_extension=stream_type).first()
    file_path=stream.download('Videos/')

    caption = user_language['caption_video'].format(
        yt.title,
        video_url+callback_data[1],
        datetime.timedelta(seconds=yt.length),
        f'{yt.views:,}',
        str(yt.publish_date).split(' ')[0].replace('-', '.'),
        yt.channel_id,
        yt.author)
    if yt.description:
        description=str(yt.description).replace('\n', '<br>')
        try:
            page = telegraph.create_page(yt.title, html_content=f'{description}')
            caption = caption.replace('DESC', f'\n📖 [{user_language["description"]}]({page["url"]})')
        except Exception as e:
            caption=caption.replace('DESC', description)
            print(f"An error occurred while creating to Telegraph page: {e}")
    else:
        caption=caption.replace('DESC','')

    if stream.type == "progressive":
        return [file_path, yt.thumbnail_url, caption]
    else:
        audio_stream=yt.streams.filter(only_audio=True).first()
        audio_file_path=audio_stream.download('Audios/')
        new_audio_file_path = os.path.splitext(audio_file_path)[0] + ".mp3"
        os.rename(audio_file_path, new_audio_file_path)

        splitted_file_name=file_path.split("Videos/")[-1]
        merged_file_path="Merged/"+splitted_file_name

        if splitted_file_name.split('.')[-1]=="webm":
            merged_file_path=merged_file_path.split('.')[0]+".mkv"
            ffmpeg_cmd = ["ffmpeg",
                          "-i", file_path,
                          "-i", new_audio_file_path,
                          "-c:v", "copy",
                          "-c:a", "aac",
                          merged_file_path]
            # subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        else:
            ffmpeg_cmd = ["ffmpeg", "-i", file_path, "-i", new_audio_file_path, "-c", "copy", merged_file_path]
            # subprocess.run(ffmpeg_cmd)
            subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return [merged_file_path, yt.thumbnail_url, caption]


async def download_video_async(video_url, callback_data, stream_resolution, stream_type, user_language, telegraph, app, chat_id, downloading):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        file_path, thumbnail_url, caption=await loop.run_in_executor(executor, download_video, video_url, callback_data, stream_resolution, stream_type, user_language, telegraph, app, chat_id, downloading)
        upload=await uploader.upload_to_telegram(
            app, 
            file_path, 
            'video', 
            callback_data[1], 
            chat_id, 
            stream_resolution, 
            caption,
            downloading.id,
            thumbnail_file_path=thumbnail_url)
        if upload:
            os.remove(file_path)
            os.remove(new_audio_file_path)
        


def download_playlist_video(video, user_language, callback_query, app, CHANNEL_ID, uploader):
    stream = video.streams.get_by_resolution('720p')
    if stream:
        file_path = stream.download('Videos/')
        caption = user_language['caption_video'].format(
            video.title,
            video.watch_url,
            datetime.timedelta(seconds=video.length),
            f"{video.views:,}",
            str(video.publish_date).split(' ')[0].replace('-', '.'),
            video.channel_id,
            video.author
        )

        if video.description:
            description=str(video.description).replace('\n', '<br>')
            try:
                page = telegraph.create_page(video.title, html_content=f'{description}')
                caption = caption.replace('DESC', f'\n📖 [{user_language["description"]}]({page["url"]})')
            except Exception as e:
                caption=caption.replace('DESC', description)
                print(f"An error occurred while creating Telegraph page of playlist video description: {e}")
        else:
            caption=caption.replace('DESC','')

        return [file_path, caption]

            
async def download_playlist_video_async(video, user_language, callback_query, app, CHANNEL_ID, uploader, chat_id):
    matching_records = Video.select().where((Video.youtube_id == video.video_id) & (Video.resolution == "720p"))
    if matching_records.exists():
        await app.forward_messages(chat_id=callback_query.message.chat.id, from_chat_id=CHANNEL_ID, message_ids=int(str(matching_records.first().id)))
    else:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            file_path, caption=await loop.run_in_executor(executor, download_playlist_video, video, user_language, callback_query, app, CHANNEL_ID, uploader)
            await uploader.upload_to_telegram(
                app,
                file_path,
                'video',
                video.video_id,
                chat_id,
                '720p',
                caption
            )


def download_playlist_audio(video, app, chat_id, CHANNEL_ID, on_complete, callback_query, uploader):
    audio_download_url = f'https://www.youtube.com/watch?v={video.video_id}'
    yt = YouTube(audio_download_url, on_complete_callback=on_complete)
    stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()
    file_path = stream.download('Audios/')
    return file_path

async def download_playlist_audio_async(video, app, chat_id, CHANNEL_ID, on_complete, callback_query, uploader):
    video_id = video.video_id
    if video_id:
        audio_results = Audio.select().where(Audio.youtube_id == video_id)
        if audio_results.exists():
            audio = audio_results.first()
            await app.forward_messages(chat_id=chat_id, from_chat_id=CHANNEL_ID, message_ids=int(str(audio)))
        else:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                file_path=await loop.run_in_executor(executor, download_playlist_audio, video, app, chat_id, CHANNEL_ID, on_complete, callback_query, uploader)
                await uploader.upload_to_telegram(app, file_path, 'audio', video_id, callback_query.message.chat.id)

x_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌', callback_data='x:')]])

async def event_controller(client, callback_query, app):    

    video_url = 'https://www.youtube.com/watch?v='
    
    callback_data = callback_query.data.split(':')
    
    from_user = callback_query.from_user
    user = User.get(id=from_user.id)
    user_language=languages[user.lang]
    match callback_data[0]:
        case 'lang':
            user.lang = callback_data[1]
            user.save()

            await app.delete_messages(callback_query.message.chat.id, callback_query.message.id)
            await client.answer_callback_query(callback_query.id, languages[callback_data[1]]['lang_changed'])

        case 'subtitles':
            try:
                subtitles=await YtVideoSubtitles(callback_data[1], user.lang)
                if subtitles:
                    buttons=[]
                    row=[]
                    for subtitle in subtitles:
                        text=f'{flags_emoji_dict.get(subtitle["language_code"], "")} {subtitle["language"]}'
                        button=InlineKeyboardButton(text, callback_data=f'sbt:{subtitle["video_id"]}:{subtitle["language_code"]}')
                        if len(row)<=3:
                            row.append(button)
                        if len(row)==3:
                            buttons.append(row)
                            row=[]
                            row.append(button)
                    if len(subtitles)%3!=0:
                        buttons.append(row)
                        row=[]
                        row.append(button)
                    
                    back=[InlineKeyboardButton('🔙', callback_data=f'back_to_video_buttons:')]
                    buttons.append(back)
                    reply_markup=InlineKeyboardMarkup(buttons)
                    await client.edit_message_reply_markup(
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.id,
                        reply_markup=reply_markup
                    )
                else:
                    await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['empty_subtitle'], reply_markup=x_markup)
            
            except Exception as e:
                print(f"An error occurred while fetching subtitles: {e}")
                await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['err_subtitles'], reply_markup=x_markup)

        # subtitle
        case 'sbt':
            try:
                subtitle = await YtVideoSubtitles(callback_data[1], user.lang, download=callback_data[2])
                file_stream = BytesIO()
                file_stream.write(str(subtitle).encode())
                file_stream.seek(0)
                caption=user_language['subtitle_of'].format(video_url+callback_data[1])
                now=datetime.datetime.now()
                file_name=now.strftime("%Y%m%d%H%M%S")
                await app.send_document(chat_id=callback_query.message.chat.id, document=file_stream, file_name=f"{file_name}.srt", caption=caption, reply_markup=x_markup)

            except Exception as e:
                print(f"An error occurred while fetching a subtitle: {e}")
                await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['err_subtitle'].format(video_url+callback_data[1]), reply_markup=x_markup)
            
        case 'back_to_video_buttons':
            chat_id=callback_query.message.chat.id
            with open(f'Keyboards/{chat_id}_back_keyboard.pkl', 'rb') as file:
                reply_markup=pickle.load(file)
            await client.edit_message_reply_markup(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.id,
                reply_markup=reply_markup
            )
        
        case 'mp3':
            try:
                if Audio.select().where(Audio.youtube_id == callback_data[1]).exists():
                    audio = Audio.select().where(Audio.youtube_id == callback_data[1]).first()
                    await app.forward_messages(chat_id=callback_query.message.chat.id, from_chat_id=CHANNEL_ID, message_ids=int(str(audio)), disable_notification=True, reply_markup=x_markup)
                else:
                    yt=YouTube(video_url+callback_data[1], on_complete_callback=on_complete)
                    stream=yt.streams.filter(only_audio=True, file_extension='mp4').first()
                    file_path=stream.download('Audios/')
                    await uploader.upload_to_telegram(app, file_path, 'audio', callback_data[1], callback_query.message.chat.id)
            except Exception as e:
                print(f"An error occurred while downloading MP3: {e}")
                await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['err_mp3'], reply_markup=x_markup)
                
        case 'channel':
            channel_info=await YtChannel(callback_data[1], user.lang)
            await sender.send_channel_info(client, callback_query.message.chat.id, channel_info, user)

        case 'video':
            error_video_url=''
            downloading=''
            try:
                chat_id=callback_query.message.chat.id
                stream_type=callback_data[2]
                stream_resolution=callback_data[3]
                huge=callback_data[4]
                if huge=="true":
                    await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['huge'], reply_markup=x_markup)
                    return None
                user = User.get(id=callback_query.from_user.id)
                if int(stream_resolution.split('p')[0])<1080 or user.premium:
                    matching_records = Video.select().where((Video.youtube_id == callback_data[1]) & (Video.resolution == stream_resolution))
                    chat_id=callback_query.message.chat.id

                    if matching_records.exists():
                        await app.forward_messages(chat_id=callback_query.message.chat.id, from_chat_id=CHANNEL_ID, message_ids=int(str(matching_records.first().id)), reply_markup=x_markup)
                        await callback_query.message.delete()
                        os.remove(f'Keyboards/{chat_id}_back_keyboard.pkl')
                        
                    else:
                        await callback_query.message.delete()
                        os.remove(f'Keyboards/{chat_id}_back_keyboard.pkl')
                        error_video_url=video_url+callback_data[1]
                        downloading=await client.send_message(chat_id=chat_id, text=user_language['downloading'])

                        await download_video_async(video_url, callback_data, stream_resolution, stream_type, user_language, telegraph, app, chat_id, downloading)

                else:
                    await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['vd_buy_premium'].format(stream_resolution), reply_markup=x_markup)
                    return None

            except Exception as e:
                print(f"An error occurred while downloading video: {e}")
                await app.delete_messages(callback_query.message.chat.id, downloading.id)
                await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['err_video'].format(error_video_url), reply_markup=x_markup)

        case 'subscribe':
            subscibed=user.add_channel(callback_data[1])
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(user_language["view_playlists"], callback_data=f'playlists:{callback_data[1]}'),
                InlineKeyboardButton(user_language["unsubscribe"], callback_data=f'unsubscribe:{callback_data[1]}')
            ], [InlineKeyboardButton('❌', callback_data='x:')]])
            if subscibed:
                await client.answer_callback_query(callback_query.id, user_language['sub_added'])
                await client.edit_message_reply_markup(chat_id=callback_query.message.chat.id, message_id=callback_query.message.id, reply_markup=reply_markup)

        case 'unsubscribe':
            unsubscribed=user.remove_channel(callback_data[1])
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(user_language['view_playlists'], callback_data=f'playlists:{callback_data[1]}'),
                InlineKeyboardButton(user_language['subscribe'], callback_data=f'subscribe:{callback_data[1]}')
            ], [InlineKeyboardButton('❌', callback_data='x:')]])
            if unsubscribed:
                await client.answer_callback_query(callback_query.id, user_language['unsubscribed'])
                await client.edit_message_reply_markup(chat_id=callback_query.message.chat.id, message_id=callback_query.message.id, reply_markup=reply_markup)

        case 'playlists':
            # Fetching playlist
            try:
                playlists=await YtChannelPlaylists(callback_data[1], user.lang)
                playlist_url='https://youtube.com/playlist?list='
                message=f''
                for playlist in playlists:
                    text=user_language['caption_playlists'].format(
                        playlist['name'],
                        playlist_url+playlist['id'],
                        playlist['created_at'].replace('-','.'),
                        playlist['video_count'])
                    if playlist['description']:
                        text=text.replace('DESC', f'\n📖 {playlist["description"]}')
                    else:
                        text=text.replace('DESC', '')
                    message+=text

                await client.send_message(chat_id=callback_query.message.chat.id, text=message, reply_markup=x_markup)

            except Exception as e:
                print(f"An error occurred while fetching playlists: {e}")
                await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['err_playlists'], reply_markup=x_markup)

        case 'playlist':
            # Downloading playlist
            try:
                playlist_url='https://youtube.com/playlist?list='
                playlist = Playlist(playlist_url+callback_data[2])
                chat_id=callback_query.message.chat.id
                if user.premium is None:
                    await client.send_message(chat_id=chat_id, text=user_language['pl_buy_premium'], reply_markup=x_markup)
                    return None
                await callback_query.message.delete()
                downloading=await client.send_message(chat_id=chat_id, text=user_language['pl_downloading'])

                if callback_data[1] == "mp4":
                    for video in playlist.videos:
                        await download_playlist_video_async(video, user_language, callback_query, app, CHANNEL_ID, uploader, chat_id)

                elif callback_data[1] == "mp3":
                    for video in playlist.videos:
                        await download_playlist_audio_async(video, app, chat_id, CHANNEL_ID, on_complete, callback_query, uploader)

                await app.delete_messages(chat_id, downloading.id)
                await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['completed'], reply_markup=x_markup)
    
            except Exception as e:
                print(f"An error occurred while downloading playlist: {e}")
                await app.delete_messages(chat_id, downloading.id)
                await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['err_playlist_download'], reply_markup=x_markup)

        case 'buy':
            try:
                buy=callback_data[1]
                if buy=='cash':
                    pass
                elif buy=='ton':
                    pass
                else:
                    proposals=user.deep_proposals
                    availabel_days=proposals//5
                    buttons=[[],[], [InlineKeyboardButton('❌', callback_data='x:')]]
                    if availabel_days>=1:
                        buttons[0].append(InlineKeyboardButton(user_language['get_day_premium'].format(1), callback_data='day_premium:1'))
                    elif availabel_days>=3:
                        buttons[0].append(InlineKeyboardButton(user_language['get_day_premium'].format(3), callback_data='day_premium:3'))
                    elif availabel_days>=7:
                        buttons[1].append(InlineKeyboardButton(user_language['get_day_premium'].format(7), callback_data='day_premium:7'))
                    elif availabel_days>=30:
                        buttons[1].append(InlineKeyboardButton(user_language['get_day_premium'].format(30), callback_data='day_premium:30'))
                    else:
                        await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['pay_proposal'].format(
                            user.id,
                            proposals,
                            availabel_days,
                            ''
                        ), disable_web_page_preview=True, reply_markup=x_markup)
                        return None
                    
                    reply_markup=InlineKeyboardMarkup(buttons)
                    await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['pay_proposal'].format(
                        user.id,
                        proposals,
                        availabel_days,
                        user_language['get_premium']
                    ), reply_markup=reply_markup, disable_web_page_preview=True)

            except Exception as e:
                print(f"An error occurred in buy command: {e}")

        case 'day_premium':
            try:
                day=int(callback_data[1])
                proposals=user.deep_proposals
                now=datetime.datetime.now()
                await callback_query.message.delete()
                match day:
                    case 1:
                        premium=now + relativedelta(days=0)
                        user.premium=premium.strftime('%Y-%m-%d')
                        user.deep_proposals=proposals-5
                        user.save()
                        await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['premium_taken'].format(1), reply_markup=x_markup)
                    case 3:
                        premium=now + relativedelta(days=3)
                        user.premium=premium.strftime('%Y-%m-%d')
                        user.deep_proposals=proposals-15
                        user.save()
                        await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['premium_taken'].format(3), reply_markup=x_markup)
                    case 7:
                        premium=now + relativedelta(days=7)
                        user.premium=premium.strftime('%Y-%m-%d')                        
                        user.deep_proposals=proposals-35
                        user.save()
                        await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['premium_taken'].format(7), reply_markup=x_markup)
                    case 30:
                        premium=now + relativedelta(months=1)
                        user.premium=premium.strftime('%Y-%m-%d')                        
                        user.deep_proposals=proposals-150
                        user.save()
                        await client.send_message(chat_id=callback_query.message.chat.id, text=user_language['premium_taken'].format(30), reply_markup=x_markup)

            except Exception as e:
                print(f"An error occurred in day_premium command: {e}")
        case 'x':
            await callback_query.message.delete()
