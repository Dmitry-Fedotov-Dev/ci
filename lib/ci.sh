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

# go install, then the binary is on PATH even when GOPATH/bin is not (fresh runners, containers).
ci_go_install() {
  go install "$1"
  PATH="$(go env GOPATH)/bin:$PATH"
  export PATH
}
