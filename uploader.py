import os
from models import User, Video, Audio, db
from credentials import CHANNEL_ID
from io import BytesIO
import requests
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def upload_to_telegram(app, file_path, file_type, youtube_id, chat_id, resolution="", caption="", downloading_id=None, thumbnail_file_path=None):
    if file_type=='video':
        caption+='\n\n@BreakTubebot'
        if thumbnail_file_path:
            thumbnail_response = requests.get(thumbnail_file_path).content
            video=await app.send_video(chat_id=CHANNEL_ID, video=file_path, caption=caption, thumb=BytesIO(thumbnail_response))
        else:
            video=await app.send_video(chat_id=CHANNEL_ID, video=file_path, caption=caption, thumb='splash.jpg')

        Video.create(id=video.id, youtube_id=youtube_id, resolution=resolution)
        send=await app.forward_messages(chat_id=chat_id, from_chat_id=CHANNEL_ID, message_ids=video.id)

        if send:
            os.remove(file_path)
            if downloading_id:
                await app.delete_messages(chat_id, downloading_id)
        return True
    else:
        new_file_path = os.path.splitext(file_path)[0] + ".mp3"
        os.rename(file_path, new_file_path)
           
        audio=await app.send_audio(chat_id=CHANNEL_ID, audio=new_file_path, caption=caption)

        Audio.create(id=audio.id, youtube_id=youtube_id)
        send=await app.forward_messages(chat_id=chat_id, from_chat_id=CHANNEL_ID, message_ids=audio.id, disable_notification=True)
        if send:
            os.remove(new_file_path)
            if downloading_id:
                await app.delete_messages(chat_id, bot_last_message.message_id)
        return True
