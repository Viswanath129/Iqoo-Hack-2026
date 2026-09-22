"""Command-line entry points: `clicker` and `clicker-inspect`."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from . import config
from . import platform_adapter as macos
from .actions import Context
from .perception import capture, perceive
from .report import annotate, ax_count, render_payload
from .runner import RunConfig, run
from .timing import format_timing
from .writer import make_writer

DOTENV = Path.cwd() / ".env"


def _prepare(require_key: bool = True) -> None:
    config.load_dotenv(DOTENV)
    if require_key and not os.environ.get("TYPESAFE_API_KEY"):
        print("[NOTICE] TYPESAFE_API_KEY is not set: running in local on-device mode (NPU/heuristics).")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="clicker",
        description="Drive this computer toward a goal: screen OCR, NPU acceleration, deterministic actions, and speech.",
    )
    parser.add_argument("goal", nargs="?", default="", help="what you want done on this computer (or use --voice)")
    parser.add_argument("--act", action="store_true", help="actually click and type (default: dry run, one step)")
    parser.add_argument("--steps", type=int, default=config.DEFAULT_STEPS, help="max actions before stopping")
    parser.add_argument("--min-confidence", type=float, default=config.DEFAULT_MIN_CONFIDENCE, help="stop below this confidence")
    parser.add_argument("--delay", type=float, default=config.DEFAULT_DELAY, help="seconds to wait after each action")
    parser.add_argument("--out", type=Path, default=Path("runs") / time.strftime("%Y%m%d-%H%M%S"), help="run folder")
    parser.add_argument("--image", type=Path, help="replay a saved capture instead of the live screen (never acts)")
    parser.add_argument("--app", help="frontmost app to report during replay")
    parser.add_argument("--url", help="browser URL to report during replay")
    parser.add_argument("--voice", action="store_true", help="listen to your voice (microphone) for the goal")
    parser.add_argument("--speak", action="store_true", help="speak actions and results aloud via speech synthesis")
    parser.add_argument("--local", action="store_true", help="force local on-device decision engine (no cloud API)")
    parser.add_argument("--target", choices=["android", "windows", "macos"], default=None,
                        help="target platform (default: auto-detect). Sets ARGUS_TARGET env var.")
    parser.add_argument("--model", choices=["slm", "cloud", "local"], default=None,
                        help="decision engine: slm (on-device NPU), cloud (TypeSafe JEV), local (keyword heuristics)")
    args = parser.parse_args(argv)

    # Set target platform before any platform_adapter imports
    if args.target:
        os.environ["ARGUS_TARGET"] = args.target
    if args.model == "local":
        args.local = True

    from . import speech
    from . import whisper_npu

    goal = args.goal.strip()
    if args.voice or not goal:
        # Pre-warm Qualcomm Hexagon NPU Whisper model before activating mic
        print("[NPU] Initializing Snapdragon Hexagon NPU Whisper...", flush=True)
        whisper_npu.warmup_npu()

        if args.voice:
            speech.speak("I am listening. What is your goal?", wait=True)
            goal = speech.listen(prompt="Speak your goal now...")
        if not goal:
            goal = speech.listen(prompt="Please enter or speak your goal:")
        if not goal:
            sys.exit("No goal provided. Exiting.")

    _prepare(require_key=not args.local and not args.image and bool(os.environ.get("TYPESAFE_API_KEY")))
    if args.act and not macos.accessibility_trusted():
        sys.exit("this terminal lacks Accessibility permission; grant it in System Settings > Privacy & Security")
    writer = make_writer()

    cfg = RunConfig(
        goal=goal,
        out=args.out,
        act=args.act,
        steps=args.steps,
        min_confidence=args.min_confidence,
        delay=args.delay,
        image=args.image,
        app=args.app,
        url=args.url,
        local=args.local,
        speak=args.speak,
    )

    def ctx_factory(typesafe, history):
        return Context(
            goal=goal,
            browser=config.browser(),
            email=config.email(),
            typesafe=typesafe,
            writer=writer,
            history=history,
        )

    state = run(cfg, ctx_factory)
    if state.outcome.startswith("aborted"):
        sys.exit(130)


def inspect(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="clicker-inspect",
        description="Count down, capture the screen, and show exactly what the clicker would send to TypeSafe.",
    )
    parser.add_argument("goal", nargs="?", default="(no goal given)")
    parser.add_argument("--countdown", type=int, default=3)
    parser.add_argument("--no-open", action="store_true", help="write files without opening them")
    parser.add_argument("--out", type=Path, default=Path("inspections") / time.strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args(argv)
    config.load_dotenv(DOTENV)
    args.out.mkdir(parents=True, exist_ok=True)

    for n in range(args.countdown, 0, -1):
        print(f"{n}...", end=" ", flush=True)
        time.sleep(1)
    print("capture")

    browser = config.browser()
    timing: dict[str, float] = {}
    screen = capture(browser=browser, timing=timing)
    items = perceive(screen, config.MAX_OPTIONS, args.goal, timing)
    annotated = args.out / "annotated.png"
    text = args.out / "state.txt"
    screen.image.save(args.out / "raw.png")
    annotate(screen, items, chosen="", out=annotated)
    text.write_text(render_payload(args.goal, screen, items, [], browser, config.email()))

    print(
        f"app={screen.app!r} url={screen.url!r} items={len(items)} ax={ax_count(items)} "
        f"offscreen={len(screen.offscreen)} field={screen.field.role if screen.field else None}"
    )
    print(format_timing(timing))
    print(f"  {annotated}\n  {text}")
    if not args.no_open:
        if sys.platform == "win32":
            os.startfile(str(annotated))
            os.startfile(str(text))
        else:
            subprocess.run(["open", str(annotated)], check=False)
            subprocess.run(["open", "-t", str(text)], check=False)


if __name__ == "__main__":
    main()

