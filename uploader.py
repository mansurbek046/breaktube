import os
from models import User, Video, Audio, db
from credentials import CHANNEL_ID
from io import BytesIO
import requests
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def upload_to_telegram(app, file_path, file_type, youtube_id, chat_id, resolution="", caption="", downloading_id=None, thumbnail_file_path=None, duration=0):
    try:
        reply_markup=InlineKeyboardMarkup([InlineKeyboardButton('🔍', switch_inline_query_current_chat=video_name)])

        if file_type=='video':
            caption+='\n\n🤡 @BreakTubebot\n…………………………………………'
            video_name=str(file_path.split('.')[0]).replace('_',' ')
            if thumbnail_file_path:
                thumbnail_response = requests.get(thumbnail_file_path).content
                if str(file_path.split('.')[-1]).lower()=="mkv":
                    video=await app.send_document(chat_id=CHANNEL_ID, document=file_path, caption=caption, thumb=BytesIO(thumbnail_response))
                else:
                    video=await app.send_video(chat_id=CHANNEL_ID, video=file_path, caption=caption, thumb=BytesIO(thumbnail_response), duration=duration)
            else:
                if str(file_path.split('.')[-1]).lower()=="mkv":
                    video=await app.send_document(chat_id=CHANNEL_ID, document=file_path, caption=caption, thumb=BytesIO(thumbnail_response))
                else:
                    video=await app.send_video(chat_id=CHANNEL_ID, video=file_path, caption=caption, thumb='splash.jpg', duration=duration)

            if str(file_path.split('.')[-1]).lower()=="mkv":
                Video.create(id=video.id, youtube_id=youtube_id, resolution=resolution, video_type="mkv")
            else:
                Video.create(id=video.id, youtube_id=youtube_id, resolution=resolution, video_type="mp4")
            send=await app.copy_message(chat_id, CHANNEL_ID, video.id)
            if send:
                os.remove(file_path)
                if downloading_id:
                    await app.delete_messages(chat_id, downloading_id)
            return True
        else:
            new_file_path = os.path.splitext(file_path)[0] + ".mp3"
            os.rename(file_path, new_file_path)
               
            audio=await app.send_audio(chat_id=CHANNEL_ID, audio=new_file_path, caption=caption, duration=duration, reply_markup=reply_markup)

            Audio.create(id=audio.id, youtube_id=youtube_id)
            send=await app.forward_messages(chat_id=chat_id, from_chat_id=CHANNEL_ID, message_ids=audio.id)
            if send:
                os.remove(new_file_path)
                if downloading_id:
                    await app.delete_messages(chat_id, bot_last_message.message_id)
            return True
    except Exception as e:
        error_handler(client, f"An error occured while uploading to telegram: {e}")

    
