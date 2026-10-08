"""Shared fixtures and options for the mkapp test suite.

Options:
    --quick                 run only the tests marked `quick`
    --sign <identity>       also run a positive codesign test using this identity
    --notarize <profile>    also run a positive notarization test (requires --sign)

--sign needs a valid identity already in your keychain, without
it the positive signing test is skipped, since most dev/CI machines
have no real cert.

--notarize needs --sign plus a keychain profile stored, without
it the positive notarization test is skipped (it submits to Apple and can take minutes).
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MKAPP = REPO_ROOT / "mkapp.sh"
TUI_DIR = REPO_ROOT / "tui"
TUI_FILE = TUI_DIR / "mkapp_tui.py"
ICON_FILE = REPO_ROOT / "resources" / "sample-icon.png"
TERMINAL_FIXTURE = REPO_ROOT / "tests" / "terminal_test" / "app.py"
STDLIB_FIXTURE = REPO_ROOT / "tests" / "stdlib_test" / "app.py"
GUI_FIXTURE = REPO_ROOT / "tests" / "gui_test" / "app.py"

EXPECTED_OUTPUT = "hello from mkapp test"

PINNED_PYTHON = f"{sys.version_info.major}.{sys.version_info.minor}"
SCRIPT_PYTHON = "3.12"
PYTHON_310 = "3.10"

IS_MACOS = platform.system() == "Darwin"
HAS_UV = shutil.which("uv") is not None
HAS_PLUTIL = shutil.which("plutil") is not None
HAS_SIPS = shutil.which("sips") is not None

if str(TUI_DIR) not in sys.path:
    sys.path.insert(0, str(TUI_DIR))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--quick",
        action="store_true",
        default=False,
        help="run only the tests marked `quick`, skipping the PyInstaller builds",
    )
    parser.addoption(
        "--sign",
        action="store",
        default="",
        metavar="IDENTITY",
        help="also run a positive codesign test using this identity",
    )
    parser.addoption(
        "--notarize",
        action="store",
        default="",
        metavar="PROFILE",
        help="also run a positive notarization test using this profile (requires --sign)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "quick: a fast check")
    config.addinivalue_line("markers", "macos: requires macOS")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    skip_quick = pytest.mark.skip(reason="--quick: skipping build tests")
    skip_no_uv = pytest.mark.skip(reason="uv not available")
    skip_not_macos = pytest.mark.skip(reason="not macOS")
    quick = config.getoption("--quick")

    for item in items:
        if "quick" not in item.keywords:
            if quick:
                item.add_marker(skip_quick)
            elif not HAS_UV:
                item.add_marker(skip_no_uv)
        if "macos" in item.keywords and not IS_MACOS:
            item.add_marker(skip_not_macos)


def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(a) for a in args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        **kwargs,  # type: ignore[arg-type]
    )


def pin_python(folder: Path, version: str = PINNED_PYTHON) -> None:
    (folder / ".python-version").write_text(f"{version}\n", encoding="utf-8")


def run_mkapp(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return run(MKAPP, *args, **kwargs)


def plutil_extract(plist: Path, key: str) -> str:
    result = run("plutil", "-extract", key, "raw", plist)
    return result.stdout.strip() if result.returncode == 0 else ""


def expected_default_bundle_id(script_stem: str) -> str:
    user = run("id", "-un").stdout.strip()
    sanitized = re.sub(r"[^0-9A-Za-z]", "-", user)
    return f"com.{sanitized}.{script_stem}"


@pytest.fixture(scope="session")
def sign_identity(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.getoption("--sign"))


@pytest.fixture(scope="session")
def notarize_profile(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.getoption("--notarize"))


@pytest.fixture(scope="session")
def require_sign_identity(sign_identity: str) -> str:
    if not sign_identity:
        pytest.skip("no --sign <identity> passed")
    return sign_identity


@pytest.fixture(scope="session")
def require_notarize_profile(notarize_profile: str) -> str:
    if not notarize_profile:
        pytest.skip("no --notarize <profile> passed")
    return notarize_profile


@pytest.fixture(scope="session")
def temp_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("mkapp-test")
    pin_python(d)
    return d


@pytest.fixture(scope="session")
def valid_stub(temp_dir: Path) -> Path:
    stub = temp_dir / "stub.py"
    stub.write_text("pass\n", encoding="utf-8")
    return stub


@pytest.fixture(scope="session")
def build_dir(temp_dir: Path) -> Path:
    d = temp_dir / "build"
    d.mkdir()
    pin_python(d)
    return d


@pytest.fixture(scope="session")
def greeter(build_dir: Path) -> Path:
    script = build_dir / "greeter.py"
    script.write_text(
        f'if __name__ == "__main__":\n    print("{EXPECTED_OUTPUT}")\n',
        encoding="utf-8",
    )
    return script


@pytest.fixture(scope="session")
def greeter_bin(build_dir: Path) -> Path:
    return build_dir / "dist" / "greeter"


@pytest.fixture(scope="session")
def app_dir(build_dir: Path) -> Path:
    return build_dir / "dist" / "greeter.app"


@pytest.fixture(scope="session")
def app_bin(app_dir: Path) -> Path:
    return app_dir / "Contents" / "MacOS" / "greeter"


@pytest.fixture(scope="session")
def app_plist(app_dir: Path) -> Path:
    return app_dir / "Contents" / "Info.plist"


@pytest.fixture(scope="session")
def app_icns(app_dir: Path) -> Path:
    return app_dir / "Contents" / "Resources" / "greeter.icns"


@pytest.fixture(scope="session")
def dmg_path(build_dir: Path) -> Path:
    return build_dir / "dist" / "greeter.dmg"


@pytest.fixture(scope="session")
def no_arg_run() -> subprocess.CompletedProcess[str]:
    return run_mkapp()


@pytest.fixture(scope="session")
def missing_file_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp(temp_dir / "missing.py")


@pytest.fixture(scope="session")
def non_py_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    non_py = temp_dir / "not_python.txt"
    non_py.touch()
    return run_mkapp(non_py)


@pytest.fixture(scope="session")
def control_char_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    script = temp_dir / "a\x01b.py"
    script.write_text("pass\n", encoding="utf-8")
    return run_mkapp(script)


@pytest.fixture(scope="session")
def help_short_run() -> subprocess.CompletedProcess[str]:
    return run_mkapp("-h")


@pytest.fixture(scope="session")
def help_long_run() -> subprocess.CompletedProcess[str]:
    return run_mkapp("--help")


@pytest.fixture(scope="session")
def unknown_flag_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--not-a-real-flag", temp_dir / "missing.py")


@pytest.fixture(scope="session")
def unpinned_build_run(
    tmp_path_factory: pytest.TempPathFactory, valid_stub: Path
) -> subprocess.CompletedProcess[str]:
    mkapp_copy = tmp_path_factory.mktemp("mkapp-unpinned")
    shutil.copy2(MKAPP, mkapp_copy / "mkapp.sh")
    (mkapp_copy / "pyproject.toml").write_text(
        '[dependency-groups]\nbuild = [\n    "pyinstaller",\n'
        '    "pyinstaller-hooks-contrib==2026.8",\n]\n',
        encoding="utf-8",
    )
    return run(mkapp_copy / "mkapp.sh", valid_stub)


@pytest.fixture(scope="session")
def two_positional_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp(temp_dir / "a.py", temp_dir / "b.py")


@pytest.fixture(scope="session")
def missing_icon_run(
    temp_dir: Path, valid_stub: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--icon", temp_dir / "no-such-icon.png", valid_stub)


@pytest.fixture(scope="session")
def missing_icon_equals_run(
    temp_dir: Path, valid_stub: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp(f"--icon={temp_dir / 'no-such-icon.png'}", valid_stub)


@pytest.fixture(scope="session")
def missing_uv_run(valid_stub: Path) -> subprocess.CompletedProcess[str]:
    """mkapp with uv hidden behind a stripped PATH."""
    return run_mkapp(valid_stub, env={**os.environ, "PATH": "/usr/bin:/bin"})


@pytest.fixture(scope="session")
def broken_script_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    broken = temp_dir / "broken.py"
    broken.write_text("def broken(:\n    pass\n", encoding="utf-8")
    return run_mkapp(broken)


@pytest.fixture(scope="session")
def pyproject_only_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    d = temp_dir / "pyproject_only"
    d.mkdir()
    pin_python(d)
    script = d / "app.py"
    script.write_text('print("pyproject only")\n', encoding="utf-8")
    (d / "pyproject.toml").write_text(
        '[project]\nname = "app"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    return run_mkapp(script)


def _script_in(folder: Path, python_version_text: str | None) -> Path:
    folder.mkdir()
    if python_version_text is not None:
        (folder / ".python-version").write_text(python_version_text, encoding="utf-8")
    script = folder / "stub.py"
    script.write_text("pass\n", encoding="utf-8")
    return script


@pytest.fixture(scope="session")
def missing_python_version_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp(_script_in(temp_dir / "unpinned", None))


@pytest.fixture(scope="session")
def empty_python_version_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp(_script_in(temp_dir / "empty_pin", "# no version here\n\n"))


@pytest.fixture(scope="session")
def malformed_python_version_run(
    temp_dir: Path,
) -> subprocess.CompletedProcess[str]:
    return run_mkapp(_script_in(temp_dir / "malformed_pin", "latest\n"))


@pytest.fixture(scope="session")
def invalid_python_run(temp_dir: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp(_script_in(temp_dir / "bad_pin", "3.99\n"))


def _version_script_dir(folder: Path, version: str) -> Path:
    folder.mkdir()
    (folder / "version.py").write_text(
        "import sys\n\n"
        'if __name__ == "__main__":\n'
        '    print("python=%d.%d" % sys.version_info[:2])\n',
        encoding="utf-8",
    )
    pin_python(folder, version)
    return folder


@pytest.fixture(scope="session")
def python_version_dir(temp_dir: Path) -> Path:
    return _version_script_dir(temp_dir / "python_version", SCRIPT_PYTHON)


@pytest.fixture(scope="session")
def python_version_build(
    python_version_dir: Path,
) -> subprocess.CompletedProcess[str]:
    return run_mkapp(python_version_dir / "version.py")


@pytest.fixture(scope="session")
def python_version_output(
    python_version_build: subprocess.CompletedProcess[str], python_version_dir: Path
) -> str | None:
    binary = python_version_dir / "dist" / "version"
    if not os.access(binary, os.X_OK):
        return None
    return run(binary).stdout


@pytest.fixture(scope="session")
def python310_dir(temp_dir: Path) -> Path:
    return _version_script_dir(temp_dir / "python310", PYTHON_310)


@pytest.fixture(scope="session")
def python310_build(python310_dir: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp(python310_dir / "version.py")


@pytest.fixture(scope="session")
def python310_output(
    python310_build: subprocess.CompletedProcess[str], python310_dir: Path
) -> str | None:
    binary = python310_dir / "dist" / "version"
    if not os.access(binary, os.X_OK):
        return None
    return run(binary).stdout


@pytest.fixture(scope="session")
def dash_dir(temp_dir: Path) -> Path:
    d = temp_dir / "dash-named"
    d.mkdir()
    pin_python(d)
    (d / "-weird.py").write_text('print("dash ok")\n', encoding="utf-8")
    return d


@pytest.fixture(scope="session")
def dash_without_sep_run(dash_dir: Path) -> subprocess.CompletedProcess[str]:
    return run(MKAPP, "-weird.py", cwd=dash_dir)


@pytest.fixture(scope="session")
def dash_with_sep_run(dash_dir: Path) -> subprocess.CompletedProcess[str]:
    return run(MKAPP, "--", "-weird.py", cwd=dash_dir)


@pytest.fixture(scope="session")
def stdlib_build(greeter: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp(greeter)


@pytest.fixture(scope="session")
def existing_build_files_dir(temp_dir: Path) -> Path:
    d = temp_dir / "existing-build-files"
    (d / "build").mkdir(parents=True)
    pin_python(d)
    (d / "app.py").write_text('print("existing build files")\n', encoding="utf-8")
    (d / "build" / "keep.txt").write_text("keep\n", encoding="utf-8")
    (d / "app.spec").write_text("# spec file\n", encoding="utf-8")
    return d


@pytest.fixture(scope="session")
def existing_build_files_tmpdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("existing-build-files-tmpdir")


@pytest.fixture(scope="session")
def existing_build_files_build(
    existing_build_files_dir: Path, existing_build_files_tmpdir: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp(
        existing_build_files_dir / "app.py",
        env={**os.environ, "TMPDIR": str(existing_build_files_tmpdir)},
    )


@pytest.fixture(scope="session")
def ampersand_dir(temp_dir: Path) -> Path:
    d = temp_dir / "ampersand"
    d.mkdir()
    pin_python(d)
    (d / "a&b.py").write_text('print("ampersand ok")\n', encoding="utf-8")
    return d


@pytest.fixture(scope="session")
def ampersand_app_build(ampersand_dir: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--app", ampersand_dir / "a&b.py")


@pytest.fixture(scope="session")
def ampersand_plist(
    ampersand_app_build: subprocess.CompletedProcess[str], ampersand_dir: Path
) -> Path:
    return ampersand_dir / "dist" / "a&b.app" / "Contents" / "Info.plist"


@pytest.fixture(scope="session")
def ampersand_bundle_name(ampersand_plist: Path) -> str:
    return plutil_extract(ampersand_plist, "CFBundleName")


@pytest.fixture(scope="session")
def terminal_build() -> subprocess.CompletedProcess[str]:
    if not TERMINAL_FIXTURE.is_file():
        pytest.skip(f"{TERMINAL_FIXTURE} not found")
    return run_mkapp(TERMINAL_FIXTURE)


@pytest.fixture(scope="session")
def terminal_bin() -> Path:
    return TERMINAL_FIXTURE.parent / "dist" / "app"


@pytest.fixture(scope="session")
def stdlib_app_build() -> subprocess.CompletedProcess[str]:
    if not STDLIB_FIXTURE.is_file():
        pytest.skip(f"{STDLIB_FIXTURE} not found")
    return run_mkapp(STDLIB_FIXTURE)


@pytest.fixture(scope="session")
def stdlib_app_bin() -> Path:
    return STDLIB_FIXTURE.parent / "dist" / "app"


@pytest.fixture(scope="session")
def gui_build() -> subprocess.CompletedProcess[str]:
    if not GUI_FIXTURE.is_file():
        pytest.skip(f"{GUI_FIXTURE} not found")
    return run_mkapp(GUI_FIXTURE)


@pytest.fixture(scope="session")
def gui_bin() -> Path:
    return GUI_FIXTURE.parent / "dist" / "app"


@pytest.fixture(scope="session")
def require_icon_file() -> Path:
    if not ICON_FILE.is_file():
        pytest.skip(f"{ICON_FILE} not found")
    return ICON_FILE


@pytest.fixture(scope="session")
def terminal_app_build(
    terminal_build: subprocess.CompletedProcess[str], require_icon_file: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--app", "--icon", require_icon_file, TERMINAL_FIXTURE)


@pytest.fixture(scope="session")
def terminal_dmg_tmpdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("terminal-dmg-tmpdir")


@pytest.fixture(scope="session")
def terminal_dmg_build(
    terminal_app_build: subprocess.CompletedProcess[str],
    require_icon_file: Path,
    terminal_dmg_tmpdir: Path,
) -> subprocess.CompletedProcess[str]:
    return run_mkapp(
        "--dmg",
        "--icon",
        require_icon_file,
        TERMINAL_FIXTURE,
        env={**os.environ, "TMPDIR": str(terminal_dmg_tmpdir)},
    )


@pytest.fixture(scope="session")
def gui_app_build(
    gui_build: subprocess.CompletedProcess[str], require_icon_file: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--app", "--icon", require_icon_file, GUI_FIXTURE)


@pytest.fixture(scope="session")
def gui_dmg_build(
    gui_app_build: subprocess.CompletedProcess[str], require_icon_file: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--dmg", "--icon", require_icon_file, GUI_FIXTURE)


@pytest.fixture(scope="session")
def app_build(
    stdlib_build: subprocess.CompletedProcess[str], greeter: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--app", greeter)


@pytest.fixture(scope="session")
def app_run_output(
    app_build: subprocess.CompletedProcess[str], app_bin: Path
) -> str | None:
    if not os.access(app_bin, os.X_OK):
        return None
    return run(app_bin).stdout


@pytest.fixture(scope="session")
def short_a_build(
    app_run_output: str | None, greeter: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("-a", greeter)


@pytest.fixture(scope="session")
def short_d_build(
    short_a_build: subprocess.CompletedProcess[str], greeter: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("-d", greeter)


@pytest.fixture(scope="session")
def icns_fixture(
    short_d_build: subprocess.CompletedProcess[str], temp_dir: Path
) -> Path | None:
    if not HAS_SIPS or not ICON_FILE.is_file():
        return None
    out = temp_dir / "sample-icon.icns"
    result = run("sips", "-s", "format", "icns", ICON_FILE, "--out", out)
    return out if result.returncode == 0 and out.is_file() else None


@pytest.fixture(scope="session")
def icns_build(
    icns_fixture: Path | None, greeter: Path
) -> subprocess.CompletedProcess[str] | None:
    if icns_fixture is None:
        return None
    return run_mkapp("--app", "--icon", icns_fixture, greeter)


@pytest.fixture(scope="session")
def bad_icon_build(
    icns_build: subprocess.CompletedProcess[str] | None,
    temp_dir: Path,
    greeter: Path,
) -> subprocess.CompletedProcess[str]:
    not_image = temp_dir / "not-really-an-image.png"
    not_image.write_text("this is not image data\n", encoding="utf-8")
    return run_mkapp("--app", "--icon", not_image, greeter)


@pytest.fixture(scope="session")
def default_bundle_id(
    bad_icon_build: subprocess.CompletedProcess[str], app_plist: Path
) -> str:
    return plutil_extract(app_plist, "CFBundleIdentifier")


@pytest.fixture(scope="session")
def custom_bundle_id_build(
    default_bundle_id: str, greeter: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--app", "--bundle-id", "com.mkapptest.greeter", greeter)


@pytest.fixture(scope="session")
def custom_bundle_id(
    custom_bundle_id_build: subprocess.CompletedProcess[str], app_plist: Path
) -> str:
    return plutil_extract(app_plist, "CFBundleIdentifier")


@pytest.fixture(scope="session")
def equals_bundle_id_build(
    custom_bundle_id: str, greeter: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--app", "--bundle-id=com.mkapptest.equalsform", greeter)


@pytest.fixture(scope="session")
def equals_bundle_id(
    equals_bundle_id_build: subprocess.CompletedProcess[str], app_plist: Path
) -> str:
    return plutil_extract(app_plist, "CFBundleIdentifier")


@pytest.fixture(scope="session")
def invalid_bundle_id_run(greeter: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--bundle-id", "not_valid!!", greeter)


@pytest.fixture(scope="session")
def dmg_build(equals_bundle_id: str, greeter: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--dmg", greeter)


@pytest.fixture(scope="session")
def notarize_without_sign_run(greeter: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--notarize", "mkapp-test-profile", greeter)


@pytest.fixture(scope="session")
def notarize_without_sign_equals_run(
    greeter: Path,
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--notarize=mkapp-test-profile", greeter)


@pytest.fixture(scope="session")
def invalid_sign_run(greeter: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--sign", "mkapp-test: no such identity", greeter)


@pytest.fixture(scope="session")
def invalid_sign_equals_run(greeter: Path) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--sign=mkapp-test: no such identity", greeter)


@pytest.fixture(scope="session")
def real_sign_build(
    dmg_build: subprocess.CompletedProcess[str],
    require_sign_identity: str,
    greeter: Path,
) -> subprocess.CompletedProcess[str]:
    return run_mkapp("--dmg", "--sign", require_sign_identity, greeter)


@pytest.fixture(scope="session")
def combined_build(
    real_sign_build: subprocess.CompletedProcess[str],
    require_sign_identity: str,
    require_icon_file: Path,
    greeter: Path,
) -> subprocess.CompletedProcess[str]:
    """Every flag together in one invocation."""
    return run_mkapp(
        "--dmg",
        "--icon",
        require_icon_file,
        "--bundle-id",
        "com.mkapptest.combined",
        "--sign",
        require_sign_identity,
        greeter,
    )


@pytest.fixture(scope="session")
def combined_bundle_id(
    combined_build: subprocess.CompletedProcess[str], app_plist: Path
) -> str:
    return plutil_extract(app_plist, "CFBundleIdentifier")


@pytest.fixture(scope="session")
def invalid_notarize_build(
    combined_bundle_id: str, require_sign_identity: str, greeter: Path
) -> subprocess.CompletedProcess[str]:
    return run_mkapp(
        "--dmg",
        "--sign",
        require_sign_identity,
        "--notarize",
        "mkapp-test-no-such-profile",
        greeter,
    )


@pytest.fixture(scope="session")
def real_notarize_build(
    invalid_notarize_build: subprocess.CompletedProcess[str],
    require_sign_identity: str,
    require_notarize_profile: str,
    greeter: Path,
) -> subprocess.CompletedProcess[str]:
    return run_mkapp(
        "--dmg",
        "--sign",
        require_sign_identity,
        "--notarize",
        require_notarize_profile,
        greeter,
    )
