# The cikit image: every tool the steps use, at the versions pinned in versions.env, plus the
# scripts themselves in /opt/cikit. GitLab jobs run in it with nothing to download per job;
# locally: docker run --rm -v "$PWD:/src" -w /src ghcr.io/dmitry-fedotov-dev/ci:v1 go-check
#
# No apt: every component is copied from its official image at a pinned tag (Renovate bumps
# them), so the build is reproducible and needs no Debian mirror — a company network often has
# a registry proxy but no apt access.
#
# Go is a current release: govulncheck checks against its stdlib, and the tools need it.
# GOTOOLCHAIN=auto lets a project whose go.mod asks for a newer Go fetch that toolchain.
#
# Behind a TLS-inspecting proxy (common in companies) give the build its CA; it is used only
# while building and does not end up in the image:
#   docker build --secret id=ca,src=corp-ca.pem -t cikit .

FROM golang:1.27-trixie AS go
FROM node:22-trixie AS node
FROM koalaman/shellcheck:v0.11.0 AS shellcheck
FROM prom/prometheus:v3.5.0 AS prometheus

FROM go AS tools
COPY versions.env /tmp/versions.env
# hadolint ignore=SC1091
RUN --mount=type=secret,id=ca,mode=0444 \
    if [ -f /run/secrets/ca ]; then export SSL_CERT_FILE=/run/secrets/ca; fi \
 && . /tmp/versions.env \
 && go install "golang.org/x/vuln/cmd/govulncheck@${VER_GOVULNCHECK}" \
 && go install "github.com/securego/gosec/v2/cmd/gosec@${VER_GOSEC}" \
 && go install "github.com/golangci/golangci-lint/v2/cmd/golangci-lint@${VER_GOLANGCI_LINT}" \
 && go install "gotest.tools/gotestsum@${VER_GOTESTSUM}" \
 && go install "go.k6.io/xk6@${VER_XK6}" \
 && go install "github.com/rhysd/actionlint/cmd/actionlint@${VER_ACTIONLINT}"

# python:3.12 (full Debian): python3 for the summaries, git, and gcc for go test -race
FROM python:3.14-trixie
COPY --from=go /usr/local/go /usr/local/go
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=shellcheck /bin/shellcheck /usr/local/bin/shellcheck
COPY --from=prometheus /bin/promtool /usr/local/bin/promtool
COPY --from=tools /go/bin/ /usr/local/bin/
COPY bin/ /opt/cikit/bin/
COPY lib/ /opt/cikit/lib/
COPY scripts/ /opt/cikit/scripts/
COPY config/ /opt/cikit/config/
COPY versions.env /opt/cikit/versions.env
ENV CIKIT_HOME=/opt/cikit \
    GOPATH=/go \
    PATH=/opt/cikit/bin:/go/bin:/usr/local/go/bin:$PATH \
    GOTOOLCHAIN=auto
LABEL org.opencontainers.image.source=https://github.com/Dmitry-Fedotov-Dev/ci \
      org.opencontainers.image.description="Portable CI kit: Go checks, lint, security, k6, monitoring checks" \
      org.opencontainers.image.licenses=MIT
