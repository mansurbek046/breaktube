from requests_html import HTMLSession
import re

def get_id(url):
    session = HTMLSession()

    r = session.get(url)

    channel_id_pattern = r'channelId":"(.*?)"'
    channel_id_match = re.search(channel_id_pattern, r.text)

    if channel_id_match:
        channel_id = channel_id_match.group(1)
        return channel_id
    else:
        return False
