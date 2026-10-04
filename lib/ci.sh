# Shared helpers for bin/*: the same script runs on GitHub Actions, GitLab CI and a laptop,
# and only this file knows the difference.
#
#   ci_error TITLE MESSAGE [FILE]  — an error the platform shows on its own (GitHub annotation)
#   ci_summary < markdown          — append to the run summary: GitHub step summary page, or
#                                    $CIKIT_SUMMARY (default ci-summary.md) everywhere else —
#                                    the GitLab templates publish that file as an artifact
#   ci_section NAME TITLE / ci_section_end NAME — collapsible block in the job log
#   ci_need CMD...                 — fail with a clear message when a tool is missing
# shellcheck shell=bash

CIKIT_HOME=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export CIKIT_HOME
# Pinned tool versions (VER_*). Not exported: they are defaults for our flags, nothing else.
# shellcheck source=../versions.env
. "$CIKIT_HOME/versions.env"

ci_platform() {
  if [ -n "${GITHUB_ACTIONS:-}" ]; then echo github
  elif [ -n "${GITLAB_CI:-}" ]; then echo gitlab
  else echo local; fi
}

ci_error() {
  local title=$1 msg=$2 file=${3:-}
  if [ "$(ci_platform)" = github ]; then
    if [ -n "$file" ]; then echo "::error file=$file,title=$title::$msg"; else echo "::error title=$title::$msg"; fi
  else
    printf '\033[31mERROR [%s]\033[0m %s%s\n' "$title" "${file:+$file: }" "$msg" >&2
  fi
}

ci_summary() {
  if [ "$(ci_platform)" = github ] && [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    cat >>"$GITHUB_STEP_SUMMARY"
  else
    cat >>"${CIKIT_SUMMARY:-ci-summary.md}"
  fi
}

ci_section() {
  case "$(ci_platform)" in
    github) echo "::group::$2" ;;
    gitlab) printf '\e[0Ksection_start:%s:%s[collapsed=true]\r\e[0K%s\n' "$(date +%s)" "$1" "$2" ;;
    *) echo "== $2" ;;
  esac
}

ci_section_end() {
  case "$(ci_platform)" in
    github) echo "::endgroup::" ;;
    gitlab) printf '\e[0Ksection_end:%s:%s\r\e[0K\n' "$(date +%s)" "$1" ;;
  esac
}

ci_need() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null || { ci_error setup "$c is not installed"; exit 1; }
  done
}

# ci_go_install BINARY MODULE/cmd@VERSION — use the binary when it is already there at that
# version (the cikit image has every tool), go install it otherwise.
ci_go_install() {
  local bin=$1 pkg=$2 want=${2##*@}
  PATH="$(go env GOPATH)/bin:$PATH"
  export PATH
  if command -v "$bin" >/dev/null && [ "$(ci_tool_version "$bin")" = "${want#v}" ]; then return 0; fi
  go install "$pkg"
}

# The module version a Go binary was built from ("1.8.0"), empty when unknown.
ci_tool_version() {
  go version -m "$(command -v "$1")" 2>/dev/null | awk '$1 == "mod" { sub(/^v/, "", $3); print $3; exit }'
}
