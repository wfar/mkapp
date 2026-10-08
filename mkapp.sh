#!/bin/bash
set -euo pipefail

######################################################
#####      mkapp script location directory       #####
######################################################
mkapp_self_dir="$(dirname "$(realpath -- "$0")")"

######################################################
#####            text display colors             #####
######################################################
if [ -t 1 ]; then
    red=$(tput setaf 1 2>/dev/null || true)
    green=$(tput setaf 2 2>/dev/null || true)
    yellow=$(tput setaf 3 2>/dev/null || true)
    blue=$(tput setaf 4 2>/dev/null || true)
    cyan=$(tput setaf 6 2>/dev/null || true)
    normal=$(tput sgr0 2>/dev/null || true)
else
    red="" green="" yellow="" blue="" cyan="" normal=""
fi

######################################################
#####        options (set by parse_args)         #####
######################################################
make_app=false
make_dmg=false
sign_identity=""
notarize_profile=""
icon_path=""
bundle_id=""
script_arg=""
build_work_dir=""
verify_mount=""
python_version=""
build_reqs=()
tui_args=()

######################################################
# Display the usage information for mkapp.
######################################################
usage() {
    local version
    version=$(sed -n 's/^version = "\(.*\)"$/\1/p' "${mkapp_self_dir}/pyproject.toml" 2>/dev/null | head -n 1)
    version=${version:-unknown}

    printf '%s\n' "💎 mkapp - Turn a Python script into a standalone, self-contained executable."
    printf '%s\n' "version ${version}"
    printf '%s\n' ""
    printf '%s\n' "--------------------------------------------------------------------------"
    printf '%s\n' "Script requirements:"
    printf '%s\n' "    Your script's parent folder must contain a .python-version file,"
    printf '%s\n' "    and optionally a requirements.txt file to build the app."
    printf '%s\n' ""
    printf '%s\n' "Example project structure:"
    printf '%s\n' ""
    printf '%s\n' "    your-project/"
    printf '%s\n' "    |--> your_script.py"
    printf '%s\n' "    |--> .python-version"
    printf '%s\n' "    |--> requirements.txt"
    printf '%s\n' ""
    printf '%s\n' "--------------------------------------------------------------------------"
    printf '%s\n' "Usage: $(basename -- "$0") [--app] [--dmg] [--icon <file>] [--bundle-id <id>] [--sign <identity>] [--notarize <profile>] path/to/script.py"
    printf '%s\n' ""
    printf '%s\n' "Options:"
    printf '%s\n' "  -a, --app             wrap the binary in a macOS .app bundle (macOS only)"
    printf '%s\n' "  -d, --dmg             package the .app into a shareable .dmg (implies --app; macOS only)"
    printf '%s\n' "      --icon <file>     icon for the .app bundle (.icns, or an image sips can convert)"
    printf '%s\n' "      --bundle-id <id>  bundle identifier for the .app, e.g. 'com.janedoe.myscript' (implies --app)"
    printf '%s\n' "                        defaults to an id derived from your macOS account"
    printf '%s\n' "      --sign <identity> codesign the .app/.dmg with this identity (implies --app; macOS only)"
    printf '%s\n' "                        e.g. 'Developer ID Application: Jane Doe (TEAMID)'"
    printf '%s\n' "      --notarize <profile>"
    printf '%s\n' "                        notarize the .dmg with Apple and staple the ticket (implies --dmg,"
    printf '%s\n' "                        requires --sign; macOS only). <profile> is a keychain profile set up"
    printf '%s\n' "                        once via: xcrun notarytool store-credentials <profile>"
    printf '%s\n' "  -h, --help            show this help"
}

######################################################
# Display the mkapp banner with colors.
#
# Logo lives in banner.txt so mkapp.sh and the
# TUI share one source. Column 27 is where the icon
# ends and the wordmark begins on every line.
######################################################
display_banner() {
    while IFS= read -r line || [ -n "$line" ]; do
        printf '%s%s%s%s%s\n' "$blue" "${line:0:27}" "$cyan" "${line:27}" "$normal"
    done 2>/dev/null <"${mkapp_self_dir}/banner.txt" || printf 'mkapp\n'
    printf '%s\n\n' "${normal}  Python script → standalone executable"
}

######################################################
# Display the header for mkapp sections.
######################################################
display_header() {
    printf '%s\n' "${blue}--------------------------------------------------------------------------------${normal}"
    printf '%s\n' "$1"
    printf '%s\n' "${blue}--------------------------------------------------------------------------------${normal}"
}

######################################################
# Display a success message with a green checkmark.
######################################################
print_success() {
    local message="${1:-Success!}"
    printf '%s\n' "${green}✔ ${message}${normal}"
}

######################################################
# Display a warning message with a yellow triangle.
######################################################
print_warning() {
    local message="Warning!"
    if [ -n "${1:-}" ]; then
        message="Warning: $1"
    fi
    printf '%s\n' "${yellow}⚠ ${message}${normal}" >&2
}

######################################################
# Display an error message with a red cross.
######################################################
print_error() {
    local message="Error!"
    if [ -n "${1:-}" ]; then
        message="Error: $1"
    fi
    printf '%s\n' "${red}❌ ${message}${normal}" >&2
}

######################################################
# Parse the command-line arguments for mkapp.
######################################################
parse_args() {
    local positional_count=0
    while [ "$#" -gt 0 ]; do
        case "$1" in
        -a | --app)
            make_app=true
            shift
            ;;
        -d | --dmg)
            make_dmg=true
            shift
            ;;
        --icon)
            icon_path="${2:-}"
            shift 2
            ;;
        --icon=*)
            icon_path="${1#*=}"
            shift
            ;;
        --bundle-id)
            bundle_id="${2:-}"
            shift 2
            ;;
        --bundle-id=*)
            bundle_id="${1#*=}"
            shift
            ;;
        --sign)
            sign_identity="${2:-}"
            shift 2
            ;;
        --sign=*)
            sign_identity="${1#*=}"
            shift
            ;;
        --notarize)
            notarize_profile="${2:-}"
            shift 2
            ;;
        --notarize=*)
            notarize_profile="${1#*=}"
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*)
            print_error "Unknown option: $1"
            usage >&2
            exit 2
            ;;
        *)
            script_arg="$1"
            positional_count=$((positional_count + 1))
            shift
            ;;
        esac
    done
    # anything after `--`
    while [ "$#" -gt 0 ]; do
        script_arg="$1"
        positional_count=$((positional_count + 1))
        shift
    done

    if [ "$positional_count" -ne 1 ] || [ -z "$script_arg" ]; then
        print_error "expected exactly one script path."
        usage >&2
        exit 1
    fi

    # Notarizing needs a .dmg to submit.
    if [ -n "$notarize_profile" ]; then
        make_dmg=true
    fi

    # A .dmg wraps a .app, signing needs something to sign, and a bundle id
    # only means anything inside a .app, so all of these imply --app.
    if [ "$make_dmg" = "true" ] || [ -n "$sign_identity" ] || [ -n "$bundle_id" ]; then
        make_app=true
    fi
}

######################################################
# Launch the interactive TUI for mkapp.
#
# The TUI writes the input args to a file, which is
# then read back into the script. Nothing written
# back means the user quit without building.
######################################################
launch_tui() {
    local tui="${mkapp_self_dir}/tui/mkapp_tui.py"

    if [ ! -f "$tui" ]; then
        print_error "TUI not found at \"$tui\". Run with a script path instead. Exiting."
        exit 1
    fi

    if ! command -v uv >/dev/null 2>&1; then
        print_error "uv is required to launch the interactive TUI. Install it from https://docs.astral.sh/uv/, or run mkapp with a script path directly. Exiting."
        exit 1
    fi

    local tui_cmd=(uv run --project "$mkapp_self_dir" --frozen --no-dev)

    local args_file
    args_file=$(mktemp "${TMPDIR:-/tmp}/mkapp-tui.XXXXXX")
    if ! "${tui_cmd[@]}" python "$tui" "$args_file"; then
        rm -f "$args_file"
        exit 1
    fi

    tui_args=()
    while IFS= read -r arg; do
        tui_args+=("$arg")
    done <"$args_file"
    rm -f "$args_file"

    if [ "${#tui_args[@]}" -eq 0 ]; then
        exit 0
    fi
}

######################################################
# Check if uv is installed and available to run.
######################################################
check_uv() {
    display_header "Checking for uv..."

    if ! command -v uv >/dev/null 2>&1; then
        print_error "uv is not installed. Install it from https://docs.astral.sh/uv/, then re-run. Exiting."
        exit 1
    fi

    print_success "uv found ($(uv --version))"
}

######################################################
# Check that the Python version specified in
# .python-version is available via uv.
######################################################
check_python() {
    display_header "Checking python version..."

    if [ -z "$(uv python list "$python_version" 2>/dev/null)" ]; then
        print_error "\"${python_version}\" in \"${script_folder_path}/.python-version\" can't be installed by uv. See the ones it can with: 'uv python list'. Exiting."
        exit 1
    fi

    print_success
}

######################################################
# Validate the input parameters and environment for
# the script.
######################################################
validate_input() {
    display_header "Validating input..."

    if [ ! -f "$absolute_script_path" ]; then
        print_error "File at \"$absolute_script_path\" does not exist. Exiting."
        exit 1
    fi

    if [ ! -d "$script_folder_path" ]; then
        print_error "Directory at \"$script_folder_path\" does not exist. Exiting."
        exit 1
    fi

    if [[ "$script_file_name" != *.py ]]; then
        print_error "File at \"$script_file_name\" is not a python file. Exiting."
        exit 1
    fi

    if [[ "$script_file_name" == *[[:cntrl:]]* ]]; then
        print_error "\"$script_file_name\" contains control characters. Rename the script, then try again. Exiting."
        exit 1
    fi

    local python_version_file="${script_folder_path}/.python-version"
    if [ ! -f "$python_version_file" ]; then
        print_error "No .python-version file found for \"$script_file_name\". Create one specifying the python version required, then try again. Exiting."
        exit 1
    fi

    python_version=$(grep -v -e '^[[:space:]]*#' -e '^[[:space:]]*$' "$python_version_file" | head -n 1 | tr -d '[:space:]' || true)
    if [ -z "$python_version" ]; then
        print_error "\"$python_version_file\" has no python version in it. Add one, then try again. Exiting."
        exit 1
    fi

    if [ "$make_app" = "true" ] && [ "$(uname -s)" != "Darwin" ]; then
        print_error "--app/--dmg/--sign/--notarize are only supported on macOS. Exiting."
        exit 1
    fi

    if [ -n "$icon_path" ] && [ ! -f "$icon_path" ]; then
        print_error "Icon file at \"$icon_path\" does not exist. Exiting."
        exit 1
    fi

    # Reverse-DNS style
    if [ -n "$bundle_id" ] && ! [[ "$bundle_id" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$ ]]; then
        print_error "--bundle-id \"$bundle_id\" is not a valid bundle identifier. Use reverse-DNS style (e.g. \"com.janedoe.myscript\"). Exiting."
        exit 1
    fi

    if [ "$make_dmg" = "true" ] && ! command -v hdiutil >/dev/null 2>&1; then
        print_error "hdiutil not found; --dmg requires macOS. Exiting."
        exit 1
    fi

    if [ -n "$sign_identity" ] && ! command -v codesign >/dev/null 2>&1; then
        print_error "codesign not found. Install the Xcode Command Line Tools ('xcode-select --install'). Exiting."
        exit 1
    fi

    if [ -n "$notarize_profile" ] && [ -z "$sign_identity" ]; then
        print_error "--notarize requires --sign. Apple only notarizes apps signed with a Developer ID. Exiting."
        exit 1
    fi

    if [ -n "$notarize_profile" ] && { ! command -v xcrun >/dev/null 2>&1 || ! xcrun --find notarytool >/dev/null 2>&1 || ! xcrun --find stapler >/dev/null 2>&1; }; then
        print_error "notarytool/stapler not found. Install the Xcode Command Line Tools ('xcode-select --install'). Exiting."
        exit 1
    fi

    print_success
}

######################################################
# Load the pinned PyInstaller versions from the
# "build" dependency group in mkapp's pyproject.toml.
######################################################
load_build_reqs() {
    local pyproject="${mkapp_self_dir}/pyproject.toml"
    local req name

    build_reqs=()
    while IFS= read -r req; do
        build_reqs+=("$req")
    done < <(sed -n '/^build = \[/,/^\]/s/^[[:space:]]*"\([^"]*\)",\{0,1\}[[:space:]]*$/\1/p' "$pyproject" 2>/dev/null)

    for name in pyinstaller pyinstaller-hooks-contrib; do
        case " ${build_reqs[*]:-} " in
        *" ${name}=="[0-9]*) ;;
        *)
            print_error "no pinned version for ${name} in the build dependency group of \"${pyproject}\". Exiting."
            exit 1
            ;;
        esac
    done
}

######################################################
# Builds the Python application using PyInstaller.
# Retrieves the dependencies from requirements.txt
# and adds them to the PyInstaller build.
#
# If .app is requested, the resulting bundle will
# use the --onedir option of PyInstaller and
# signs each file with the signing identity provided.
# Otherwise a single-file executable will be created.
#
# Output file is named after the script file without
# its extension and location within the dist/
# directory.
######################################################
build_app() {
    display_header "Building..."

    local work_dir
    work_dir="${TMPDIR:-/tmp}"
    work_dir="${work_dir%/}/mkapp-build.$(date -u +%Y%m%dT%H%M%SZ)"
    if ! mkdir -m 700 "$work_dir"; then
        print_error "could not create the build folder \"${work_dir}\". Exiting."
        exit 1
    fi
    build_work_dir="$work_dir"

    printf '%s\n' "Using Python ${python_version} from .python-version"
    printf '%s\n' "Using ${build_reqs[*]}"
    local build_cmd=(uv run --no-project --python "$python_version")
    local req
    for req in "${build_reqs[@]}"; do
        build_cmd+=(--with "$req")
    done

    if [ -f "${script_folder_path}/requirements.txt" ]; then
        build_cmd+=(--with-requirements "${script_folder_path}/requirements.txt")
    elif [ -f "${script_folder_path}/pyproject.toml" ]; then
        printf '%s\n' "Note: found pyproject.toml but no requirements.txt. Its dependencies won't be bundled."
        printf '%s\n' "      Generate one first with: 'uv pip compile pyproject.toml -o requirements.txt'"
    fi

    build_cmd+=(python -m PyInstaller --noconfirm
        --workpath "${build_work_dir}/build" --specpath "$build_work_dir")

    if [ "$make_app" = "true" ]; then
        build_cmd+=(--onedir --windowed)
        if [ -n "$sign_identity" ]; then
            build_cmd+=("--codesign-identity=${sign_identity}")
        fi
    else
        build_cmd+=(--onefile)
    fi

    build_cmd+=("--name=${script_file_name_without_extension}" "./${script_file_name}")

    "${build_cmd[@]}"

    print_success
}

######################################################
# Creates a macOS .app bundle from a PyInstaller build
# Uses the PyInstaller build created by
# build_app() as the base for the .app bundle.
#
# Adds an Info.plist and optional icon to the .app
# bundle. Uses the identifier resolved from
# --bundle-id or derived from the calling user's
# macOS account.
######################################################
make_macos_app() {
    display_header "Creating macOS .app bundle..."

    local name="$script_file_name_without_extension"
    local app_dir="${script_folder_path}/dist/${name}.app"

    if [ ! -d "$app_dir" ]; then
        print_error "Expected .app bundle not found at \"$app_dir\". Cannot create .app. Exiting."
        exit 1
    fi

    rm -f "${app_dir}/Contents/Resources/icon-windowed.icns"

    local icon_key=""
    if [ -n "$icon_path" ]; then
        if [[ "$icon_path" == *.icns ]]; then
            cp "$icon_path" "${app_dir}/Contents/Resources/${name}.icns"
            icon_key=true
        elif command -v sips >/dev/null 2>&1 &&
            sips -s format icns "$icon_path" --out "${app_dir}/Contents/Resources/${name}.icns" >/dev/null 2>&1; then
            icon_key=true
        else
            printf '%s\n' "Note: could not convert \"$icon_path\" to .icns. Building the bundle without an icon."
        fi
    fi

    local resolved_bundle_id
    if [ -n "$bundle_id" ]; then
        resolved_bundle_id="$bundle_id"
    else
        local calling_user
        calling_user=$(id -un 2>/dev/null)
        calling_user=$(printf '%s' "$calling_user" | tr -c '[:alnum:]' '-')
        resolved_bundle_id="com.${calling_user}.$(printf '%s' "$name" | tr -c '[:alnum:].-' '-')"
        printf '%s\n' "Note: no --bundle-id given. Using \"${resolved_bundle_id}\" (pass --bundle-id to set your own)."
    fi

    local plist="${app_dir}/Contents/Info.plist"
    printf '%s\n' \
        '<?xml version="1.0" encoding="UTF-8"?>' \
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
        '<plist version="1.0">' \
        '<dict/>' \
        '</plist>' >"$plist"

    set_plist_key "$plist" CFBundleName -string "$name"
    set_plist_key "$plist" CFBundleDisplayName -string "$name"
    set_plist_key "$plist" CFBundleExecutable -string "$name"
    set_plist_key "$plist" CFBundleIdentifier -string "$resolved_bundle_id"
    set_plist_key "$plist" CFBundlePackageType -string APPL
    set_plist_key "$plist" CFBundleVersion -string 1.0
    set_plist_key "$plist" CFBundleShortVersionString -string 1.0
    set_plist_key "$plist" NSHighResolutionCapable -bool YES
    if [ -n "$icon_key" ]; then
        set_plist_key "$plist" CFBundleIconFile -string "${name}.icns"
    fi

    if ! plutil -lint -s "$plist"; then
        print_error "\"${plist}\" is not a valid property list. Exiting."
        exit 1
    fi

    print_success "Created ${app_dir}"
}

######################################################
# Set a key in a plist with plutil, which escapes the
# value, so any characters in it are stored safely.
#
# Parameters:
#   $1 - path to the plist
#   $2 - key
#   $3 - value type, e.g. -string or -bool
#   $4 - value
######################################################
set_plist_key() {
    if ! plutil -replace "$2" "$3" "$4" "$1"; then
        print_error "could not set ${2} in \"${1}\". Exiting."
        exit 1
    fi
}

######################################################
# Resign the app with an ad-hoc signature since
# the Info.plist or icon has been modified.
#
# Used when no signing identity is provided.
#
# Parameters:
#   $1 - path to the .app bundle to resign with
#        an ad-hoc signature.
######################################################
resign_adhoc_app() {
    local path="$1"
    if ! codesign --force --sign - "$path" >/dev/null 2>&1; then
        print_error "ad-hoc codesign failed for \"${path}\". Exiting."
        exit 1
    fi
}

######################################################
# Sign the given path with the specified signing
# identity and extra codesign arguments.
#
# Parameters:
#   $1 - path to the item to sign
#   $2 - label for display purposes
#   $@ - extra codesign arguments
######################################################
codesign_path() {
    local path="$1" label="$2"
    shift 2
    display_header "Signing ${label}..."

    if codesign --force --timestamp --sign "$sign_identity" "$@" "$path"; then
        print_success "Signed ${path}"
    else
        print_error "codesign failed for \"${path}\". List available identities with: 'security find-identity -v -p codesigning'. Exiting."
        exit 1
    fi
}

######################################################
# Submits the .dmg to Apple's notary service, waits
# for processing to complete and then staples the
# notarization ticket returned by Apple.
#
# Requires a keychain profile to already be saved.
#
# Parameters:
#   $1 - path to the .dmg to notarize and staple
######################################################
notarize_and_staple() {
    local path="$1"
    display_header "Notarizing ${path}..."

    if ! xcrun notarytool submit "$path" --keychain-profile "$notarize_profile" --wait; then
        print_error "notarization failed for \"${path}\". Check the profile with: xcrun notarytool history --keychain-profile \"$notarize_profile\". Exiting."
        exit 1
    fi
    print_success "Notarized ${path}"

    display_header "Stapling notarization ticket..."
    if ! xcrun stapler staple "$path"; then
        print_error "stapling failed for \"${path}\" (it was notarized, but the ticket wasn't attached  which means recipients will need network access on first launch to verify the notarization with Apple). Exiting."
        exit 1
    fi
    print_success "Stapled ${path}"
}

######################################################
# Verifies that the signed, notarized, and stapled
# .dmg and .app bundle inside it pass Gatekeeper
# on a recipient's Mac.
#
# Any failures during this verification will cause
# the build to fail.
#
# Parameters:
#   $1 - path to the .dmg to verify
######################################################
verify_gatekeeper() {
    local dmg_path="$1"
    local name="$script_file_name_without_extension"
    display_header "Verifying Gatekeeper acceptance..."

    if ! stapler validate "$dmg_path"; then
        print_error "stapler validation failed for \"${dmg_path}\". The notarization ticket isn't valid. Exiting."
        exit 1
    fi

    if ! spctl -a -vv --type install "$dmg_path"; then
        print_error "spctl rejected \"${dmg_path}\" for install. It will not pass Gatekeeper. Exiting."
        exit 1
    fi

    # Mount the finished .dmg and check the .app as a recipient would on their Mac.
    # clean_up unmounts it if the script exits before the detach below.
    local mount_point="${build_work_dir}/verify-mount"
    mkdir "$mount_point"
    if ! hdiutil attach "$dmg_path" -nobrowse -readonly -mountpoint "$mount_point"; then
        print_error "could not mount \"${dmg_path}\" to verify its contents. Exiting."
        exit 1
    fi
    verify_mount="$mount_point"

    local mounted_app="${mount_point}/${name}.app"
    local verify_failed=""

    # Deep verify every nested binary/library's signature.
    codesign --verify --deep --strict -vvv "$mounted_app" || verify_failed=true

    # Check Gatekeeper's actual launch-time assessment on the .app, separate from
    # the install-time assessment on the .dmg.
    spctl -a -vv --type exec "$mounted_app" || verify_failed=true

    # Hardened runtime is required for notarization eligibility. Confirm the
    # flag actually made it onto the shipped binary.
    local runtime_flags
    runtime_flags=$(codesign -dv "$mounted_app" 2>&1 | grep 'flags=' || true)
    printf '%s\n' "$runtime_flags"
    if [ -z "$runtime_flags" ]; then
        print_error "could not read the code signature of \"${mounted_app}\"."
        verify_failed=true
    elif ! printf '%s' "$runtime_flags" | grep -q 'runtime'; then
        print_error "\"${mounted_app}\" is missing the hardened runtime flag (required for notarization)."
        verify_failed=true
    fi

    if ! hdiutil detach "$mount_point" -quiet; then
        print_error "could not unmount \"${mount_point}\" after verification. Detach manually with: hdiutil detach \"${mount_point}\". Exiting."
        exit 1
    fi
    verify_mount=""

    if [ -n "$verify_failed" ]; then
        print_error "the .app inside \"${dmg_path}\" failed signature or Gatekeeper verification. Exiting."
        exit 1
    fi

    print_success "Verified ${dmg_path} and its .app pass Gatekeeper and are ready to distribute"
}

######################################################
# Creates a .dmg containing the built and verified
# .app for distribution.
#
# The .app and an /Applications symlink are staged into
# a writable image. If a Finder session is available,
# its used to set the background layout for the .dmg
# Otherwise, the .dmg will have a plain layout.
# Finally the image is converted to a compressed,
# read-only .dmg.
######################################################
make_dmg() {
    display_header "Creating .dmg..."

    local name="$script_file_name_without_extension"
    local app_dir="${script_folder_path}/dist/${name}.app"
    local dmg_path="${script_folder_path}/dist/${name}.dmg"
    local background="${mkapp_self_dir}/resources/dmg_background.tiff"

    if [ ! -d "$app_dir" ]; then
        print_error "Expected .app not found at \"$app_dir\". Cannot create .dmg. Exiting."
        exit 1
    fi

    # Stage the bundle, an /Applications symlink, and the background inside the
    # private build folder, which clean_up removes on exit.
    local staging="${build_work_dir}/dmg-staging"
    local rw_dmg="${build_work_dir}/rw.dmg"
    mkdir "$staging"
    cp -R "$app_dir" "${staging}/"
    ln -s /Applications "${staging}/Applications"
    if [ -f "$background" ]; then
        mkdir "${staging}/.background"
        cp "$background" "${staging}/.background/background.tiff"
    fi

    if ! hdiutil create -volname "$name" -srcfolder "$staging" -fs HFS+ -format UDRW -ov "$rw_dmg" >/dev/null; then
        print_error "hdiutil failed to create the writable image \"$rw_dmg\". Exiting."
        exit 1
    fi

    if [ -f "$background" ]; then
        dmg_layout "$rw_dmg" "${name}.app" || print_warning "could not set the .dmg window layout (it needs a Finder session). Building with the plain layout."
    fi

    rm -f "$dmg_path"
    if ! hdiutil convert "$rw_dmg" -format UDZO -o "$dmg_path" >/dev/null; then
        print_error "hdiutil failed to convert the image to \"$dmg_path\". Exiting."
        exit 1
    fi

    print_success "Created ${dmg_path}"
}

######################################################
# Runs a command once every second until it succeeds
# the timeout passes.
#
# Parameters:
#   $1 - timeout in seconds
#   $@ - the command to run
#
# Returns:
#   0 - command succeeded in time.
#   1 - timed out.
######################################################
wait_until() {
    local deadline=$((SECONDS + $1))
    shift
    until "$@"; do
        if [ "$SECONDS" -ge "$deadline" ]; then
            return 1
        fi
        sleep 1
    done
}

######################################################
# Use Finder to arrange the window of a mounted .dmg.
# Sets the background and positions of items in the
# window using Finder and AppleScript.

# Parameters:
#   $1 - volume name
#   $2 - file name of the .app on the volume
######################################################
finder_layout_dmg_window() {
    osascript - "$1" "$2" >/dev/null 2>&1 <<'APPLESCRIPT'
on run argv
    set volumeName to item 1 of argv
    set appName to item 2 of argv
    with timeout of 30 seconds
        tell application "Finder"
            tell disk volumeName
                open
                set current view of container window to icon view
                set toolbar visible of container window to false
                set statusbar visible of container window to false
                set the bounds of container window to {200, 120, 860, 548}
                set viewOptions to the icon view options of container window
                set arrangement of viewOptions to not arranged
                set icon size of viewOptions to 128
                set text size of viewOptions to 13
                set background picture of viewOptions to file ".background:background.tiff"
                set position of item appName of container window to {165, 185}
                set position of item "Applications" of container window to {495, 185}
                close
                update without registering applications
            end tell
        end tell
    end timeout
end run
APPLESCRIPT
}

######################################################
# Checks that Finder saved the app's icon position in
# the volume's .DS_Store. Finder stores file names
# there as UTF-16, so the name is looked up as hex.
#
# Parameters:
#   $1 - mount point of the volume
#   $2 - file name of the .app on the volume
######################################################
dmg_layout_saved() {
    local app_name_hex
    app_name_hex=$(printf '%s' "$2" | iconv -f UTF-8 -t UTF-16BE | xxd -p | tr -d '\n')
    xxd -p "${1}/.DS_Store" 2>/dev/null | tr -d '\n' | grep -qF "$app_name_hex"
}

######################################################
# Mounts a writable .dmg and uses Finder to set
# window layout and background image. Finder saves
# the layout in the volume's .DS_Store.
#
# Parameters:
#   $1 - path to the writable .dmg
#   $2 - file name of the .app inside it
#
# Returns:
#   0 - layout was successfully saved.
#   1 - layout could not be saved.
######################################################
dmg_layout() {
    local rw_dmg="$1"
    local app_name="$2"

    local attach_output mount_point volume_name
    if ! attach_output=$(hdiutil attach "$rw_dmg" -readwrite -noverify -noautoopen); then
        return 1
    fi
    mount_point=$(printf '%s\n' "$attach_output" | awk -F'\t' '/\/Volumes\//{print $NF}' | tail -n 1)
    if [ -z "$mount_point" ]; then
        return 1
    fi
    volume_name=$(basename "$mount_point")
    rm -f "${mount_point}/.DS_Store"

    # Wait for Finder to save the layout before detaching the volume.
    local status=1
    if wait_until 30 finder_layout_dmg_window "$volume_name" "$app_name" &&
        wait_until 10 dmg_layout_saved "$mount_point" "$app_name"; then
        status=0
    fi

    # Finder can hold the volume for a moment after laying out the window.
    sync
    wait_until 10 hdiutil detach "$mount_point" -quiet 2>/dev/null ||
        hdiutil detach "$mount_point" -force -quiet || true

    return "$status"
}

######################################################
# Cleans up intermediate build artifacts.
# Called on script exit.
######################################################
clean_up() {
    display_header "Cleaning up..."

    if [ -n "${verify_mount:-}" ]; then
        if ! hdiutil detach "$verify_mount" -quiet 2>/dev/null &&
            ! hdiutil detach "$verify_mount" -force -quiet 2>/dev/null; then
            print_warning "could not unmount \"${verify_mount}\". Detach it manually with: hdiutil detach \"${verify_mount}\""
            build_work_dir=""
        fi
    fi

    if [ -n "${build_work_dir:-}" ]; then
        rm -rf "$build_work_dir"
    fi

    print_success
}

######################################################
# Main entry point for the script.

# Overview of the steps:
# 1. Launch TUI if no arguments are provided and
#    running interactively.
# 2. Parse command-line arguments.
# 3. Resolve script and icon paths.
# 4. Display banner and validate input.
# 5. Check for required tools (uv, Python).
# 6. Build (sign and notarize, if applicable) the app
#    and optionally create a .dmg.
# 7. Clean up intermediate artifacts on exit.
######################################################
run() {
    # No arguments provided and if running in an interactive terminal, launch TUI.
    if [ "$#" -eq 0 ] && [ -t 0 ] && [ -t 1 ]; then
        launch_tui
        set -- "${tui_args[@]}"
    fi

    parse_args "$@"

    # Get script paths and names.
    absolute_script_path=$(realpath -- "$script_arg" 2>/dev/null || echo "$script_arg")
    script_folder_path="$(dirname -- "$absolute_script_path")"
    script_file_name=$(basename -- "$absolute_script_path")
    script_file_name_without_extension=${script_file_name%.*}

    # Resolve the icon path to an absolute path if provided.
    if [ -n "$icon_path" ]; then
        icon_path=$(realpath -- "$icon_path" 2>/dev/null || echo "$icon_path")
    fi

    display_banner

    validate_input
    load_build_reqs
    check_uv
    check_python

    display_header "Making app from \"$script_file_name\" ..."

    # Clean up intermediate artifacts on exit.
    trap clean_up EXIT

    cd "$script_folder_path"
    build_app

    # Build and sign the macOS app.
    if [ "$make_app" = "true" ]; then
        make_macos_app
        if [ -n "$sign_identity" ]; then
            codesign_path "${script_folder_path}/dist/${script_file_name_without_extension}.app" \
                "app bundle" --options runtime
        else
            resign_adhoc_app "${script_folder_path}/dist/${script_file_name_without_extension}.app"
        fi
    fi

    # Build and sign the disk image.
    if [ "$make_dmg" = "true" ]; then
        make_dmg
        if [ -n "$sign_identity" ]; then
            codesign_path "${script_folder_path}/dist/${script_file_name_without_extension}.dmg" \
                "disk image"
        fi
        if [ -n "$notarize_profile" ]; then
            notarize_and_staple "${script_folder_path}/dist/${script_file_name_without_extension}.dmg"
            verify_gatekeeper "${script_folder_path}/dist/${script_file_name_without_extension}.dmg"
        fi
    fi

    display_header "Done making app!"
}

##########################################
##########################################

run "$@"
