import asyncio
import subprocess
import logging
import os
from googleapiclient.discovery import build
from urllib.parse import urlparse, parse_qs
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from models import User, db
from serializer import YtVideo, YtChannel, YtPlaylist, YtUpdate, YtChannels
import sender
import json
from events import event_controller
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent
from datetime import datetime
from credentials import API_KEY, api_hash, api_id, bot_token
from emoji_dict import flags_emoji_dict

db.connect()
app = Client('BreakTubebot', api_hash=api_hash, api_id=api_id, bot_token=bot_token)

logging.basicConfig(filename='tmp/log.txt', level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def error_handler(client, message):
    logging.error("Error: %s", message)

app.add_handler(error_handler)

languages = ''
with open('languages.json') as lang:
    languages = json.load(lang)

def channel_updates(client, user_id, chat_id):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(YtUpdate(client, user_id, chat_id))

x_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌', callback_data='x:')]])

@app.on_message(filters.command('start'))
async def welcome(client, message):
    from_user = message.from_user
    user = User.select().where(User.id == from_user.id).first()
    language_code = from_user.language_code if from_user.language_code in list(languages.keys()) else 'uz'
    if user is None:
        start_parameter = message.command[1] if len(message.command) > 1 else None
        if start_parameter:
            proposed_user = User.select().where(User.id == start_parameter).first()
            proposed_user.proposals=proposed_user.proposals+1
            proposed_user.deep_proposals=proposed_user.deep_proposals+1
            proposed_user.save()
            await client.send_message(chat_id=start_parameter, text=languages[proposed_user.lang]['one_proposal'].format(proposed_user.deep_proposals))

        user = User.create(id=from_user.id, lang=language_code, premium=None, updated_at=datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
        asyncio.create_task(YtUpdate(client, from_user.id, message.chat.id))

    else:
        user.lang = language_code
        user.save()
    try:
        lang = from_user.language_code
        reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(languages[lang]['video'], switch_inline_query_current_chat='')],
        [InlineKeyboardButton(languages[lang]['channel'], switch_inline_query_current_chat='.c '),
        InlineKeyboardButton(languages[lang]['playlist'], switch_inline_query_current_chat='.p ')]
        ])
        await client.send_message(chat_id=message.chat.id, text=languages[lang]['wel'], reply_markup=reply_markup)
    except KeyError:
        reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(languages[lang]['video'], switch_inline_query_current_chat='')],
        [InlineKeyboardButton(languages[lang]['channel'], switch_inline_query_current_chat='.c '),
        InlineKeyboardButton(languages[lang]['playlist'], switch_inline_query_current_chat='.p ')]
        ])
        await client.send_message(chat_id=message.chat.id, text=languages['uz']['wel'], reply_markup=reply_markup)

@app.on_message(filters.command('menu'))
async def menu(client, message):
    user = User.select().where(User.id == message.from_user.id).first()
    await message.delete()
    lang = user.lang
    try:
        reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(languages[lang]['video'], switch_inline_query_current_chat='')],
        [InlineKeyboardButton(languages[lang]['channel'], switch_inline_query_current_chat='.c '),
        InlineKeyboardButton(languages[lang]['playlist'], switch_inline_query_current_chat='.p ')]
        ])
        await client.send_message(chat_id=message.chat.id, text='⚪️🔴⚪️\n🔴              @BreakTubebot\n⚪️⚪️', reply_markup=reply_markup)
    except KeyError:
        reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(languages[lang]['video'], switch_inline_query_current_chat='')],
        [InlineKeyboardButton(languages[lang]['channel'], switch_inline_query_current_chat='.c '),
        InlineKeyboardButton(languages[lang]['playlist'], switch_inline_query_current_chat='.p ')]
        ])
        await client.send_message(chat_id=message.chat.id, text='⚪️🔴⚪️\n🔴              @BreakTubebot\n⚪️⚪️', reply_markup=reply_markup)


@app.on_message(filters.command('lang'))
async def set_lang(client, message):
    user = User.get(id=message.from_user.id)
    language_dict = {
        'O\'zbek': 'uz',
        'English': 'en',
        'Русский': 'ru',
        'Français': 'fr',
        'Bahasa Indonesia': 'id',
        'Português': 'pt',
        'فارسی': 'ir',
        'Қазақ': 'kz',
        'Bahasa Melayu': 'my',
        'Italiano': 'it',
        'Español': 'es',
        'العربية': 'sa',
        'Українська': 'ua',
        'Deutsch': 'de'
    }
    buttons=[]
    index=0
    for x,y in language_dict.items():
        if index%2==0:
            buttons.append([InlineKeyboardButton(f'{flags_emoji_dict[y]} {x}', callback_data=f'lang:{y}')])
        else:
            buttons[(index//2)].append(InlineKeyboardButton(f'{flags_emoji_dict[y]} {x}', callback_data=f'lang:{y}'))
        index+=1
    buttons.append([InlineKeyboardButton('❌', callback_data='x:')])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.delete()
    await client.send_message(text=languages[user.lang]['lang'], chat_id=message.chat.id, reply_markup=reply_markup)

@app.on_message(filters.command('logs'))
async def logs(client, message):
    text='No logs..'

    with open('tmp/log.txt', 'r') as file:
        text=str(file.read())
    
    if len(text)>4090:
        for chunk in [text[i:i+4096] for i in range(0, len(text), 4096)]:
            await client.send_message(-1002092731391, text=chunk, reply_markup=x_markup)
    else:
        await client.send_message(-1002092731391, text=text, reply_markup=x_markup)
    
    with open('tmp/log.txt', 'w') as file:
        file.write('No logs..')
    await message.delete()

@app.on_message(filters.command('subs'))
async def get_subs(client, message):
    user=User.get(id=message.from_user.id)
    await message.delete()
    ids=user.get_channels()
    await YtChannels(ids, client, message.chat.id, user)

@app.on_message(filters.command('profile'))
async def get_profile(client, message):
    user=User.get(id=message.from_user.id)
    text=languages[user.lang]['profile'].format(
        len(user.get_channels()),
        str(user.premium).split(' ')[0].replace('-','.'),
        user.proposals
    )
    await message.delete()
    await client.send_message(text=text, chat_id=message.chat.id, reply_markup=x_markup)

@app.on_message(filters.command('premium'))
async def get_premium(client, message):
    user=User.get(id=message.from_user.id)
    text=languages[user.lang]['premium']

    reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(languages[user.lang]['buy'], callback_data='buy:cash')],
        [InlineKeyboardButton(languages[user.lang]['by_ton'], callback_data='buy:ton')],
        [InlineKeyboardButton(languages[user.lang]['by_proposal'], callback_data='buy:proposal'), InlineKeyboardButton('❌', callback_data='x:')]
    ])
    await message.delete()
    await client.send_message(text=text, chat_id=message.chat.id, reply_markup=reply_markup)

@app.on_message()
async def youlink(client, message):
    user = User.get(id=message.from_user.id)

    if message.text:
        urls = message.text.split()  # Split the message text by whitespace to extract URLs
        youtube_hosts = ["www.youtube.com", "youtube.com", "youtu.be", "m.youtube.com", "youtube.com/shorts"]
        await message.delete()
        count = len(urls)
        process_count = 0
        
        for url in urls:
            if process_count == 5:
                break
            
            parsed_url = urlparse(url)

            if parsed_url.netloc in youtube_hosts:
                query_params = parse_qs(parsed_url.query)
                count -= 1
                video_id = None

                if parsed_url.netloc == "youtu.be":
                    video_id = parsed_url.path.lstrip('/')
                elif parsed_url.netloc == "youtube.com" and parsed_url.path.startswith("/shorts/"):
                    video_id = parsed_url.path.split("/shorts/")[-1]
                elif 'v' in query_params:
                    video_id = query_params['v'][0]

                if 'list' in query_params:
                    playlist_id = query_params['list'][0]
                    playlist_info = await YtPlaylist(playlist_id, user.lang)
                    await sender.send_playlist_info(client, message.chat.id, playlist_info, user)
                elif video_id:
                    await sender.send_video_info(client, message.chat.id, video_id, user)
                else:
                    channel_path = parsed_url.path.split('/')

                    if len(channel_path) > 1 and channel_path[1] in ['user', 'channel']:
                        channel_info = await YtChannel(channel_path[2], user.lang)
                        await sender.send_channel_info(client, message.chat.id, channel_info, user)
                    else:
                        channel_info = await YtChannel(url, user.lang, True)
                        await sender.send_channel_info(client, message.chat.id, channel_info, user)
                
                process_count += 1

        if count == len(urls):
            await client.send_message(chat_id=message.chat.id, text=languages[user.lang]['bad_req'], reply_markup=x_markup)
    else:
        await client.send_message(chat_id=message.chat.id, text=languages[user.lang]['bad_req'], reply_markup=x_markup)

@app.on_callback_query()
async def handle_callback_query(client, callback_query):
    await event_controller(client, callback_query, app)

@app.on_inline_query()
async def handle_inline_query(client, inline_query):
    video_url = f'https://www.youtube.com/watch?v='
    channel_url = f"https://www.youtube.com/channel/"
    playlist_url=f"https://www.youtube.com/playlist?list="
    
    query=inline_query.query
    if not query.strip():
        query='uzbekistan'

    results=[]
    type_='video'
    search_query=query
    if query.startswith('.p'):
        type_='playlist'
        search_query=query.replace('.p', '')
    elif query.startswith('.c'):
        type_='channel'
        search_query=query.replace('.c', '')

    youtube = build('youtube', 'v3', developerKey=API_KEY())

    req=youtube.search().list(
        part='snippet',
        q=search_query,
        type=type_,
        maxResults=30
    )
    res=req.execute()

    for item in res['items']:
        match type_:
            case 'video':
                video_id=item['id']['videoId']
                item=item['snippet']
                results.append(InlineQueryResultArticle(
                    title=item['title'],
                    input_message_content=InputTextMessageContent(video_url+video_id),
                    description=f"📅 {item['publishedAt'].split('T')[0].replace('-','.')} | 🗣 {item['channelTitle']}",
                    thumb_url=item['thumbnails']['medium']['url']
                ))
            case 'channel':
                channel_id=item['id']['channelId']
                item=item['snippet']
                results.append(InlineQueryResultArticle(
                    title=item['title'],
                    input_message_content=InputTextMessageContent(channel_url+channel_id),
                    description=f"📅 {item['publishedAt'].split('T')[0].replace('-','.')}",
                    thumb_url=item['thumbnails']['medium']['url']
                ))
            case 'playlist':
                video_id=item['id']['playlistId']
                item=item['snippet']
                results.append(InlineQueryResultArticle(
                    title=item['title'],
                    input_message_content=InputTextMessageContent(playlist_url+video_id),
                    description=f"📅 {item['publishedAt'].split('T')[0].replace('-','.')} | 🗣 {item['channelTitle']}",
                    thumb_url=item['thumbnails']['medium']['url']
                ))
    
    await inline_query.answer(results)


if __name__ == '__main__':
    app.run()
