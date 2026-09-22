"""Execute one decided action. Every function returns a one-line description for the history."""

from __future__ import annotations

import time
from dataclasses import dataclass

import anthropic
from typesafe_sdk import TypeSafeClient

from . import platform_adapter as macos
from .config import SITES
from .decide import OFFSCREEN_PREFIX, Decision, verify_typed
from .models import Field, Item, Screen
from .writer import compose_text, compose_url

VERIFY_THRESHOLD = 0.5
NOOP_MARKERS = ("refused", "failed", "waited")


@dataclass(frozen=True)
class Context:
    goal: str
    browser: str
    email: str | None
    typesafe: TypeSafeClient
    writer: anthropic.Anthropic | None
    history: list[str]


def is_noop(description: str) -> bool:
    return any(marker in description for marker in NOOP_MARKERS)


def perform(decision: Decision, screen: Screen, items: list[Item], ctx: Context) -> str:
    key = decision.chosen
    by_index = {str(it.index): it for it in items}
    if key in by_index:
        return click_item(by_index[key], screen)
    if key.startswith(OFFSCREEN_PREFIX):
        return press_offscreen(key[len(OFFSCREEN_PREFIX) :], screen)
    handler = _HANDLERS.get(key)
    if handler is None:
        raise ValueError(f"unknown action {key!r}")
    return handler(decision, screen, items, ctx)


def click_item(item: Item, screen: Screen) -> str:
    """Press an item the app declared through the accessibility tree; click the pixel under it otherwise.

    A press goes to the control itself, so it lands even when the center of the box is covered by
    a sticky header, a cookie banner, or a tooltip. An element that refuses still has a location.
    """
    ref = screen.ax_refs.get(item.index)
    if ref is not None and macos.ax_press(ref):
        return f"pressed {item.text!r} via accessibility"
    macos.click_at(screen.to_points(item))
    if ref is None:
        return f"clicked {item.text!r}"
    return f"clicked {item.text!r} (accessibility press did not take)"


def press_offscreen(key: str, screen: Screen) -> str:
    """Press a control the app exposes but does not show.

    AXPress does not need the element to be visible: a note row scrolled thousands of points down
    and a link the browser parked above the viewport both take it. There is no pixel to fall back
    on, so a refusal is the end of it and reads as a no-op.
    """
    nodes = screen.offscreen
    node = nodes[int(key)] if key.isdigit() and int(key) < len(nodes) else None
    if node is None:
        return f"press_offscreen refused: there is no off-screen control {key!r}"
    if macos.ax_press(node.ref):
        return f"pressed {node.label!r} (off-screen control) via accessibility"
    return f"press_offscreen refused: {node.label!r} did not accept the press"


def fill_field(field: Field, text: str) -> str:
    """Put text in the focused field, by value if the element accepts one and keystrokes otherwise.

    Setting the value is one message instead of one per character, and it cannot be stolen by a
    page that moves the focus mid-word. It is also widely ignored, so the value is read back and
    only a field that really holds the text counts. Returns which path ran, for the history.
    """
    ref = field.ref
    if ref is not None:
        macos.ax_focus(ref)
        if macos.ax_set_value(ref, text):
            back = macos.ax_value(ref)
            if back is not None and back.endswith(text):
                return "via accessibility"
    macos.type_text(text)
    return "via keystrokes"


def _use_browser(decision: Decision, screen, items, ctx: Context) -> str:
    """Go to the browser, and open the website the site answer named.

    `none` is the page already open there, so bringing the browser forward is the whole action. A
    catalog key is its URL, and `other` is a site outside the catalog, which only the writer can
    name. Opening a URL activates the browser too, so the three cases differ only in the page.
    """
    site = decision.site.choice
    if site == "none":
        if macos.activate(ctx.browser):
            return f"activated {ctx.browser}"
        return f"use_browser failed: {ctx.browser} did not come to the front"
    url = SITES.get(site)
    if url is None:
        if ctx.writer is None:
            return "use_browser refused: the site is outside the catalog and no writer is available to propose a URL"
        url = compose_url(ctx.writer, ctx.goal, ctx.history)
    if not url:
        return "use_browser refused: the writer proposed no usable URL for this goal"
    if macos.open_url(ctx.browser, url):
        return f"opened {url}"
    return f"use_browser failed: opened {url} but {ctx.browser} did not come to the front"


def _type_email(decision, screen: Screen, items, ctx: Context) -> str:
    if not (screen.field and screen.field.is_text):
        return "type_email refused: no text field is focused"
    how = fill_field(screen.field, ctx.email or "")
    return f"typed email {how}"


def _extract_local_text(goal: str) -> str:
    """Extract search query or text payload from a natural language goal."""
    g = goal.strip()
    g_lower = g.lower()
    triggers = [
        "ask for ",
        "ask about ",
        "ask ",
        "search for ",
        "search ",
        "type ",
        "enter ",
        "write ",
        "query ",
        "find ",
    ]
    if " and " in g_lower:
        part = g.split(" and ", 1)[1].strip()
        for trig in triggers:
            if trig in part.lower():
                idx = part.lower().index(trig) + len(trig)
                return part[idx:].strip()
        return part

    for trig in triggers:
        if trig in g_lower:
            idx = g_lower.index(trig) + len(trig)
            return g[idx:].strip()

    return g


def _type_text(decision, screen: Screen, items, ctx: Context) -> str:
    if not (screen.field and screen.field.is_text):
        return "type_text refused: no text field is focused"
    if ctx.writer is None:
        text = _extract_local_text(ctx.goal)
        if not text:
            return "type_text refused: no text extracted to type"
        how = fill_field(screen.field, text)
        time.sleep(0.3)
        macos.press("return")
        return f"typed {text!r} into {screen.field.label!r} {how} and pressed Return"

    text = compose_text(ctx.writer, ctx.goal, screen, items, ctx.history)
    if not text:
        return "type_text refused: writer declined to fill this field"
    how = fill_field(screen.field, text)
    time.sleep(0.3)
    p = verify_typed(ctx.typesafe, ctx.goal, screen.field, text, macos.focused_field())
    if p < VERIFY_THRESHOLD:
        macos.clear_field()
        return f"typed {text!r} into {screen.field.label!r} {how} but verification failed ({p:.2f}); cleared it"
    return f"typed {text!r} into {screen.field.label!r} {how} (verified {p:.2f})"


def _key(name: str, description: str):
    def handler(decision, screen, items, ctx) -> str:
        macos.press(name)
        return description

    return handler


def _scroll(lines: int, description: str):
    def handler(decision, screen, items, ctx) -> str:
        macos.scroll(lines)
        return description

    return handler


def _extract_app_name(goal: str) -> str:
    g_lower = goal.lower()
    known = {
        "spotify": "Spotify",
        "notepad": "Notepad",
        "calculator": "Calculator",
        "calc": "Calculator",
        "explorer": "File Explorer",
        "files": "File Explorer",
        "terminal": "Windows Terminal",
        "cmd": "Windows Terminal",
        "vs code": "Visual Studio Code",
        "vscode": "Visual Studio Code",
        "slack": "Slack",
    }
    for k, name in known.items():
        if k in g_lower:
            return name
    for verb in ("open ", "launch ", "start "):
        if verb in g_lower:
            part = g_lower.split(verb, 1)[1].split()[0]
            return part.title()
    return "App"


def _launch_app(decision, screen: Screen, items, ctx: Context) -> str:
    app_name = _extract_app_name(ctx.goal)
    ok = macos.launch_or_activate_app(app_name)
    time.sleep(1.0)
    if ok:
        return f"launched {app_name} and brought it to the front"
    return f"launch_app failed: could not open or activate {app_name}"


def _play_media(decision, screen: Screen, items, ctx: Context) -> str:
    macos.play_media()
    return "played media (sent play/pause)"


_HANDLERS = {
    "use_browser": _use_browser,
    "launch_app": _launch_app,
    "play_media": _play_media,
    "type_email": _type_email,
    "type_text": _type_text,
    "press_enter": _key("return", "pressed Return"),
    "press_escape": _key("escape", "pressed Escape"),
    "scroll_down": _scroll(-10, "scrolled down"),
    "scroll_up": _scroll(10, "scrolled up"),
    "wait": lambda decision, screen, items, ctx: "waited",
}
