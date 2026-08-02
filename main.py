import asyncio
import threading
import webview
from api import Api
from utils import resource_path, get_media_info

# TODOLATER: Meilleure qualité de thumbnail ? Il faudrait faire une requête directement sur une plateforme (Deezer par exemple)
# TODO? Potentielle modification du style d'affichage/ajouts
# TODO: Vérifier si une adaptation sous Linux est possible

WINDOW_TITLE = "Now Playing"


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
        url=resource_path("ui.html"),
        fullscreen=True,
        frameless=True,
        easy_drag=False,
        js_api=api,
    )
    threading.Thread(target=polling_loop, args=(api,), daemon=True).start()
    webview.start(debug=False, icon=resource_path("icon.ico"))
