import asyncio
import os
import re
import json
import glob
import random
import logging
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from L2RMUSIC.utils.database import is_on_off
from L2RMUSIC.utils.formatters import time_to_seconds

# ===========================================
# Logging Configuration
# ===========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ===========================================
# Helper: Select Cookie File
# ===========================================
def cookie_txt_file() -> str:
    folder_path = os.path.join(os.getcwd(), "cookies")
    filename = os.path.join(folder_path, "logs.csv")
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    
    if not txt_files:
        logging.error("No .txt cookie files found in cookies folder.")
        raise FileNotFoundError("No .txt cookie files found in the cookies folder.")
    
    chosen_file = random.choice(txt_files)
    with open(filename, "a") as f:
        f.write(f"Chosen File: {chosen_file}\n")
    
    return os.path.join("cookies", os.path.basename(chosen_file))

# ===========================================
# Helper: Check YouTube Video Size
# ===========================================
async def check_file_size(link: str) -> Union[int, None]:
    async def get_format_info(url):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logging.error(f"yt-dlp error (check_file_size): {stderr.decode()}")
            return None
        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError:
            logging.error("Failed to parse yt-dlp JSON output.")
            return None

    info = await get_format_info(link)
    if not info:
        return None

    total_size = 0
    for f in info.get("formats", []):
        if f.get("filesize"):
            total_size += f["filesize"]

    return total_size if total_size > 0 else None

# ===========================================
# Helper: Shell Command Executor
# ===========================================
async def shell_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if stderr and b"unavailable videos are hidden" not in stderr.lower():
        logging.error(stderr.decode())
    return stdout.decode().strip()

# ===========================================
# Main YouTubeAPI Class
# ===========================================
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Union[str, None]:
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)

        for msg in messages:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for entity in entities:
                if entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
                    return text[entity.offset:entity.offset + entity.length]
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        search = VideosSearch(link, limit=1)
        data = (await search.next())["result"][0]
        title = data["title"]
        duration = data["duration"] or "0:00"
        thumb = data["thumbnails"][0]["url"].split("?")[0]
        vidid = data["id"]
        return title, duration, int(time_to_seconds(duration)), thumb, vidid

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--cookies", cookie_txt_file(), "-g", "-f", "18/best", link,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().strip().split("\n")[0]
        else:
            logging.error(f"yt-dlp video fetch error: {stderr.decode()}")
            return 0, stderr.decode()

    async def playlist(self, link, limit):
        link = link.split("&")[0]
        cmd = f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        output = await shell_cmd(cmd)
        result = [i for i in output.split("\n") if i.strip()]
        return result

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]

        ydl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ydl_opts)
        try:
            with ydl:
                info = ydl.extract_info(link, download=False)
                formats = []
                for fmt in info.get("formats", []):
                    if not fmt.get("filesize") or "dash" in fmt.get("format", "").lower():
                        continue
                    formats.append({
                        "format": fmt["format"],
                        "filesize": fmt["filesize"],
                        "format_id": fmt["format_id"],
                        "ext": fmt["ext"],
                        "format_note": fmt.get("format_note", ""),
                        "yturl": link,
                    })
                return formats, link
        except Exception as e:
            logging.error(f"Failed to extract formats: {e}")
            return [], link

    # ===========================================
    # Download Function (Audio/Video)
    # ===========================================
    async def download(
        self,
        link: str,
        video: bool = False,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: str = None,
        title: str = None,
    ):
        if "&" in link:
            link = link.split("&")[0]

        loop = asyncio.get_running_loop()

        # Define executor downloaders
        def run_dl(ydl_opts):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    return ydl.prepare_filename(info)
            except Exception as e:
                logging.error(f"Download failed: {e}")
                return None

        if songvideo:
            opts = {
                "format": f"{format_id}+140",
                "outtmpl": f"downloads/{title}.%(ext)s",
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "merge_output_format": "mp4",
            }
            result = await loop.run_in_executor(None, run_dl, opts)
            return result

        elif songaudio:
            opts = {
                "format": format_id or "bestaudio/best",
                "outtmpl": f"downloads/{title}.%(ext)s",
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            result = await loop.run_in_executor(None, run_dl, opts)
            return result

        elif video:
            opts = {
                "format": "(bestvideo[height<=720][ext=mp4])+bestaudio[ext=m4a]",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "merge_output_format": "mp4",
            }
            result = await loop.run_in_executor(None, run_dl, opts)
            return result

        else:
            opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            result = await loop.run_in_executor(None, run_dl, opts)
            return result
