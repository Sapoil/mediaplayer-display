import asyncio
import webview
import os
import psutil
from utils import get_volume_interface, get_current_session, get_media_info


# Class used as a link between the Pyhton and JS code, its methods can be called by JS
class Api:
    def __init__(self):
        self.latest_data = None
        self.vol = get_volume_interface()

    # Function called by JS to fecth the data about the current media playing
    def get_now_playing(self):
        data = dict(self.latest_data) if self.latest_data else {}
        try:
            if self.vol:
                data["volume"] = round(self.vol.GetMasterVolumeLevelScalar(), 2)
                data["muted"] = bool(self.vol.GetMute())
            else:
                self.vol = get_volume_interface()
        except Exception as e:
            print(f"volume error: {e}")
        return data

    def play_pause(self):
        async def _do():
            session = await get_current_session()
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
            session = await get_current_session()
            if session:
                await session.try_skip_next_async()

        asyncio.run(_do())

    def previous_track(self):
        async def _do():
            session = await get_current_session()
            if session:
                await session.try_skip_previous_async()

        asyncio.run(_do())

    def seek(self, position_seconds):
        async def _do():
            session = await get_current_session()
            if session:
                ticks = int(position_seconds * 10_000_000)  # secondes -> ticks (100ns)
                await session.try_change_playback_position_async(ticks)
            await asyncio.sleep(0.15)
            return await get_media_info()

        data = asyncio.run(_do())
        if data:
            self.latest_data = data
        return data

    def set_volume(self, value):
        try:
            value = max(0.0, min(1.0, float(value)))
            if self.vol:
                self.vol.SetMasterVolumeLevelScalar(value, None)
                if value > 0 and self.vol.GetMute():
                    self.vol.SetMute(0, None)
            else:
                self.vol = get_volume_interface()
            return {"volume": value, "muted": False}
        except Exception:
            return None

    def toggle_mute(self):
        try:
            if self.vol:
                new_state = not self.vol.GetMute()
                self.vol.SetMute(new_state, None)
                return {
                    "volume": round(self.vol.GetMasterVolumeLevelScalar(), 2),
                    "muted": bool(new_state),
                }
            else:
                self.vol = get_volume_interface()
                return None
        except Exception as e:
            print(f"toggle_mute error: {e}")
            return None

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
