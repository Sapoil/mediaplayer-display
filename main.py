import asyncio
import base64
import threading
import webview
import os
import psutil
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)
from winrt.windows.storage.streams import DataReader, Buffer, InputStreamOptions

# TODOLATER: Meilleure qualité de thumbnail ?
# FIXME: Icône bien affiché sauf dans la barre des tâches, à vérifier après déploiement
# TODO: Volume
# TODO? Potentielle modification du style d'affichage/ajouts
# TODO: Vérifier si une adaptation sous Linux est possible

WINDOW_TITLE = "Now Playing"


async def _get_current_session():
    sessions = await MediaManager.request_async()
    return sessions.get_current_session()


# Class used as a link between the Pyhton and JS code, its methods can be called by JS
class Api:
    def __init__(self):
        self.latest_data = None

    # Function called by JS to fecth the data about the current media playing
    def get_now_playing(self):
        return self.latest_data or {}

    def play_pause(self):
        async def _do():
            session = await _get_current_session()
            if session:
                await session.try_toggle_play_pause_async()
            # petit délai pour laisser le temps à l'app source de mettre à jour son état SMTC
            await asyncio.sleep(0.15)
            return await get_media_info()

        data = asyncio.run(_do())
        if data:
            self.latest_data = data  # évite un flicker au prochain tick du polling
        return data

    def next_track(self):
        async def _do():
            session = await _get_current_session()
            if session:
                await session.try_skip_next_async()

        asyncio.run(_do())

    def previous_track(self):
        async def _do():
            session = await _get_current_session()
            if session:
                await session.try_skip_previous_async()

        asyncio.run(_do())

    def seek(self, position_seconds):
        async def _do():
            session = await _get_current_session()
            if session:
                ticks = int(position_seconds * 10_000_000)  # secondes -> ticks (100ns)
                await session.try_change_playback_position_async(ticks)
            await asyncio.sleep(0.15)
            return await get_media_info()

        data = asyncio.run(_do())
        if data:
            self.latest_data = data
        return data

    # Closes the app as quickly and cleanly as possible, first we destroy the window so the user doesn't see it right after clicking then we destroy the children processes and then we call os._exit(0) to assure everything was closed
    def close_app(self):
        try:
            if webview.windows:
                webview.windows[0].destroy()
            parent = psutil.Process(os.getpid())
            for child in parent.children(recursive=True):
                child.kill()
        except Exception:
            pass
        os._exit(0)

    # Toggles fullscreen from webview
    def toggle_fullscreen(self):
        if webview.windows:
            webview.windows[0].maximize()
            webview.windows[0].toggle_fullscreen()


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
    current = await _get_current_session()
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


# Defines a loop that fetches the data from windows media manager every second and puts it in Api.latest_data for JS to fetch
def polling_loop(api):
    async def loop():
        while True:
            api.latest_data = await get_media_info()
            await asyncio.sleep(1)

    asyncio.run(loop())


if __name__ == "__main__":
    api = Api()
    window = webview.create_window(
        title=WINDOW_TITLE,
        url="ui.html",
        fullscreen=True,
        frameless=True,
        easy_drag=False,
        js_api=api,
    )
    threading.Thread(target=polling_loop, args=(api,), daemon=True).start()
    webview.start(debug=False, icon="icon.ico")
