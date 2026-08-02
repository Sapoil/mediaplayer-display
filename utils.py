import pythoncom
from pycaw.pycaw import AudioUtilities
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)
from winrt.windows.storage.streams import DataReader, Buffer, InputStreamOptions
import base64
import os


def get_volume_interface():
    pythoncom.CoInitialize()
    device = AudioUtilities.GetSpeakers()
    return device.EndpointVolume if device else None


async def get_current_session():
    sessions = await MediaManager.request_async()
    return sessions.get_current_session()


# Takes the string describing the thumbnail and tranforms it in a b64 image, usable by JS
async def get_thumbnail_b64(thumbnail_ref):
    if thumbnail_ref is None:
        return None
    stream = await thumbnail_ref.open_read_async()
    size = stream.size
    buffer = Buffer(size)
    await stream.read_async(buffer, size, InputStreamOptions.READ_AHEAD)
    reader = DataReader.from_buffer(buffer)
    data = bytearray(size)
    reader.read_bytes(data)
    return base64.b64encode(bytes(data)).decode("ascii")


# Gets wanted info from windows media manager
async def get_media_info():
    current = await get_current_session()
    if not current:
        return None

    info = await current.try_get_media_properties_async()
    timeline = current.get_timeline_properties()
    playback = current.get_playback_info()
    source_app = current.source_app_user_model_id
    return {
        "title": info.title if info else "",
        "artist": info.artist if info else "",
        "album": info.album_title if info else "",
        "status": int(playback.playback_status),
        "position": timeline.position.total_seconds(),
        "duration": (timeline.end_time - timeline.start_time).total_seconds(),
        "thumbnail_b64": await get_thumbnail_b64(info.thumbnail if info else ""),
        "source_app": clean_source_app(source_app),
    }


KNOWN_APPS = {
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "spotify.exe": "Spotify",
    "vlc.exe": "VLC",
    "com.deezer.deezer-desktop": "Deezer",
    "microsoft.zunemusic_8wekyb3d8bbwe!microsoft.zunemusic": "Musique Windows",
}


def clean_source_app(aumid):
    if not aumid:
        return None
    if aumid.lower() in KNOWN_APPS:
        return KNOWN_APPS[aumid]
    # fallback : retire l'extension .exe si présent
    if aumid.lower().endswith(".exe"):
        return aumid[:-4]
    # fallback pour UWP : prend la partie après le "!"
    if "!" in aumid:
        return aumid.split("!")[-1]
    return aumid


def resource_path(relative_path):
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
