"""Automated tests for mkapp.sh and the TUI.

Quick validation tests and error-path checks are marked `quick`. --quick runs those
and skips everything else, including the end-to-end PyInstaller builds that
produce and execute binaries. See conftest.py for the options and fixtures.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import (
    EXPECTED_OUTPUT,
    HAS_PLUTIL,
    MKAPP,
    PINNED_PYTHON,
    PYTHON_310,
    REPO_ROOT,
    SCRIPT_PYTHON,
    STDLIB_FIXTURE,
    TUI_FILE,
    expected_default_bundle_id,
    run,
)


@pytest.mark.quick
def test_suite_runs_on_a_supported_python() -> None:
    floor = re.search(
        r">=(\d+\.\d+)", (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )[1]
    assert tuple(sys.version_info[:2]) >= tuple(map(int, floor.split(".")))


@pytest.mark.quick
def test_mkapp_passes_bash_syntax_check() -> None:
    result = run("bash", "-n", MKAPP)
    assert result.returncode == 0, result.stdout


@pytest.mark.quick
def test_no_argument_exits_nonzero(
    no_arg_run: subprocess.CompletedProcess[str],
) -> None:
    assert no_arg_run.returncode != 0


@pytest.mark.quick
def test_no_argument_error_mentions_usage(
    no_arg_run: subprocess.CompletedProcess[str],
) -> None:
    assert "Usage:" in no_arg_run.stdout


@pytest.mark.quick
def test_nonexistent_file_exits_nonzero(
    missing_file_run: subprocess.CompletedProcess[str],
) -> None:
    assert missing_file_run.returncode != 0


@pytest.mark.quick
def test_nonexistent_file_error_mentions_the_path(
    missing_file_run: subprocess.CompletedProcess[str],
) -> None:
    assert "does not exist" in missing_file_run.stdout


@pytest.mark.quick
def test_non_py_file_exits_nonzero(
    non_py_run: subprocess.CompletedProcess[str],
) -> None:
    assert non_py_run.returncode != 0


@pytest.mark.quick
def test_non_py_error_mentions_python_file(
    non_py_run: subprocess.CompletedProcess[str],
) -> None:
    assert "not a python file" in non_py_run.stdout


@pytest.mark.quick
def test_control_char_in_script_name_fails_cleanly(
    control_char_run: subprocess.CompletedProcess[str],
) -> None:
    assert control_char_run.returncode != 0


@pytest.mark.quick
def test_control_char_in_script_name_error_says_so(
    control_char_run: subprocess.CompletedProcess[str],
) -> None:
    assert "contains control characters" in control_char_run.stdout


@pytest.mark.quick
def test_startup_shows_the_mkapp_ascii_banner(
    non_py_run: subprocess.CompletedProcess[str],
) -> None:
    assert "|_| |_| |_|" in non_py_run.stdout


@pytest.mark.quick
def test_h_shows_help_and_exits_zero(
    help_short_run: subprocess.CompletedProcess[str],
) -> None:
    assert help_short_run.returncode == 0, help_short_run.stdout


@pytest.mark.quick
def test_h_output_shows_usage(
    help_short_run: subprocess.CompletedProcess[str],
) -> None:
    assert "Usage:" in help_short_run.stdout


@pytest.mark.quick
def test_help_shows_help_and_exits_zero(
    help_long_run: subprocess.CompletedProcess[str],
) -> None:
    assert help_long_run.returncode == 0, help_long_run.stdout


@pytest.mark.quick
def test_help_output_documents_bundle_id(
    help_long_run: subprocess.CompletedProcess[str],
) -> None:
    assert "--bundle-id" in help_long_run.stdout


@pytest.mark.quick
def test_help_output_documents_python_version_file(
    help_long_run: subprocess.CompletedProcess[str],
) -> None:
    assert ".python-version" in help_long_run.stdout


@pytest.mark.quick
def test_missing_python_version_fails_cleanly(
    missing_python_version_run: subprocess.CompletedProcess[str],
) -> None:
    assert missing_python_version_run.returncode != 0


@pytest.mark.quick
def test_missing_python_version_error_names_the_script(
    missing_python_version_run: subprocess.CompletedProcess[str],
) -> None:
    out = missing_python_version_run.stdout
    assert 'No .python-version file found for "stub.py"' in out
    assert "Create one specifying the python version required" in out


@pytest.mark.quick
def test_python_version_file_without_a_version_fails_cleanly(
    empty_python_version_run: subprocess.CompletedProcess[str],
) -> None:
    assert empty_python_version_run.returncode != 0


@pytest.mark.quick
def test_python_version_file_without_a_version_error_says_so(
    empty_python_version_run: subprocess.CompletedProcess[str],
) -> None:
    assert "has no python version in it" in empty_python_version_run.stdout


def test_malformed_python_version_fails_cleanly(
    malformed_python_version_run: subprocess.CompletedProcess[str],
) -> None:
    assert malformed_python_version_run.returncode != 0


def test_malformed_python_version_error_names_the_bad_value(
    malformed_python_version_run: subprocess.CompletedProcess[str],
) -> None:
    out = malformed_python_version_run.stdout
    assert '"latest" in' in out
    assert "can't be installed by uv" in out


@pytest.mark.quick
def test_unknown_flag_fails_cleanly(
    unknown_flag_run: subprocess.CompletedProcess[str],
) -> None:
    assert unknown_flag_run.returncode != 0


@pytest.mark.quick
def test_unknown_flag_error_names_the_flag(
    unknown_flag_run: subprocess.CompletedProcess[str],
) -> None:
    assert "Unknown option: --not-a-real-flag" in unknown_flag_run.stdout


@pytest.mark.quick
def test_pyproject_pins_exact_pyinstaller_versions() -> None:
    with (REPO_ROOT / "pyproject.toml").open("rb") as f:
        build = tomllib.load(f)["dependency-groups"]["build"]
    for name in ("pyinstaller", "pyinstaller-hooks-contrib"):
        assert any(re.fullmatch(rf"{name}==\d[\w.]*", req) for req in build), name


@pytest.mark.quick
def test_unpinned_pyinstaller_fails_cleanly(
    unpinned_build_run: subprocess.CompletedProcess[str],
) -> None:
    assert unpinned_build_run.returncode != 0


@pytest.mark.quick
def test_unpinned_pyinstaller_error_names_the_package(
    unpinned_build_run: subprocess.CompletedProcess[str],
) -> None:
    assert "no pinned version for pyinstaller in" in unpinned_build_run.stdout


@pytest.mark.quick
def test_two_positional_script_paths_fails_cleanly(
    two_positional_run: subprocess.CompletedProcess[str],
) -> None:
    assert two_positional_run.returncode != 0


@pytest.mark.quick
def test_two_positional_error_mentions_exactly_one_script(
    two_positional_run: subprocess.CompletedProcess[str],
) -> None:
    assert "expected exactly one script path" in two_positional_run.stdout


@pytest.mark.quick
def test_missing_icon_fails_validation(
    missing_icon_run: subprocess.CompletedProcess[str],
) -> None:
    assert missing_icon_run.returncode != 0


@pytest.mark.quick
def test_missing_icon_error_mentions_the_icon_file(
    missing_icon_run: subprocess.CompletedProcess[str],
) -> None:
    assert "Icon file" in missing_icon_run.stdout


@pytest.mark.quick
def test_missing_icon_equals_form_fails_the_same_way(
    missing_icon_equals_run: subprocess.CompletedProcess[str],
) -> None:
    assert missing_icon_equals_run.returncode != 0


@pytest.mark.quick
def test_missing_icon_equals_form_error_mentions_the_icon_file(
    missing_icon_equals_run: subprocess.CompletedProcess[str],
) -> None:
    assert "Icon file" in missing_icon_equals_run.stdout


def test_missing_uv_fails_cleanly(
    missing_uv_run: subprocess.CompletedProcess[str],
) -> None:
    assert missing_uv_run.returncode != 0


def test_missing_uv_error_mentions_installing_uv(
    missing_uv_run: subprocess.CompletedProcess[str],
) -> None:
    assert "uv is not installed" in missing_uv_run.stdout


def test_unavailable_python_fails_cleanly(
    invalid_python_run: subprocess.CompletedProcess[str],
) -> None:
    assert invalid_python_run.returncode != 0


def test_unavailable_python_error_names_the_version(
    invalid_python_run: subprocess.CompletedProcess[str],
) -> None:
    assert '"3.99" in' in invalid_python_run.stdout
    assert "can't be installed by uv" in invalid_python_run.stdout


def test_unavailable_python_fails_before_building(
    invalid_python_run: subprocess.CompletedProcess[str],
) -> None:
    assert "Building..." not in invalid_python_run.stdout


def test_python_version_build_succeeds(
    python_version_build: subprocess.CompletedProcess[str],
) -> None:
    assert python_version_build.returncode == 0, python_version_build.stdout


def test_python_version_build_reports_the_version(
    python_version_build: subprocess.CompletedProcess[str],
) -> None:
    assert (
        f"Using Python {SCRIPT_PYTHON} from .python-version"
        in python_version_build.stdout
    )


def test_binary_embeds_the_python_from_python_version(
    python_version_output: str | None,
) -> None:
    if python_version_output is None:
        pytest.skip("binary missing")
    assert f"python={SCRIPT_PYTHON}" in python_version_output


def test_python310_build_succeeds(
    python310_build: subprocess.CompletedProcess[str],
) -> None:
    assert python310_build.returncode == 0, python310_build.stdout


def test_python310_build_reports_the_version(
    python310_build: subprocess.CompletedProcess[str],
) -> None:
    assert f"Using Python {PYTHON_310} from .python-version" in python310_build.stdout


def test_python310_binary_runs_on_310_not_mkapps_python(
    python310_output: str | None,
) -> None:
    if python310_output is None:
        pytest.skip("binary missing")
    assert f"python={PYTHON_310}" in python310_output
    assert f"python={PINNED_PYTHON}" not in python310_output


def test_script_with_a_syntax_error_fails_the_build(
    broken_script_run: subprocess.CompletedProcess[str],
) -> None:
    assert broken_script_run.returncode != 0


def test_pyproject_only_fixture_still_builds(
    pyproject_only_run: subprocess.CompletedProcess[str],
) -> None:
    assert pyproject_only_run.returncode == 0, pyproject_only_run.stdout


def test_pyproject_only_build_notes_requirements_missing(
    pyproject_only_run: subprocess.CompletedProcess[str],
) -> None:
    assert "found pyproject.toml but no requirements.txt" in pyproject_only_run.stdout


def test_dash_prefixed_path_without_separator_is_rejected(
    dash_without_sep_run: subprocess.CompletedProcess[str],
) -> None:
    assert dash_without_sep_run.returncode != 0


def test_dash_prefixed_path_error_mentions_unknown_option(
    dash_without_sep_run: subprocess.CompletedProcess[str],
) -> None:
    assert "Unknown option" in dash_without_sep_run.stdout


def test_separator_allows_a_dash_prefixed_script_path(
    dash_with_sep_run: subprocess.CompletedProcess[str],
) -> None:
    assert dash_with_sep_run.returncode == 0, dash_with_sep_run.stdout


def test_stdlib_fixture_builds_successfully(
    stdlib_build: subprocess.CompletedProcess[str],
) -> None:
    assert stdlib_build.returncode == 0, stdlib_build.stdout


def test_produced_binary_exists_and_is_executable(
    stdlib_build: subprocess.CompletedProcess[str], greeter_bin: Path
) -> None:
    assert os.access(greeter_bin, os.X_OK), f"not executable: {greeter_bin}"


def test_binary_prints_the_expected_output(
    stdlib_build: subprocess.CompletedProcess[str], greeter_bin: Path
) -> None:
    if not os.access(greeter_bin, os.X_OK):
        pytest.skip("binary missing")
    assert EXPECTED_OUTPUT in run(greeter_bin).stdout


def test_no_build_dir_left_next_to_script(
    stdlib_build: subprocess.CompletedProcess[str], build_dir: Path
) -> None:
    assert not (build_dir / "build").exists()


def test_no_spec_file_left_next_to_script(
    stdlib_build: subprocess.CompletedProcess[str], build_dir: Path
) -> None:
    assert not (build_dir / "greeter.spec").exists()


def test_build_with_existing_build_files_succeeds(
    existing_build_files_build: subprocess.CompletedProcess[str],
) -> None:
    assert existing_build_files_build.returncode == 0


def test_build_keeps_existing_build_dir(
    existing_build_files_build: subprocess.CompletedProcess[str],
    existing_build_files_dir: Path,
) -> None:
    keep = existing_build_files_dir / "build" / "keep.txt"
    assert keep.read_text(encoding="utf-8") == "keep\n"


def test_build_keeps_existing_spec_file(
    existing_build_files_build: subprocess.CompletedProcess[str],
    existing_build_files_dir: Path,
) -> None:
    spec = existing_build_files_dir / "app.spec"
    assert spec.read_text(encoding="utf-8") == "# spec file\n"


def test_build_removes_its_work_folder(
    existing_build_files_build: subprocess.CompletedProcess[str],
    existing_build_files_tmpdir: Path,
) -> None:
    assert not list(existing_build_files_tmpdir.glob("mkapp-build.*"))


def test_no_virtualenv_left_behind(
    stdlib_build: subprocess.CompletedProcess[str], build_dir: Path
) -> None:
    """uv's ephemeral env means there is never a venv or lockfile to clean up."""
    assert not (build_dir / ".venv").exists()


def test_terminal_fixture_builds_successfully(
    terminal_build: subprocess.CompletedProcess[str],
) -> None:
    assert terminal_build.returncode == 0, terminal_build.stdout


def test_terminal_dist_app_produced(
    terminal_build: subprocess.CompletedProcess[str], terminal_bin: Path
) -> None:
    assert os.access(terminal_bin, os.X_OK), f"not executable: {terminal_bin}"


def test_terminal_prints_countdown(
    terminal_build: subprocess.CompletedProcess[str], terminal_bin: Path
) -> None:
    if not os.access(terminal_bin, os.X_OK):
        pytest.skip("binary missing")
    assert "Countdown 10..." in run(terminal_bin).stdout


def test_terminal_prints_response_payload(
    terminal_build: subprocess.CompletedProcess[str], terminal_bin: Path
) -> None:
    if not os.access(terminal_bin, os.X_OK):
        pytest.skip("binary missing")
    assert "Response payload:" in run(terminal_bin).stdout


@pytest.mark.macos
def test_terminal_app_with_icon_builds(
    terminal_app_build: subprocess.CompletedProcess[str],
) -> None:
    assert terminal_app_build.returncode == 0, terminal_app_build.stdout


@pytest.mark.macos
def test_terminal_app_produced(
    terminal_app_build: subprocess.CompletedProcess[str], terminal_bin: Path
) -> None:
    app_bin = terminal_bin.parent / "app.app" / "Contents" / "MacOS" / "app"
    assert os.access(app_bin, os.X_OK), f"not executable: {app_bin}"


@pytest.mark.macos
def test_terminal_app_has_icon(
    terminal_app_build: subprocess.CompletedProcess[str], terminal_bin: Path
) -> None:
    icns = terminal_bin.parent / "app.app" / "Contents" / "Resources" / "app.icns"
    assert icns.is_file(), f"no .icns at {icns}"


@pytest.mark.macos
def test_terminal_dmg_with_icon_builds(
    terminal_dmg_build: subprocess.CompletedProcess[str],
) -> None:
    assert terminal_dmg_build.returncode == 0, terminal_dmg_build.stdout


@pytest.mark.macos
def test_terminal_dmg_build_leaves_no_temp_files(
    terminal_dmg_build: subprocess.CompletedProcess[str], terminal_dmg_tmpdir: Path
) -> None:
    assert not list(terminal_dmg_tmpdir.glob("mkapp-*"))


@pytest.mark.macos
def test_terminal_dmg_produced(
    terminal_dmg_build: subprocess.CompletedProcess[str], terminal_bin: Path
) -> None:
    dmg = terminal_bin.parent / "app.dmg"
    assert dmg.is_file(), f"no file at {dmg}"


@pytest.mark.macos
def test_terminal_dmg_passes_hdiutil_verify(
    terminal_dmg_build: subprocess.CompletedProcess[str], terminal_bin: Path
) -> None:
    dmg = terminal_bin.parent / "app.dmg"
    if not dmg.is_file():
        pytest.skip("dmg missing")
    result = run("hdiutil", "verify", dmg)
    assert result.returncode == 0, result.stdout


@pytest.mark.quick
def test_stdlib_fixture_has_no_requirements_txt() -> None:
    assert not (STDLIB_FIXTURE.parent / "requirements.txt").exists()


def test_stdlib_app_fixture_builds_successfully(
    stdlib_app_build: subprocess.CompletedProcess[str],
) -> None:
    assert stdlib_app_build.returncode == 0, stdlib_app_build.stdout


def test_stdlib_app_dist_app_produced(
    stdlib_app_build: subprocess.CompletedProcess[str], stdlib_app_bin: Path
) -> None:
    assert os.access(stdlib_app_bin, os.X_OK), f"not executable: {stdlib_app_bin}"


def test_stdlib_app_prints_hello_world(
    stdlib_app_build: subprocess.CompletedProcess[str], stdlib_app_bin: Path
) -> None:
    if not os.access(stdlib_app_bin, os.X_OK):
        pytest.skip("binary missing")
    assert "Hello World!" in run(stdlib_app_bin).stdout


def test_stdlib_app_prints_the_utc_time_after_hello_world(
    stdlib_app_build: subprocess.CompletedProcess[str], stdlib_app_bin: Path
) -> None:
    if not os.access(stdlib_app_bin, os.X_OK):
        pytest.skip("binary missing")
    lines = run(stdlib_app_bin).stdout.splitlines()
    assert lines[0] == "Hello World!"
    printed = datetime.strptime(
        lines[1], "Current time: %Y-%m-%d %H:%M:%S UTC"
    ).replace(tzinfo=UTC)
    assert abs((datetime.now(UTC) - printed).total_seconds()) < 300


def test_gui_fixture_builds_successfully(
    gui_build: subprocess.CompletedProcess[str],
) -> None:
    assert gui_build.returncode == 0, gui_build.stdout


def test_gui_dist_app_produced(
    gui_build: subprocess.CompletedProcess[str], gui_bin: Path
) -> None:
    assert os.access(gui_bin, os.X_OK), f"not executable: {gui_bin}"


@pytest.mark.macos
def test_gui_app_with_icon_builds(
    gui_app_build: subprocess.CompletedProcess[str],
) -> None:
    assert gui_app_build.returncode == 0, gui_app_build.stdout


@pytest.mark.macos
def test_gui_app_produced(
    gui_app_build: subprocess.CompletedProcess[str], gui_bin: Path
) -> None:
    app_bin = gui_bin.parent / "app.app" / "Contents" / "MacOS" / "app"
    assert os.access(app_bin, os.X_OK), f"not executable: {app_bin}"


@pytest.mark.macos
def test_gui_app_has_icon(
    gui_app_build: subprocess.CompletedProcess[str], gui_bin: Path
) -> None:
    icns = gui_bin.parent / "app.app" / "Contents" / "Resources" / "app.icns"
    assert icns.is_file(), f"no .icns at {icns}"


@pytest.mark.macos
def test_app_with_ampersand_in_name_builds(
    ampersand_app_build: subprocess.CompletedProcess[str],
) -> None:
    assert ampersand_app_build.returncode == 0, ampersand_app_build.stdout


@pytest.mark.macos
def test_app_with_ampersand_in_name_has_a_valid_plist(
    ampersand_plist: Path,
) -> None:
    if not HAS_PLUTIL:
        pytest.skip("plutil not available")
    result = run("plutil", "-lint", ampersand_plist)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_app_with_ampersand_in_name_keeps_the_name(
    ampersand_bundle_name: str,
) -> None:
    assert ampersand_bundle_name == "a&b"


@pytest.mark.macos
def test_gui_dmg_with_icon_builds(
    gui_dmg_build: subprocess.CompletedProcess[str],
) -> None:
    assert gui_dmg_build.returncode == 0, gui_dmg_build.stdout


@pytest.mark.macos
def test_gui_dmg_produced(
    gui_dmg_build: subprocess.CompletedProcess[str], gui_bin: Path
) -> None:
    dmg = gui_bin.parent / "app.dmg"
    assert dmg.is_file(), f"no file at {dmg}"


@pytest.mark.macos
def test_gui_dmg_passes_hdiutil_verify(
    gui_dmg_build: subprocess.CompletedProcess[str], gui_bin: Path
) -> None:
    dmg = gui_bin.parent / "app.dmg"
    if not dmg.is_file():
        pytest.skip("dmg missing")
    result = run("hdiutil", "verify", dmg)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_build_with_app_succeeds(
    app_build: subprocess.CompletedProcess[str],
) -> None:
    assert app_build.returncode == 0, app_build.stdout


@pytest.mark.macos
def test_app_embeds_an_executable_in_contents_macos(
    app_build: subprocess.CompletedProcess[str], app_bin: Path
) -> None:
    assert os.access(app_bin, os.X_OK), f"not executable: {app_bin}"


@pytest.mark.macos
def test_info_plist_is_valid(
    app_build: subprocess.CompletedProcess[str], app_plist: Path
) -> None:
    if not app_plist.is_file() or not HAS_PLUTIL:
        pytest.skip("missing plist or plutil")
    result = run("plutil", "-lint", app_plist)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_app_embedded_binary_runs(app_run_output: str | None) -> None:
    if app_run_output is None:
        pytest.skip("binary missing")
    assert EXPECTED_OUTPUT in app_run_output


@pytest.mark.macos
def test_short_a_builds_the_app(
    short_a_build: subprocess.CompletedProcess[str],
) -> None:
    assert short_a_build.returncode == 0, short_a_build.stdout


@pytest.mark.macos
def test_short_a_produced_a_working_app_binary(
    short_a_build: subprocess.CompletedProcess[str], app_bin: Path
) -> None:
    assert os.access(app_bin, os.X_OK), f"not executable: {app_bin}"


@pytest.mark.macos
def test_short_d_builds_the_dmg(
    short_d_build: subprocess.CompletedProcess[str],
) -> None:
    assert short_d_build.returncode == 0, short_d_build.stdout


@pytest.mark.macos
def test_short_d_also_produced_the_app(
    short_d_build: subprocess.CompletedProcess[str], app_bin: Path
) -> None:
    assert os.access(app_bin, os.X_OK), f"not executable: {app_bin}"


@pytest.mark.macos
def test_short_d_produced_a_valid_dmg(
    short_d_build: subprocess.CompletedProcess[str], dmg_path: Path
) -> None:
    result = run("hdiutil", "verify", dmg_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_build_with_an_icns_icon_succeeds(
    icns_build: subprocess.CompletedProcess[str] | None,
) -> None:
    if icns_build is None:
        pytest.skip("could not generate a test .icns fixture (sips)")
    assert icns_build.returncode == 0, icns_build.stdout


@pytest.mark.macos
def test_icns_icon_is_copied_as_is_into_the_bundle(
    icns_build: subprocess.CompletedProcess[str] | None, app_icns: Path
) -> None:
    if icns_build is None:
        pytest.skip("could not generate a test .icns fixture (sips)")
    assert app_icns.is_file(), f"no .icns at {app_icns}"


@pytest.mark.macos
def test_build_with_a_bad_icon_still_succeeds(
    bad_icon_build: subprocess.CompletedProcess[str],
) -> None:
    assert bad_icon_build.returncode == 0, bad_icon_build.stdout


@pytest.mark.macos
def test_bad_icon_build_notes_it_could_not_convert(
    bad_icon_build: subprocess.CompletedProcess[str],
) -> None:
    assert "could not convert" in bad_icon_build.stdout


@pytest.mark.macos
def test_bundle_has_no_icon_when_conversion_fails(
    bad_icon_build: subprocess.CompletedProcess[str], app_icns: Path
) -> None:
    """Order matters: the .icns build ran first, so this proves it was removed."""
    assert not app_icns.exists(), f"file should not exist: {app_icns}"


@pytest.mark.macos
def test_default_bundle_id_derives_from_the_calling_user(
    default_bundle_id: str,
) -> None:
    if not HAS_PLUTIL:
        pytest.skip("plutil unavailable")
    assert expected_default_bundle_id("greeter") in default_bundle_id


@pytest.mark.macos
def test_build_with_bundle_id_succeeds(
    custom_bundle_id_build: subprocess.CompletedProcess[str],
) -> None:
    assert custom_bundle_id_build.returncode == 0, custom_bundle_id_build.stdout


@pytest.mark.macos
def test_explicit_bundle_id_is_used_as_is(custom_bundle_id: str) -> None:
    if not HAS_PLUTIL:
        pytest.skip("plutil unavailable")
    assert "com.mkapptest.greeter" in custom_bundle_id


@pytest.mark.macos
def test_build_with_bundle_id_equals_form_succeeds(
    equals_bundle_id_build: subprocess.CompletedProcess[str],
) -> None:
    assert equals_bundle_id_build.returncode == 0, equals_bundle_id_build.stdout


@pytest.mark.macos
def test_bundle_id_equals_form_is_used_as_is(equals_bundle_id: str) -> None:
    if not HAS_PLUTIL:
        pytest.skip("plutil unavailable")
    assert "com.mkapptest.equalsform" in equals_bundle_id


@pytest.mark.macos
def test_invalid_bundle_id_fails_cleanly(
    invalid_bundle_id_run: subprocess.CompletedProcess[str],
) -> None:
    assert invalid_bundle_id_run.returncode != 0


@pytest.mark.macos
def test_invalid_bundle_id_error_mentions_bundle_identifier(
    invalid_bundle_id_run: subprocess.CompletedProcess[str],
) -> None:
    assert "bundle identifier" in invalid_bundle_id_run.stdout


@pytest.mark.macos
def test_build_with_dmg_succeeds(
    dmg_build: subprocess.CompletedProcess[str],
) -> None:
    assert dmg_build.returncode == 0, dmg_build.stdout


@pytest.mark.macos
def test_dmg_produced(
    dmg_build: subprocess.CompletedProcess[str], dmg_path: Path
) -> None:
    assert dmg_path.is_file(), f"no file at {dmg_path}"


@pytest.mark.macos
def test_dmg_passes_hdiutil_verify(
    dmg_build: subprocess.CompletedProcess[str], dmg_path: Path
) -> None:
    if not dmg_path.is_file():
        pytest.skip("dmg missing")
    result = run("hdiutil", "verify", dmg_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_dmg_also_produced_the_app(
    dmg_build: subprocess.CompletedProcess[str], app_bin: Path
) -> None:
    assert os.access(app_bin, os.X_OK), f"not executable: {app_bin}"


@pytest.mark.macos
def test_notarize_without_sign_fails_cleanly(
    notarize_without_sign_run: subprocess.CompletedProcess[str],
) -> None:
    assert notarize_without_sign_run.returncode != 0


@pytest.mark.macos
def test_notarize_without_sign_error_mentions_sign(
    notarize_without_sign_run: subprocess.CompletedProcess[str],
) -> None:
    assert "--sign" in notarize_without_sign_run.stdout


@pytest.mark.macos
def test_notarize_equals_form_without_sign_fails_the_same_way(
    notarize_without_sign_equals_run: subprocess.CompletedProcess[str],
) -> None:
    assert notarize_without_sign_equals_run.returncode != 0


@pytest.mark.macos
def test_notarize_equals_form_error_mentions_sign(
    notarize_without_sign_equals_run: subprocess.CompletedProcess[str],
) -> None:
    assert "--sign" in notarize_without_sign_equals_run.stdout


@pytest.mark.macos
def test_sign_with_invalid_identity_fails_cleanly(
    invalid_sign_run: subprocess.CompletedProcess[str],
) -> None:
    assert invalid_sign_run.returncode != 0


@pytest.mark.macos
def test_invalid_sign_error_mentions_codesign(
    invalid_sign_run: subprocess.CompletedProcess[str],
) -> None:
    assert "codesign" in invalid_sign_run.stdout


@pytest.mark.macos
def test_sign_equals_form_with_invalid_identity_fails_cleanly(
    invalid_sign_equals_run: subprocess.CompletedProcess[str],
) -> None:
    assert invalid_sign_equals_run.returncode != 0


@pytest.mark.macos
def test_sign_equals_form_error_mentions_codesign(
    invalid_sign_equals_run: subprocess.CompletedProcess[str],
) -> None:
    assert "codesign" in invalid_sign_equals_run.stdout


@pytest.mark.macos
def test_build_with_a_real_sign_identity_succeeds(
    real_sign_build: subprocess.CompletedProcess[str],
) -> None:
    assert real_sign_build.returncode == 0, real_sign_build.stdout


@pytest.mark.macos
def test_signed_app_passes_codesign_verify(
    real_sign_build: subprocess.CompletedProcess[str], app_dir: Path
) -> None:
    result = run("codesign", "--verify", "--deep", "--strict", app_dir)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_signed_app_shows_a_real_signing_authority(
    real_sign_build: subprocess.CompletedProcess[str], app_dir: Path
) -> None:
    assert "Authority=" in run("codesign", "-dvvv", app_dir).stdout


@pytest.mark.macos
def test_signed_dmg_passes_codesign_verify(
    real_sign_build: subprocess.CompletedProcess[str], dmg_path: Path
) -> None:
    result = run("codesign", "--verify", dmg_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_signed_dmg_shows_a_real_signing_authority(
    real_sign_build: subprocess.CompletedProcess[str], dmg_path: Path
) -> None:
    assert "Authority=" in run("codesign", "-dvvv", dmg_path).stdout


@pytest.mark.macos
def test_combined_flags_build_successfully(
    combined_build: subprocess.CompletedProcess[str],
) -> None:
    assert combined_build.returncode == 0, combined_build.stdout


@pytest.mark.macos
def test_combined_build_honors_bundle_id(combined_bundle_id: str) -> None:
    assert "com.mkapptest.combined" in combined_bundle_id


@pytest.mark.macos
def test_combined_build_includes_the_icon(
    combined_build: subprocess.CompletedProcess[str], app_icns: Path
) -> None:
    assert app_icns.is_file(), f"no .icns at {app_icns}"


@pytest.mark.macos
def test_combined_build_app_passes_codesign_verify(
    combined_build: subprocess.CompletedProcess[str], app_dir: Path
) -> None:
    result = run("codesign", "--verify", "--deep", "--strict", app_dir)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_combined_build_dmg_passes_codesign_verify(
    combined_build: subprocess.CompletedProcess[str], dmg_path: Path
) -> None:
    result = run("codesign", "--verify", dmg_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_notarize_with_a_nonexistent_profile_fails_cleanly(
    invalid_notarize_build: subprocess.CompletedProcess[str],
) -> None:
    assert invalid_notarize_build.returncode != 0


@pytest.mark.macos
def test_invalid_notarize_error_mentions_notariz(
    invalid_notarize_build: subprocess.CompletedProcess[str],
) -> None:
    assert "notariz" in invalid_notarize_build.stdout


@pytest.mark.macos
def test_build_with_a_real_notarize_profile_succeeds(
    real_notarize_build: subprocess.CompletedProcess[str],
) -> None:
    assert real_notarize_build.returncode == 0, real_notarize_build.stdout


@pytest.mark.macos
def test_notarized_dmg_has_a_stapled_ticket(
    real_notarize_build: subprocess.CompletedProcess[str], dmg_path: Path
) -> None:
    result = run("xcrun", "stapler", "validate", dmg_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.macos
def test_notarized_dmg_passes_a_gatekeeper_assessment(
    real_notarize_build: subprocess.CompletedProcess[str], dmg_path: Path
) -> None:
    result = run(
        "spctl",
        "--assess",
        "--type",
        "open",
        "--context",
        "context:primary-signature",
        "-v",
        dmg_path,
    )
    assert result.returncode == 0, result.stdout


MINIMAL_ARGS = ["--app", "--dmg", "--", "s.py"]
FULL_ARGS = [
    "--app",
    "--dmg",
    "--icon",
    "icon.png",
    "--bundle-id",
    "com.janedoe.myscript",
    "--sign",
    "Developer ID Application: Jane Doe (TEAMID)",
    "--notarize",
    "my-notary-profile",
    "--",
    "s.py",
]


@pytest.mark.quick
@pytest.mark.skipif(not TUI_FILE.is_file(), reason="tui/mkapp_tui.py not found")
def test_tui_compiles() -> None:
    result = run(sys.executable, "-m", "py_compile", TUI_FILE)
    assert result.returncode == 0, result.stdout


@pytest.fixture
def tui_app():
    """A fresh MkappTUI, or a skip if textual isn't importable."""
    pytest.importorskip("textual")
    from mkapp_tui import MkappTUI

    return MkappTUI()


@pytest.mark.asyncio
async def test_tui_minimal_form_produces_correct_cli_args(tui_app) -> None:
    from textual.widgets import Button

    async with tui_app.run_test(size=(120, 50)) as pilot:
        tui_app.query_one("#script").value = "s.py"
        tui_app.query_one("#app").value = True
        tui_app.query_one("#dmg").value = True
        tui_app.query_one("#build", Button).press()
        # The press must be processed before the context exits, or _submit()
        # never runs and return_value stays None.
        await pilot.pause()
    assert tui_app.return_value == MINIMAL_ARGS


@pytest.mark.asyncio
async def test_tui_full_form_produces_correct_cli_args_in_order(tui_app) -> None:
    from textual.widgets import Button

    async with tui_app.run_test(size=(120, 50)) as pilot:
        tui_app.query_one("#script").value = "s.py"
        tui_app.query_one("#app").value = True
        tui_app.query_one("#dmg").value = True
        tui_app.query_one("#icon").value = "icon.png"
        tui_app.query_one("#bundle_id").value = "com.janedoe.myscript"
        tui_app.query_one("#sign").value = "Developer ID Application: Jane Doe (TEAMID)"
        tui_app.query_one("#notarize").value = "my-notary-profile"
        tui_app.query_one("#build", Button).press()
        await pilot.pause()
    assert tui_app.return_value == FULL_ARGS


@pytest.mark.asyncio
async def test_tui_passes_a_dash_named_script_after_the_separator(tui_app) -> None:
    from textual.widgets import Button

    async with tui_app.run_test(size=(120, 50)) as pilot:
        tui_app.query_one("#script").value = "-weird.py"
        tui_app.query_one("#build", Button).press()
        await pilot.pause()
    assert tui_app.return_value == ["--", "-weird.py"]


@pytest.mark.asyncio
async def test_tui_rejects_an_empty_script_path(tui_app) -> None:
    from textual.widgets import Button, Static

    async with tui_app.run_test(size=(120, 50)) as pilot:
        tui_app.query_one("#build", Button).press()
        await pilot.pause()
        error_text = str(tui_app.query_one("#error", Static).content)
    assert "A script path is required." in error_text


@pytest.mark.asyncio
async def test_tui_stays_open_after_empty_script_validation_error(tui_app) -> None:
    from textual.widgets import Button

    async with tui_app.run_test(size=(120, 50)) as pilot:
        tui_app.query_one("#build", Button).press()
        await pilot.pause()
        still_running = tui_app.is_running
    assert still_running is True


@pytest.mark.asyncio
async def test_tui_quit_button_cancels_with_no_args(tui_app) -> None:
    from textual.widgets import Button

    async with tui_app.run_test(size=(120, 50)) as pilot:
        tui_app.query_one("#quit", Button).press()
        # Without the pause this would pass vacuously: return_value is None
        # until the press is processed, whether or not Quit actually works.
        await pilot.pause()
        pressed_while_running = tui_app.is_running
    assert tui_app.return_value is None
    assert pressed_while_running is False, "Quit should have exited the app"


@pytest.mark.asyncio
async def test_tui_mounts_the_ascii_banner(tui_app) -> None:
    from textual.widgets import Static

    async with tui_app.run_test(size=(120, 50)):
        banner = tui_app.query_one("#banner", Static)
    assert banner is not None


def test_tui_banner_constant_holds_the_art() -> None:
    pytest.importorskip("textual")
    from mkapp_tui import BANNER

    assert "|_| |_| |_|" in BANNER


def test_tui_main_hands_the_args_back_one_per_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("textual")
    import mkapp_tui

    args_file = tmp_path / "args"
    monkeypatch.setattr(mkapp_tui.MkappTUI, "run", lambda self: FULL_ARGS)
    monkeypatch.setattr(sys, "argv", ["mkapp_tui.py", str(args_file)])
    assert mkapp_tui.main() == 0
    assert args_file.read_text(encoding="utf-8").splitlines() == FULL_ARGS


def test_tui_main_writes_nothing_when_cancelled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("textual")
    import mkapp_tui

    args_file = tmp_path / "args"
    args_file.touch()
    monkeypatch.setattr(mkapp_tui.MkappTUI, "run", lambda self: None)
    monkeypatch.setattr(sys, "argv", ["mkapp_tui.py", str(args_file)])
    assert mkapp_tui.main() == 0
    assert args_file.read_text(encoding="utf-8") == ""
