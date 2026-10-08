"""Interactive TUI front-end for mkapp.

Launched when ``mkapp.sh`` is run with no arguments. It walks the
user through the same options the command line accepts, then hands the choices
back to ``mkapp.sh``.

The resulting build output is identical to running the script directly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Input, Label, Static

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    BANNER = (REPO_ROOT / "banner.txt").read_text(encoding="utf-8").rstrip("\n")
except OSError:
    BANNER = "mkapp"

# Column 27 is where the icon ends and the wordmark
# begins on every line in the banner
_ICON_WIDTH = 27


def _colorize_banner(banner: str) -> Text:
    text = Text()
    for i, line in enumerate(banner.split("\n")):
        if i:
            text.append("\n")
        text.append(line[:_ICON_WIDTH], style="bold blue")
        text.append(line[_ICON_WIDTH:], style="bold cyan")
    return text


BANNER_TEXT = _colorize_banner(BANNER)


class MkappTUI(App[list[str]]):
    """A simple form that gathers mkapp options and returns them as CLI args."""

    TITLE = "mkapp"

    CSS = """
    Screen {
        align: center top;
    }
    #banner {
        width: auto;
        height: auto;
        margin: 1 0 0 0;
    }
    #subtitle {
        width: auto;
        height: auto;
        color: $text-muted;
        margin: 0 0 0 2;
    }
    #form {
        width: 80%;
        max-width: 72;
        height: auto;
        padding: 0 1;
    }
    Label {
        margin: 1 0 0 0;
        text-style: bold;
    }
    .hint {
        color: $text-muted;
    }
    #error {
        color: red;
        height: auto;
    }
    #buttons {
        height: auto;
        margin: 1 0 0 0;
    }
    #buttons Button {
        margin: 0 2 0 0;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(BANNER_TEXT, id="banner")
        yield Static("Python script → standalone executable", id="subtitle")
        with VerticalScroll(id="form"):
            yield Label("Step 1: Python script to build (required)")
            yield Static(
                "The script's parent folder should have a .python-version file "
                "and an optional requirements.txt",
                classes="hint",
            )
            yield Input(placeholder="path/to/script.py", id="script")

            yield Label("Step 2: macOS output (optional)")
            yield Checkbox("Wrap the binary in a .app bundle", id="app", compact=True)
            yield Checkbox(
                "Package a shareable .dmg (implies .app)", id="dmg", compact=True
            )

            yield Label("Step 3: Icon for the .app (optional)")
            yield Static(
                ".icns, or any image sips can convert (e.g. a 512x512 png)",
                classes="hint",
            )
            yield Input(placeholder="path/to/icon.png", id="icon")

            yield Label("Step 4: Bundle identifier (optional)")
            yield Static(
                "Reverse-DNS style, e.g. com.janedoe.myscript (default is derived from your macOS account)",
                classes="hint",
            )
            yield Input(placeholder="com.janedoe.myscript", id="bundle_id")

            yield Label("Step 5: Code-signing identity (optional)")
            yield Static(
                "Sign the .app/.dmg for distribution. Needs an Apple Developer identity",
                classes="hint",
            )
            yield Input(
                placeholder="Developer ID Application: Jane Doe (TEAMID)", id="sign"
            )

            yield Label("Step 6: Notarization profile (optional)")
            yield Static(
                "Notarize the .dmg with Apple and staple the ticket so Gatekeeper never warns "
                "recipients. Implies .dmg and requires signing. Set up a profile before using it.",
                classes="hint",
            )
            yield Input(placeholder="my-notary-profile", id="notarize")

            yield Static("", id="error")

            with Horizontal(id="buttons"):
                yield Button("Build", variant="success", id="build", compact=True)
                yield Button("Quit", variant="error", id="quit", compact=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#script", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.screen.focus_next()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.exit(None)
        elif event.button.id == "build":
            self._submit()

    def _submit(self) -> None:
        error = self.query_one("#error", Static)
        script = self.query_one("#script", Input).value.strip()

        if not script:
            error.update("A script path is required.")
            self.query_one("#script", Input).focus()
            return

        args: list[str] = []
        if self.query_one("#app", Checkbox).value:
            args.append("--app")
        if self.query_one("#dmg", Checkbox).value:
            args.append("--dmg")

        icon = self.query_one("#icon", Input).value.strip()
        if icon:
            args += ["--icon", os.path.expanduser(icon)]

        bundle_id = self.query_one("#bundle_id", Input).value.strip()
        if bundle_id:
            args += ["--bundle-id", bundle_id]

        sign = self.query_one("#sign", Input).value.strip()
        if sign:
            args += ["--sign", sign]

        notarize = self.query_one("#notarize", Input).value.strip()
        if notarize:
            args += ["--notarize", notarize]

        args += ["--", os.path.expanduser(script)]
        self.exit(args)


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "error: launch the TUI by running mkapp.sh with no arguments",
            file=sys.stderr,
        )
        return 2

    args = MkappTUI().run()
    if args is None:
        print("Cancelled. Nothing was built.")
        return 0

    Path(sys.argv[1]).write_text("".join(f"{a}\n" for a in args), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
