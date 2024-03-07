from peewee import *
import psycopg2
import json
from credentials import dbname, dbuser, dbhost, dbpassword

db=PostgresqlDatabase(
    dbname,
    user=dbuser,
    host=dbhost,
    password=dbpassword
)

class TgField(CharField):
    def __init__(self):
        super().__init__(primary_key=True)

class User(Model):
    id = TgField()
    channels = BlobField(default=b'[]')
    lang = CharField(max_length=3)
    premium = DateTimeField(null=True)
    updated_at = DateTimeField()
    proposals = BigIntegerField(default=0)
    deep_proposals = BigIntegerField(default=0)
    
    class Meta:
        database = db

    def get_channels(self):
        channels_bytes = bytes(self.channels)
        return json.loads(channels_bytes.decode())

    def add_channel(self, channel_id):
        channel_list = self.get_channels()
        if channel_id not in channel_list:
            channel_list.append(channel_id)
            self.channels = json.dumps(channel_list).encode()
            self.save()
            return True
        return False

    def remove_channel(self, channel_id):
            channel_list = self.get_channels()
            if channel_id in channel_list:
                channel_list.remove(channel_id)
                self.channels = json.dumps(channel_list).encode()
                self.save()
                return True
            return False

class Video(Model):
    id=TgField()
    youtube_id=CharField()
    resolution=CharField()

    class Meta:
        database = db

class Audio(Model):
    id=TgField()
    youtube_id=CharField()

    class Meta:
        database=db

db.connect()
db.create_tables([User, Video, Audio])
db.close()
