#!/bin/bash
set -euo pipefail

# URL for mkapp repository and installation directory
repo_url="https://github.com/wfar/mkapp.git"
install_dir="${HOME}/.mkapp"

# mkapp installer line blocks for shell rc files
start_marker="# >>> mkapp installer >>>"
end_marker="# <<< mkapp installer <<<"

# temp file used while rewriting an rc file, removed on exit
tmp_file=""

# text display colors for terminal output
if [ -t 1 ]; then
    red=$(tput setaf 1 2>/dev/null || true)
    green=$(tput setaf 2 2>/dev/null || true)
    yellow=$(tput setaf 3 2>/dev/null || true)
    blue=$(tput setaf 4 2>/dev/null || true)
    normal=$(tput sgr0 2>/dev/null || true)
else
    red="" green="" yellow="" blue="" normal=""
fi

display_header() {
    printf '%s\n' "${blue}--------------------------------------------------------------------------------${normal}"
    printf '%s\n' "$1"
    printf '%s\n' "${blue}--------------------------------------------------------------------------------${normal}"
}

print_success() {
    printf '%s\n' "${green}✔ ${1:-Success!}${normal}"
}

print_warning() {
    printf '%s\n' "${yellow}⚠ Warning: $1${normal}" >&2
}

print_error() {
    printf '%s\n' "${red}❌ Error: $1${normal}" >&2
}

usage() {
    printf '%s\n' "Usage: install.sh [-y|--yes]"
    printf '%s\n' ""
    printf '%s\n' "  -y, --yes   install without asking for confirmation"
    printf '%s\n' "  -h, --help  show this help"
}

# ask the user to confirm before anything is changed
confirm_install() {
    display_header "Installing mkapp"
    printf '%s\n' "This will:"
    printf '%s\n' "  - download mkapp to \"$install_dir\" (unless run from an existing checkout)"
    printf '%s\n' "  - install uv if it's missing"
    printf '%s\n' "  - add mkapp to your PATH in your shell's startup file(s)"
    printf '\n'

    if [ "$assume_yes" = true ]; then
        return
    fi

    if ! { : </dev/tty; } 2>/dev/null; then
        print_error "No terminal available to confirm the install. Re-run with --yes to install without prompting."
        exit 1
    fi

    local reply
    while true; do
        printf '%s' "Install mkapp? [Y/n] "
        if ! read -r reply </dev/tty; then
            printf '\n'
            reply="n"
        fi
        case "$reply" in
        "" | [Yy] | [Yy][Ee][Ss])
            return
            ;;
        [Nn] | [Nn][Oo])
            printf '%s\n' "Install cancelled."
            exit 0
            ;;
        *)
            printf '%s\n' "Please answer y or n."
            ;;
        esac
    done
}

# locate mkapp's source code, either from an
# existing checkout or by cloning the repository
locate_source() {
    display_header "Locating mkapp..."

    local script_dir
    script_dir="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

    if [ -f "${script_dir}/mkapp.sh" ]; then
        source_dir="$script_dir"
        print_success "Using existing checkout at \"$source_dir\""
        return
    fi

    if ! command -v git >/dev/null 2>&1; then
        print_error "git is required to download mkapp. Install it, then re-run. Exiting."
        exit 1
    fi

    source_dir="$install_dir"
    if [ -d "${source_dir}/.git" ]; then
        printf '%s\n' "Found existing install at \"$source_dir\", updating..."
        git -C "$source_dir" pull --ff-only
    else
        printf '%s\n' "Cloning $repo_url to \"$source_dir\"..."
        git clone --depth 1 "$repo_url" "$source_dir"
    fi

    print_success "mkapp downloaded to \"$source_dir\""
}

# install uv
install_uv() {
    display_header "Checking for uv..."

    if command -v uv >/dev/null 2>&1; then
        print_success "uv found ($(uv --version))"
        return
    fi

    printf '%s\n' "uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh

    hash -r
    if ! command -v uv >/dev/null 2>&1; then
        print_error "uv installer finished but 'uv' is still not on PATH. Open a new shell and re-run this script."
        exit 1
    fi
    print_success "uv installed ($(uv --version))"
}

# report the install state of mkapp in the rc_file:
# no mkapp block ("none"), exactly one well-formed block ("found"), or anything else ("bad")
rc_block_state() {
    local rc_file="$1"

    if [ ! -e "$rc_file" ]; then
        printf '%s\n' "none"
        return
    fi

    awk -v start="$start_marker" -v end="$end_marker" '
        function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t\r]+$/, "", s); return s }
        { line = trim($0) }
        line == start { starts++; if (!start_nr) start_nr = NR }
        line == end { ends++; if (!end_nr) end_nr = NR }
        END {
            if (!starts && !ends) print "none"
            else if (starts == 1 && ends == 1 && start_nr < end_nr) print "found"
            else print "bad"
        }
    ' "$rc_file"
}

# add the mkapp block to rc_file, replacing an existing one
update_rc_file() {
    local rc_file="$1" block="$2"
    local state
    state="$(rc_block_state "$rc_file")"

    case "$state" in
    bad)
        print_warning "$rc_file has a damaged or duplicated mkapp block, so it was left unchanged."
        printf '%s\n' "  Remove everything between \"$start_marker\" and \"$end_marker\" in it, then re-run this script." >&2
        return
        ;;
    found)
        cp "$rc_file" "${rc_file}.mkapp.bak"
        tmp_file="$(mktemp)"

        awk -v start="$start_marker" -v end="$end_marker" '
            function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t\r]+$/, "", s); return s }
            { line = trim($0) }
            skip { if (line == end) skip = 0; next }
            line == start { held = 0; skip = 1; next }
            held { print held_line; held = 0 }
            line == "" { held_line = $0; held = 1; next }
            { print }
            END { if (held) print held_line }
        ' "$rc_file" >"$tmp_file"

        cat "$tmp_file" >"$rc_file"
        rm -f "$tmp_file"
        tmp_file=""
        ;;
    esac

    if [ -s "$rc_file" ]; then
        printf '\n' >>"$rc_file"
    fi
    printf '%s\n' "$block" >>"$rc_file"
    print_success "Updated $rc_file"
}

# make mkapp.sh runnable, and reachable as a plain "mkapp" command
setup_command() {
    display_header "Setting up the mkapp command..."

    if [[ "$source_dir" == *[\"\$\`\\]* || "$source_dir" == *$'\n'* ]]; then
        print_error "mkapp's path \"$source_dir\" contains a character (\", \$, \`, \\ or a newline) that can't be safely added to your shell config. Move it to a different directory and re-run."
        exit 1
    fi

    chmod +x "${source_dir}/mkapp.sh"

    local block
    # shellcheck disable=SC2016  # $PATH must stay literal
    block="$(printf '%s\nexport PATH="$PATH:%s"\nalias mkapp="%s/mkapp.sh"\n%s' \
        "$start_marker" "$source_dir" "$source_dir" "$end_marker")"

    local rc_file=""
    case "$(basename -- "${SHELL:-}")" in
    zsh) rc_file="${HOME}/.zshrc" ;;
    bash) rc_file="${HOME}/.bashrc" ;;
    esac

    if [ -z "$rc_file" ] || [ ! -e "$rc_file" ]; then
        print_warning "No ~/.zshrc or ~/.bashrc found for your shell (${SHELL:-unknown}). Add these lines to your shell's config yourself:"
        printf '%s\n' "$block" >&2
        return
    fi

    update_rc_file "$rc_file" "$block"
}

main() {
    assume_yes=false
    while [ "$#" -gt 0 ]; do
        case "$1" in
        -y | --yes)
            assume_yes=true
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage >&2
            exit 1
            ;;
        esac
        shift
    done

    trap '[ -z "$tmp_file" ] || rm -f "$tmp_file"' EXIT

    local source_dir
    confirm_install
    locate_source
    install_uv
    setup_command

    display_header "Done"
    print_success "mkapp is installed."
    printf '%s\n\n' "Open a new terminal (or 'source' your shell's startup file) and run: mkapp"
}

main "$@"
