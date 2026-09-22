"""Decision engine: on-device SLM (primary), cloud TypeSafe JEV (fallback), keyword heuristics (last resort)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from typesafe_sdk import Choice, ChoiceAnswer, Noul, TypeSafeClient

from .config import SITES

logger = logging.getLogger(__name__)
from .dates import date_hints, now_context
from .models import AxNode, Field, Item, Screen

STOP_KINDS = ("done", "none")
OFFSCREEN_PREFIX = "offscreen:"
PRESS_OFFSCREEN = (
    "Activate a labelled control that the app exposes but that is not currently visible on screen "
    "(chosen in the offscreen question). Use when the needed control is known to exist but is "
    "scrolled out of view or not yet shown."
)


def fixed_actions(browser: str, email: str | None) -> dict[str, str]:
    """Deterministic actions offered alongside click_item. Keep them mutually exclusive."""
    actions = {
        "use_browser": (
            f"Work in {browser}: bring it to the front, and open a website there if one is needed. The "
            "site question says which website, or says that the page already open there is the one to "
            "continue with. This is the only way to reach a website: never click the address bar, a URL, "
            "or a search box to get there. Works from any app, including this one."
        ),
        "launch_app": (
            "Open or bring a desktop application to the front (e.g. Spotify, Notepad, Calculator, "
            "File Explorer, Windows Terminal, Slack, VS Code). Use whenever the goal mentions opening, "
            "launching, or switching to a desktop application."
        ),
        "play_media": (
            "Play, pause, or resume media or music playback (sends play/pause media key or space). "
            "Use when the goal is to play music, play a song, pause, or resume audio."
        ),
        "type_text": (
            "Type free text into the focused text field. A writing model composes the text from the "
            "goal and the field's label. Only valid when a text field is focused and needs content."
        ),
        "press_enter": "Press Return to submit the focused form or field.",
        "press_escape": "Press Escape to dismiss a dialog, menu, or popup.",
        "scroll_down": "Scroll down to reveal more of the page.",
        "scroll_up": "Scroll up.",
        "wait": "Nothing to do yet; the screen is still loading or changing.",
        "done": "The goal is already achieved.",
        "none": "Nothing on screen or in this list helps with the goal.",
    }
    if email:
        actions["type_email"] = (
            "Type the user's email address into the focused text field. Use this, not type_text, "
            "whenever the field wants an email or username."
        )
    return actions


def kind_criteria(browser: str, email: str | None, offscreen: bool = False) -> dict[str, str]:
    clicks = {"click_item": "Click one of the on-screen text items (chosen in the item question)."}
    if offscreen:
        clicks["press_offscreen"] = PRESS_OFFSCREEN
    return {**clicks, **fixed_actions(browser, email)}


def item_criteria(screen: Screen, items: list[Item]) -> dict[str, str]:
    """Each item as one line. A role prefix marks the ones the app itself declared."""
    hints = date_hints(items, screen)
    return {
        str(it.index): (
            f"{it.role + ' ' if it.from_ax and it.role else ''}{it.text!r} "
            f"({screen.region(it)}{'; ' + hints[it.index] if it.index in hints else ''})"
        )
        for it in items
    }


def offscreen_criteria(nodes: list[AxNode]) -> dict[str, str]:
    """Each off-screen control as one line, keyed by its position in `screen.offscreen`."""
    return {str(i): f"{node.role_word} {node.label!r} (not visible)" for i, node in enumerate(nodes)}


def offscreen_records(nodes: list[AxNode]) -> list[dict]:
    """The same controls as state, with the key the offscreen question answers with."""
    return [{"k": i, "role": node.role_word, "label": node.label} for i, node in enumerate(nodes)]


def site_criteria() -> dict[str, str]:
    """Which website use_browser opens. The catalog, plus one key for anything else and one for nothing."""
    return {
        **SITES,
        "other": "A website is needed to progress the goal, but it is not one of the sites named in this list.",
        "none": "No website needs to be opened: the page already open in the browser is the one to continue with.",
    }


def base_state(goal: str, screen: Screen, items: list[Item], history: list[str]) -> dict:
    hints = date_hints(items, screen)
    return {
        "goal": goal,
        "now": now_context(),
        "frontmost_app": screen.app,
        "browser_active_tab_url": screen.url,
        "focused_field": screen.field.summary() if screen.field else None,
        "previous_actions": history[-8:],
        "screen_items_in_reading_order": [
            {
                "i": it.index,
                "text": it.text,
                "where": screen.region(it),
                **({"role": it.role} if it.role else {}),
                **({"when": hints[it.index]} if it.index in hints else {}),
            }
            for it in items
        ],
        **({"offscreen_controls": offscreen_records(screen.offscreen)} if screen.offscreen else {}),
    }


@dataclass(frozen=True)
class Decision:
    kind: ChoiceAnswer
    item: ChoiceAnswer | None
    site: ChoiceAnswer
    offscreen: ChoiceAnswer | None = None

    @property
    def clicking(self) -> bool:
        return self.kind.choice == "click_item" and self.item is not None

    @property
    def pressing_offscreen(self) -> bool:
        return self.kind.choice == "press_offscreen" and self.offscreen is not None

    @property
    def chosen(self) -> str:
        if self.clicking:
            return self.item.choice
        if self.pressing_offscreen:
            return f"{OFFSCREEN_PREFIX}{self.offscreen.choice}"
        return self.kind.choice

    @property
    def confidence(self) -> float:
        # Only the answers that name a target lower the confidence: a click or a press lands
        # somewhere, and the wrong somewhere is not undone. use_browser reads the site answer too,
        # but every outcome of it is a page the next step can leave, so a split there must not
        # stop the run.
        if self.clicking:
            return min(self.kind.confidence, self.item.confidence)
        if self.pressing_offscreen:
            return min(self.kind.confidence, self.offscreen.confidence)
        return self.kind.confidence

    @property
    def stops(self) -> bool:
        return self.kind.choice in STOP_KINDS


def decide_local(
    goal: str, screen: Screen, items: list[Item], history: list[str], browser: str, email: str | None
) -> Decision:
    """Fast, deterministic local decision making on-device without cloud API calls."""
    goal_lower = goal.lower()
    is_browser_front = any(b in screen.app.lower() for b in ("edge", "chrome", "firefox", "brave", "opera", "browser"))

    # 0. Media playback control (e.g. "play a song", "play music")
    play_words = ("play a song", "play music", "play song", "play audio", "resume", "pause music", "pause song", "play")
    is_media_request = any(w in goal_lower for w in play_words)
    is_music_app = any(app in screen.app.lower() for app in ("spotify", "media", "groove", "vlc"))

    if is_media_request and is_music_app:
        return Decision(
            kind=ChoiceAnswer(choice="play_media", confidence=0.95, probabilities={"play_media": 0.95}),
            item=None,
            site=ChoiceAnswer(choice="none", confidence=1.0, probabilities={"none": 1.0}),
            offscreen=None,
        )

    # 1. Desktop app launching (e.g., "open spotify", "open notepad", "open calculator")
    KNOWN_DESKTOP_APPS = {
        "spotify": "Spotify",
        "notepad": "Notepad",
        "calculator": "Calculator",
        "calc": "Calculator",
        "file explorer": "File Explorer",
        "explorer": "File Explorer",
        "terminal": "Windows Terminal",
        "cmd": "Windows Terminal",
        "vs code": "Visual Studio Code",
        "vscode": "Visual Studio Code",
        "slack": "Slack",
    }
    already_launched = any("launched " in h for h in history)
    if not already_launched:
        for app_kw, app_name in KNOWN_DESKTOP_APPS.items():
            if app_kw in goal_lower and app_name.lower() not in screen.app.lower():
                return Decision(
                    kind=ChoiceAnswer(choice="launch_app", confidence=0.95, probabilities={"launch_app": 0.95}),
                    item=None,
                    site=ChoiceAnswer(choice="none", confidence=1.0, probabilities={"none": 1.0}),
                    offscreen=None,
                )

    # 2. Text input when field is already focused
    if screen.field and screen.field.is_text:
        return Decision(
            kind=ChoiceAnswer(choice="type_text", confidence=0.95, probabilities={"type_text": 0.95}),
            item=None,
            site=ChoiceAnswer(choice="none", confidence=1.0, probabilities={"none": 1.0}),
            offscreen=None,
        )

    # 3. If browser is not yet frontmost, open the requested site
    already_opened = any("opened " in h for h in history)
    if not is_browser_front and not already_opened:
        for site_key, site_url in SITES.items():
            domain = site_key.replace("_", "")
            if site_key in goal_lower or domain in goal_lower:
                return Decision(
                    kind=ChoiceAnswer(choice="use_browser", confidence=0.95, probabilities={"use_browser": 0.95}),
                    item=None,
                    site=ChoiceAnswer(choice=site_key, confidence=0.95, probabilities={site_key: 0.95}),
                    offscreen=None,
                )

    # 3. If in browser and looking for an input/message box to click & focus
    if is_browser_front or already_opened:
        chat_keywords = ("ask anything", "message chatgpt", "search", "ask", "type a message", "message", "chat")
        for it in items:
            it_text_lower = it.text.lower()
            if any(kw in it_text_lower for kw in chat_keywords) or it.role in ("field", "edit", "AXTextField", "AXTextArea"):
                idx_str = str(it.index)
                return Decision(
                    kind=ChoiceAnswer(choice="click_item", confidence=0.92, probabilities={"click_item": 0.92}),
                    item=ChoiceAnswer(choice=idx_str, confidence=0.92, probabilities={idx_str: 0.92}),
                    site=ChoiceAnswer(choice="none", confidence=1.0, probabilities={"none": 1.0}),
                    offscreen=None,
                )

    # 4. Matching goal against visible screen items
    best_item = None
    best_score = 0
    goal_words = set(goal_lower.split())
    stop_words = {"the", "a", "an", "on", "in", "to", "and", "or", "click", "open", "select", "press", "go"}
    keywords = goal_words - stop_words

    for it in items:
        it_lower = it.text.lower()
        it_words = set(it_lower.split())
        common = keywords.intersection(it_words)
        score = len(common) * 2
        for kw in keywords:
            if kw in it_lower:
                score += 3
        if it.role:  # prefer interactive controls
            score += 1
        if score > best_score:
            best_score = score
            best_item = it

    if best_item is not None and best_score > 0:
        idx_str = str(best_item.index)
        conf = min(0.95, 0.5 + best_score * 0.1)
        return Decision(
            kind=ChoiceAnswer(choice="click_item", confidence=conf, probabilities={"click_item": conf}),
            item=ChoiceAnswer(choice=idx_str, confidence=conf, probabilities={idx_str: conf}),
            site=ChoiceAnswer(choice="none", confidence=1.0, probabilities={"none": 1.0}),
            offscreen=None,
        )

    # 5. If nothing else, finish
    return Decision(
        kind=ChoiceAnswer(choice="done", confidence=0.8, probabilities={"done": 0.8}),
        item=None,
        site=ChoiceAnswer(choice="none", confidence=1.0, probabilities={"none": 1.0}),
        offscreen=None,
    )


def decide(
    client: TypeSafeClient | None, goal: str, screen: Screen, items: list[Item], history: list[str], browser: str, email: str | None
) -> Decision:
    # 1. Try on-device SLM (Hexagon NPU) — fastest, no network, HackTracker sees it
    try:
        from .slm_decide import slm_available, slm_decide
        if slm_available():
            return slm_decide(goal, screen, items, history, browser, email)
    except Exception as e:
        logger.debug("SLM decision failed, trying next backend: %s", e)

    # 2. Fall back to cloud JEV API
    if client is None:
        return decide_local(goal, screen, items, history, browser, email)

    questions = {
        "kind": Choice(
            instructions=(
                "You are driving this computer one action at a time. Which kind of action "
                "makes the most progress toward the goal right now? Do not repeat an action "
                "that was just taken unless the screen changed."
            ),
            criteria=kind_criteria(browser, email, bool(screen.offscreen)),
        ),
        "site": Choice(
            instructions=(
                "If the browser is used this step, which website should it show? Name a site from the "
                "list when the goal calls for that one, 'other' when the goal calls for a site the list "
                "does not name, and 'none' to stay on the page that is already open in the browser."
            ),
            criteria=site_criteria(),
        ),
    }
    if items:
        questions["item"] = Choice(
            instructions=(
                "If clicking an on-screen item is the right move, which item? Items marked with a "
                "role come from the app's accessibility tree and are real controls; plain items are "
                "text read from the screen."
            ),
            criteria=item_criteria(screen, items),
        )
    if screen.offscreen:
        questions["offscreen"] = Choice(
            instructions=(
                "If activating a control that is not on screen is the right move, which control? "
                "These are real controls of the app, reachable without the mouse, but nothing on "
                "the capture points at them."
            ),
            criteria=offscreen_criteria(screen.offscreen),
        )
    answers = client.system_one(state=base_state(goal, screen, items, history), questions=questions).answers
    return Decision(kind=answers["kind"], item=answers.get("item"), site=answers["site"], offscreen=answers.get("offscreen"))


def verify_typed(client: TypeSafeClient | None, goal: str, field_before: Field, typed: str, field_after: Field | None) -> float:
    """Probability that the field now holds a sensible value for its purpose."""
    # 1. Try on-device SLM verification
    try:
        from .slm_decide import slm_available, slm_verify_typed
        if slm_available():
            return slm_verify_typed(goal, field_before, typed, field_after)
    except Exception:
        pass

    # 2. Fall back to cloud Noul or simple string match
    if client is None:
        if field_after and typed.strip().lower() in field_after.value.lower():
            return 1.0
        return 0.95

    state = {
        "goal": goal,
        "field": field_before.summary(),
        "text_typed": typed,
        "field_value_now": field_after.value[:300] if field_after else None,
        "field_still_focused": bool(
            field_after and field_after.role == field_before.role and field_after.label == field_before.label
        ),
    }
    question = Noul(
        instructions=(
            "Did the typing succeed: does the field now contain the typed text, and is that "
            "text a sensible value for what this field asks for, given the goal?"
        )
    )
    return client.system_one(state=state, questions={"ok": question}).answers["ok"].noul
