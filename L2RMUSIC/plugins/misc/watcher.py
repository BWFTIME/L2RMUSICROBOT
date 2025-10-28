from pyrogram import filters
from pyrogram.types import Message

from L2RMUSIC import app
from L2RMUSIC.core.call import Ashish

welcome = 20
close = 30


@app.on_message(filters.video_chat_started, group=welcome)
@app.on_message(filters.video_chat_ended, group=close)
async def welcome(_, message: Message):
    await Ashish.stop_stream_force(message.chat.id)
