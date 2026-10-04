# ci

A portable CI kit for Go services: Go checks, security scans, a k6 build with extensions, k6
result summaries, and checks for embedded pages and monitoring configs. One set of scripts,
three ways to run it:

| Where | How | What you write in the project |
|---|---|---|
| **GitHub Actions** | reusable workflow + actions | `uses: Dmitry-Fedotov-Dev/ci/actions/go-security@v1` |
| **GitLab CI** | hidden jobs to `extends:` | `extends: .cikit-go-security` |
| **A laptop, any other CI** | plain scripts | `bin/go-security` |

```
bin/            the steps themselves: bash, flags, no CI vendor inside
lib/ci.sh       the only file that knows GitHub from GitLab (errors, summaries, log sections)
scripts/        Python helpers the steps call (summaries, JS check)
actions/        GitHub wrappers: inputs → bin/ flags
gitlab/ci.yml   GitLab wrappers: CIKIT_* variables → bin/ flags
templates/      starter pipelines to copy into a new project
testdata/       what the selftests run against
```

Used by [kontakt](https://github.com/Dmitry-Fedotov-Dev/kontakt) and
[xk6-sip](https://github.com/Dmitry-Fedotov-Dev/xk6-sip).

## New project

Copy a starter and delete what you do not need:
[`templates/github-go.yml`](templates/github-go.yml) → `.github/workflows/ci.yml`, or
[`templates/gitlab-go.yml`](templates/gitlab-go.yml) → `.gitlab-ci.yml`.

### GitHub

Pin a version: `@v1` follows compatible releases, `@v1.x.y` never moves.

```yaml
jobs:
  go:
    uses: Dmitry-Fedotov-Dev/ci/.github/workflows/go.yml@v1
    with:
      test-flags: -race -count=2

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: Dmitry-Fedotov-Dev/ci/actions/go-security@v1
```

### GitLab

```yaml
include:
  - remote: https://raw.githubusercontent.com/Dmitry-Fedotov-Dev/ci/v1/gitlab/ci.yml

go:
  extends: .cikit-go
  variables:
    CIKIT_GO_TEST_FLAGS: -race -count=2

security:
  extends: .cikit-go-security
```

What GitLab gets on top of the log: test results in the merge request (JUnit), coverage on
the job, gosec findings in the Code Quality widget (only new and fixed ones), k6 and gosec
summaries as a merge request link (`expose_as`).

**Inside a company GitLab** (runners without internet, an internal registry):

1. Mirror this repository into your GitLab, e.g. `tools/ci` (Settings → Repository → Mirroring,
   or a plain push). Its own `.gitlab-ci.yml` then selftests the templates on your runners.
2. Include from the mirror and point the scripts and images at internal copies:

   ```yaml
   include:
     - project: tools/ci
       ref: v1
       file: gitlab/ci.yml

   variables:
     CIKIT_URL: https://gitlab.example.com/tools/ci.git
     CIKIT_GO_IMAGE: registry.example.com/golang:1.24
     CIKIT_GO_TOOLS_IMAGE: registry.example.com/golang:1
   ```

   A private mirror needs the job token to clone it: allow the project in the mirror's
   Settings → CI/CD → Job token permissions and set
   `CIKIT_URL: https://gitlab-ci-token:${CI_JOB_TOKEN}@gitlab.example.com/tools/ci.git`.

GitLab includes YAML only, not scripts, so each job's `before_script` clones this repository at
`CIKIT_REF` (default `v1`) and exports its path as `$CIKIT`. A job with its own `before_script`
keeps ours with `- !reference [.cikit, before_script]`.

### Locally, or in any other CI

```sh
git clone https://github.com/Dmitry-Fedotov-Dev/ci ~/ci
~/ci/bin/go-check --test-flags "-race -count=2"
~/ci/bin/go-security --gosec-args -exclude=G115
~/ci/bin/promtool --dir monitoring/prometheus --rule-tests tests/alerts_test.yml
```

Outside GitHub the summaries go to `ci-summary.md` (`CIKIT_SUMMARY` to change it).

## Steps

| Step | GitHub | GitLab | Does |
|---|---|---|---|
| [`go-check`](bin/go-check) | [`go.yml`](.github/workflows/go.yml) (workflow) | `.cikit-go` | gofmt, go vet, go test; `--junit`, `--coverage` |
| [`go-security`](bin/go-security) | [`actions/go-security`](actions/go-security/action.yml) | `.cikit-go-security` | govulncheck (blocking), gosec (report unless `--gosec-fail`), summary, Code Quality report |
| [`xk6-build`](bin/xk6-build) | [`actions/xk6-build`](actions/xk6-build/action.yml) | `.cikit-xk6-build` | k6 with extensions: `--with module@version` or `module=.` for the checked-out repo |
| [`k6-summary`](bin/k6-summary) | [`actions/k6-summary`](actions/k6-summary/action.yml) | `.cikit-k6-summary` | Markdown from k6 JUnit reports (`functional`) or `--summary-export` (`load`); `--lang en\|ru` |
| [`inline-js`](bin/inline-js) | [`actions/inline-js`](actions/inline-js/action.yml) | `.cikit-inline-js` | `node --check` for `.js` and inline `<script>` in `.html` |
| [`promtool`](bin/promtool) | [`actions/promtool`](actions/promtool/action.yml) | `.cikit-promtool` | `promtool check config` and alert rule unit tests |
| [`dashboards-sync`](bin/dashboards-sync) | [`actions/dashboards-sync`](actions/dashboards-sync/action.yml) | `.cikit-dashboards-sync` | generated Grafana dashboards match their generators |

Every script documents its flags in its header. Two exceptions to "logic only in `bin/`", both
small and both covered by the selftests: the GitHub workflow `go.yml` runs gofmt/vet/test
inline (a reusable workflow cannot locate its own repository at the right version), and the
GitLab promtool job runs inside the Prometheus image (busybox: no git to fetch the scripts with).

## Rules

- **Logic lives in `bin/`, never in a wrapper.** An action or a GitLab job only maps its
  inputs to flags. A fix in `bin/` reaches GitHub, GitLab and laptops at once.
- **Every release passes two selftests** against `testdata/`, including the failure paths (bad
  JS, dashboard drift, a bad flag must really fail):
  [GitHub](.github/workflows/selftest.yml) runs the actions, the scripts and — through
  [gitlab-ci-local](https://github.com/firecow/gitlab-ci-local) in Docker — the GitLab
  templates in their real images; [`.gitlab-ci.yml`](.gitlab-ci.yml) is that GitLab selftest.
- **Breaking change → `v2`.** Renaming or removing an input, a flag or a `CIKIT_*` variable, or
  changing a default that changes a project's result. Projects move on their own schedule.
- **Release:** develop on `next`; point a project's branch at `@next` and let its CI pass together
  with selftest; then merge to `main`, move the `v1` **branch** (`git push origin main:v1`) and
  tag `v1.x.y` (Releases → Draft a new release). `v1` is a branch, not a tag: `uses: …@v1` and
  GitLab's `ref: v1` resolve either, and a branch moves forward without force-pushing.
- **Never name a variable `K6_*` or `XK6_*`**: k6 and xk6 read those as their own options.
  Ours start with `CIKIT_`.
- **GitLab: checks go in `script`, not `after_script`** — GitLab ignores `after_script` failures.

License: MIT.
