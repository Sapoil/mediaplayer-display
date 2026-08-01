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

# TODO: Meilleure qualité de thumbnail ?
# TODO: Icône barre des tâches et icône aperçu fenêtre
# TODO: Ajouter quel site/app joue le média en question (+ autre fonctionnalité, par exemple YT n'update sa timeline qu'à la pause)
# TODO: Ajouter des contrôles : Pause/Play, Next, Before (+ Timeline position ? Volume ?) si impossible, au minimum display si lecture en cours ou en pause
# TODO? Potentielle modification du style d'affichage/ajouts
# TODO: Vérifier si une adaptation sous Linux est possible

WINDOW_TITLE = "Now Playing"


# Class used as a link between the Pyhton and JS code, its methods can be called by JS
class Api:
    def __init__(self):
        self.latest_data = None

    # Function called by JS to fecth the data about the current media playing
    def get_now_playing(self):
        return self.latest_data or {}

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
    sessions = await MediaManager.request_async()
    current = sessions.get_current_session()
    if not current:
        return None

    info = await current.try_get_media_properties_async()
    timeline = current.get_timeline_properties()
    playback = current.get_playback_info()

    return {
        "title": info.title if info else "",
        "artist": info.artist if info else "",
        "album": info.album_title if info else "",
        "status": int(playback.playback_status),
        "position": timeline.position.total_seconds(),
        "duration": (timeline.end_time - timeline.start_time).total_seconds(),
        "thumbnail_b64": await get_thumbnail_b64(info.thumbnail if info else ""),
    }


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
    webview.start(debug=False)
