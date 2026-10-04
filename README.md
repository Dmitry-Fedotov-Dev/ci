# ci

Shared GitHub Actions for [xk6-sip](https://github.com/Dmitry-Fedotov-Dev/xk6-sip) and
[kontakt](https://github.com/Dmitry-Fedotov-Dev/kontakt): one place for the Go checks, the k6 build
with xk6-sip, the k6 result summaries and the monitoring checks. Project-specific jobs (call
scenarios against a running station, load runs, cross-builds) stay in the projects.

## Use

Always pin a version: `@v1` follows compatible releases, `@v1.0.0` never moves.

```yaml
jobs:
  go:
    uses: Dmitry-Fedotov-Dev/ci/.github/workflows/go.yml@v1
    with:
      test-flags: -race -count=2

  k6:
    runs-on: ubuntu-latest
    steps:
      - uses: Dmitry-Fedotov-Dev/ci/actions/xk6-build@v1
        with:
          with: github.com/Dmitry-Fedotov-Dev/xk6-sip@v0.4.0
      - uses: actions/upload-artifact@v7
        with: { name: k6, path: bin/k6 }

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: Dmitry-Fedotov-Dev/ci/actions/go-security@v1
```

## What is here

| | Kind | Does |
|---|---|---|
| [`.github/workflows/go.yml`](.github/workflows/go.yml) | reusable workflow | gofmt, go vet, go test (`go-version-file`, `go-version`, `working-directory`, `packages`, `test-flags`, `gofmt`) |
| [`actions/xk6-build`](actions/xk6-build/action.yml) | action | k6 with extensions: `with` (one per line, as `xk6 --with` takes them; `module=.` for the checked-out repo), `k6-version`, `output` → output `path` |
| [`actions/k6-summary`](actions/k6-summary/action.yml) | action | Markdown summary on the run page and in the log: `kind: functional` from JUnit reports (`reports`, `scenarios`), `kind: load` from `--summary-export` (`reports`, `title`, `note`); `lang: en\|ru`; `output` for the artifact |
| [`actions/go-security`](actions/go-security/action.yml) | action | govulncheck (blocking) and gosec (report unless `gosec-fail: true`), gosec summary on the run page, `gosec.json` |
| [`actions/inline-js`](actions/inline-js/action.yml) | action | `node --check` for `.js` files and inline `<script>` blocks in `.html` under `paths` |
| [`actions/promtool`](actions/promtool/action.yml) | action | `promtool check config` and alert rule unit tests from the project's Prometheus image |
| [`actions/dashboards-sync`](actions/dashboards-sync/action.yml) | action | generated Grafana dashboards match their generators (`pairs`: `<generator.py> <committed.json>` per line) |

Scripts the actions run live in [`scripts/`](scripts) and work locally too:
`python3 scripts/summary.py --lang ru load summary.json "title"`, `python3 scripts/check_js.py web/static`.

## Rules

- **Breaking change → new major tag.** Renaming or removing an input, or changing a default that
  changes a project's result, means `v2`. Projects move to it on their own schedule.
- **Every release passes [selftest](.github/workflows/selftest.yml)** against `testdata/`: the Go
  workflow, a real k6 build with xk6-sip, both summaries, and the failure paths (bad JS, dashboard
  drift) are checked to really fail.
- **Release:** develop on a branch (e.g. `next`); point a project's branch at `@next` and let its CI pass
  together with selftest; only then merge to `main`, move the `v1` **branch** to it
  (`git push origin main:v1`) and tag the release `v1.x.y` (Releases → Draft a new release).
  `v1` is a branch, not a tag: `uses: …@v1` resolves either, and a branch moves forward without force-pushing.
- Do not use `xk6`'s environment names (`K6_VERSION`, `XK6_*`) for your own variables: xk6 reads them as its flags.

License: MIT.
