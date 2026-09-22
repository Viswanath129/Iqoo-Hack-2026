from PIL import Image
from typesafe_computer_use.decide import decide, decide_local
from typesafe_computer_use.models import Item, Screen


def test_decide_local_use_browser():
    img = Image.new("RGB", (100, 100))
    screen = Screen(image=img, scale=1.0, app="Explorer", field=None, url=None)
    items = []
    decision = decide_local("Open GitHub", screen, items, [], "Google Chrome", None)
    assert decision.kind.choice == "use_browser"
    assert decision.site.choice == "github"


def test_decide_local_matches_item():
    img = Image.new("RGB", (100, 100))
    screen = Screen(image=img, scale=1.0, app="Chrome", field=None, url="https://github.com")
    item0 = Item(index=0, text="Repositories", ocr_confidence=1.0, x1=10, y1=10, x2=50, y2=30, role="button", source="ocr")
    item1 = Item(index=1, text="Settings", ocr_confidence=1.0, x1=60, y1=10, x2=100, y2=30, role="button", source="ocr")
    decision = decide_local("click on Settings", screen, [item0, item1], [], "Google Chrome", None)
    assert decision.kind.choice == "click_item"
    assert decision.item.choice == "1"


def test_decide_dispatches_to_local_when_client_is_none():
    img = Image.new("RGB", (100, 100))
    screen = Screen(image=img, scale=1.0, app="Explorer", field=None, url=None)
    decision = decide(None, "Go to Linear", screen, [], [], "Google Chrome", None)
    assert decision.kind.choice == "use_browser"
    assert decision.site.choice == "linear"


def test_decide_local_chatgpt_query():
    img = Image.new("RGB", (100, 100))
    screen = Screen(image=img, scale=1.0, app="Windows Terminal", field=None, url=None)
    items = []
    decision = decide_local("open chatgpt and ask for todays whether in tuni?", screen, items, [], "Google Chrome", None)
    assert decision.kind.choice == "use_browser"
    assert decision.site.choice == "chatgpt"


def test_decide_local_open_spotify():
    img = Image.new("RGB", (100, 100))
    screen = Screen(image=img, scale=1.0, app="Windows Terminal", field=None, url=None)
    items = []
    decision = decide_local("open Spotify and play a song for me", screen, items, [], "Google Chrome", None)
    assert decision.kind.choice == "launch_app"


def test_decide_local_play_media_when_spotify_front():
    img = Image.new("RGB", (100, 100))
    screen = Screen(image=img, scale=1.0, app="Spotify", field=None, url=None)
    items = []
    decision = decide_local("open Spotify and play a song for me", screen, items, ["launched Spotify and brought it to the front"], "Google Chrome", None)
    assert decision.kind.choice == "play_media"
