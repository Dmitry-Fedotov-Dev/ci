# ci

A portable CI kit for Go services: Go checks, golangci-lint, security scans, a k6 build with
extensions, k6 result summaries, and checks for embedded pages and monitoring configs. One set
of scripts, one image, four ways to run them:

| Where | How | What you write in the project |
|---|---|---|
| **GitHub Actions** | reusable workflow + actions | `uses: Dmitry-Fedotov-Dev/ci/actions/go-lint@v1` |
| **GitLab 17+** | CI/CD components, typed inputs | `- component: $CI_SERVER_FQDN/tools/ci/go-lint@v1` |
| **Any GitLab** | include templates (hidden jobs) | `extends: .cikit-go-lint` |
| **A laptop, any other CI** | the image or plain scripts | `docker run … ghcr.io/dmitry-fedotov-dev/ci:v1 go-lint` |

```
bin/            the steps: bash, flags, no CI vendor inside
lib/ci.sh       the only file that knows GitHub from GitLab (errors, summaries, log sections)
versions.env    every tool version, pinned; Renovate keeps them current
Dockerfile      the cikit image: all tools at those versions + the scripts (/opt/cikit)
config/         defaults, e.g. golangci.yml for projects without their own
scripts/        Python helpers the steps call (summaries, JS check)
actions/        GitHub wrappers: inputs → bin/ flags
templates/      GitLab CI/CD components: inputs → bin/ flags
gitlab/ci.yml   GitLab include templates: CIKIT_* variables → bin/ flags
starters/       pipelines to copy into a new project
testdata/       what the selftests run against
```

Used by [kontakt](https://github.com/Dmitry-Fedotov-Dev/kontakt) and
[xk6-sip](https://github.com/Dmitry-Fedotov-Dev/xk6-sip).

## New project

Copy a starter and delete what you do not need:

| | Starter | Copy to |
|---|---|---|
| GitHub | [`starters/github-go.yml`](starters/github-go.yml) | `.github/workflows/ci.yml` |
| GitLab 17+, with a mirror | [`starters/gitlab-components.yml`](starters/gitlab-components.yml) | `.gitlab-ci.yml` |
| Any GitLab | [`starters/gitlab-go.yml`](starters/gitlab-go.yml) | `.gitlab-ci.yml` |

An **existing** project usually has lint findings already: start the linter with
`new-from-rev: origin/main` (GitLab: `new_from_rev` / `CIKIT_LINT_NEW_FROM_REV`) so it reports
only what each change adds, and fix the rest when convenient.

### GitHub

Pin a version: `@v1` follows compatible releases, `@v1.x.y` never moves.

```yaml
jobs:
  go:
    uses: Dmitry-Fedotov-Dev/ci/.github/workflows/go.yml@v1
    with:
      test-flags: -race -count=2

  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: Dmitry-Fedotov-Dev/ci/actions/go-lint@v1
      - uses: Dmitry-Fedotov-Dev/ci/actions/go-security@v1
```

On GitHub the actions install each tool at its pinned version (`go install`), so they do not
depend on the image.

### GitLab

Every GitLab job runs in the **cikit image** (`ghcr.io/dmitry-fedotov-dev/ci:v1`): all tools
are inside at pinned versions, nothing is downloaded per job, and the image tag is the version
of the kit. What GitLab shows on top of the log: test results in the merge request (JUnit),
coverage on the job, golangci-lint and gosec findings in the Code Quality widget (only new and
fixed ones), k6 and gosec summaries as merge request links (`expose_as`).

**Components** (GitLab 17+) — typed inputs, validated when the pipeline is created, listed in
the CI/CD Catalog. A component is included from a project on the same GitLab, so it needs a
mirror (below):

```yaml
include:
  - component: $CI_SERVER_FQDN/tools/ci/go@v1
    inputs:
      test_flags: -race -count=2
  - component: $CI_SERVER_FQDN/tools/ci/go-lint@v1
  - component: $CI_SERVER_FQDN/tools/ci/go-security@v1
```

Each component's inputs are at the top of [`templates/<name>.yml`](templates). Common to all:
`job` (the job name, to add one component twice), `stage`, `image`.

**Include templates** — any GitLab version, and straight from GitHub without a mirror:

```yaml
include:
  - remote: https://raw.githubusercontent.com/Dmitry-Fedotov-Dev/ci/v1/gitlab/ci.yml

go:
  extends: .cikit-go
  variables:
    CIKIT_GO_TEST_FLAGS: -race -count=2
lint:
  extends: .cikit-go-lint
security:
  extends: .cikit-go-security
```

Settings are `CIKIT_*` variables, documented in [`gitlab/ci.yml`](gitlab/ci.yml). A job given
an image without the scripts (`CIKIT_GO_IMAGE: golang:1.24` to test with exactly that Go)
clones this repository at `CIKIT_REF` instead; a job with its own `before_script` keeps ours
with `- !reference [.cikit, before_script]`.

**Inside a company GitLab** (runners without internet, an internal registry):

1. Mirror this repository into your GitLab, e.g. `tools/ci` (Settings → Repository → Mirroring,
   or a plain push). Its own [`.gitlab-ci.yml`](.gitlab-ci.yml) then selftests the templates and
   components on your runners. To list the components in the CI/CD Catalog, mark the project
   as a catalog project (Settings → General → Visibility → CI/CD Catalog project).
2. Mirror the image into your registry (a pull-through proxy, or `docker pull` + `docker push`)
   and point the kit at it: `image:` input for components, `CIKIT_IMAGE` for templates.
3. To build the image yourself behind a TLS-inspecting proxy, give the build the proxy's CA —
   it is used only while building and is not left in the image:
   `docker build --secret id=ca,src=corp-ca.pem -t registry.example.com/tools/ci:v1 .`
   The build needs no apt: everything is copied from official images.

### Locally, or in any other CI

```sh
docker run --rm -v "$PWD:/src" -w /src ghcr.io/dmitry-fedotov-dev/ci:v1 go-lint
docker run --rm -v "$PWD:/src" -w /src ghcr.io/dmitry-fedotov-dev/ci:v1 go-check --test-flags "-race -count=2"
# or without Docker: the scripts install pinned tools with go install when missing
git clone https://github.com/Dmitry-Fedotov-Dev/ci ~/ci && ~/ci/bin/go-security
```

Outside GitHub the summaries go to `ci-summary.md` (`CIKIT_SUMMARY` to change it).

## Steps

| Step | GitHub | GitLab component / template | Does |
|---|---|---|---|
| [`go-check`](bin/go-check) | [`go.yml`](.github/workflows/go.yml) (workflow) | `go` / `.cikit-go` | gofmt, go vet, go test; `--junit`, `--coverage` |
| [`go-lint`](bin/go-lint) | [`actions/go-lint`](actions/go-lint/action.yml) | `go-lint` / `.cikit-go-lint` | golangci-lint: the project's config or [the default](config/golangci.yml); `--new-from-rev` |
| [`go-security`](bin/go-security) | [`actions/go-security`](actions/go-security/action.yml) | `go-security` / `.cikit-go-security` | govulncheck (blocking), gosec (report unless `--gosec-fail`), summary, Code Quality report |
| [`xk6-build`](bin/xk6-build) | [`actions/xk6-build`](actions/xk6-build/action.yml) | `xk6-build` / `.cikit-xk6-build` | k6 with extensions: `--with module@version` or `module=.` for the checked-out repo |
| [`k6-summary`](bin/k6-summary) | [`actions/k6-summary`](actions/k6-summary/action.yml) | `k6-summary` / `.cikit-k6-summary` | Markdown from k6 JUnit reports (`functional`) or `--summary-export` (`load`); `--lang en\|ru` |
| [`inline-js`](bin/inline-js) | [`actions/inline-js`](actions/inline-js/action.yml) | `inline-js` / `.cikit-inline-js` | `node --check` for `.js` and inline `<script>` in `.html` |
| [`promtool`](bin/promtool) | [`actions/promtool`](actions/promtool/action.yml) | `promtool` / `.cikit-promtool` | `promtool check config` and alert rule unit tests |
| [`dashboards-sync`](bin/dashboards-sync) | [`actions/dashboards-sync`](actions/dashboards-sync/action.yml) | `dashboards-sync` / `.cikit-dashboards-sync` | generated Grafana dashboards match their generators |

Every script documents its flags in its header. One exception to "logic only in `bin/`": the
GitHub workflow `go.yml` runs gofmt/vet/test inline — a reusable workflow cannot locate its own
repository at the right version.

## Versions

- **The kit:** `@v1` (GitHub), `@v1` (components), `CIKIT_REF: v1` and the image tag `:v1`
  follow compatible releases; `v1.x.y` tags never move.
- **The tools:** pinned in [`versions.env`](versions.env) (govulncheck, gosec, golangci-lint,
  gotestsum, xk6, k6, actionlint, gitlab-ci-local) and as image tags in the
  [`Dockerfile`](Dockerfile). [Renovate](renovate.json) opens one grouped PR a week; selftest
  checks it before it can be merged. Nothing runs `@latest`: a CI that changes by itself turns
  red for no reason — exactly what happened with an unpinned xk6 before v1.1.
- **The image** is rebuilt weekly on `v1` to pick up the latest Go patch release: govulncheck
  reports the stdlib of the Go it runs with, so a stale image would flag long-fixed issues.

## Rules

- **Logic lives in `bin/`, never in a wrapper.** An action, a component or a template only maps
  its inputs to flags. A fix in `bin/` reaches GitHub, GitLab and laptops at once.
- **Every release passes two selftests** against `testdata/`, including the failure paths (bad
  JS, dashboard drift, a lint error, a bad flag must really fail):
  [GitHub](.github/workflows/selftest.yml) runs the actions and the scripts, builds the image
  and runs every GitLab template and component in it through
  [gitlab-ci-local](https://github.com/firecow/gitlab-ci-local);
  [`.gitlab-ci.yml`](.gitlab-ci.yml) is that GitLab selftest. The image is published only when
  all of it passes.
- **Breaking change → `v2`.** Renaming or removing an input, a flag or a `CIKIT_*` variable, or
  changing a default that changes a project's result. Projects move on their own schedule.
- **Release:** develop on `next` (its image is `:next`); point a project's branch at `@next`
  and let its CI pass together with selftest; then merge to `main`, move the `v1` **branch**
  (`git push origin main:v1`) and tag `v1.x.y` (Releases → Draft a new release). `v1` is a
  branch, not a tag: `uses: …@v1`, `component: …@v1` and `ref: v1` resolve either, and a
  branch moves forward without force-pushing.
- **Never name a variable `K6_*` or `XK6_*`**: k6 and xk6 read those as their own options.
  Ours start with `CIKIT_` (and `VER_` in versions.env).
- **GitLab: checks go in `script`, not `after_script`** — GitLab ignores `after_script` failures.

## Changes

- **v1.1** — golangci-lint step; GitLab CI/CD components; the cikit image (GitLab jobs run in
  it by default); every tool version pinned, Renovate. `CIKIT_PROMETHEUS_IMAGE` must now have
  bash (the cikit image does; plain `prom/prometheus` no longer fits).
- **v1.0** — shared steps for GitHub and GitLab, selftests.

License: MIT.
