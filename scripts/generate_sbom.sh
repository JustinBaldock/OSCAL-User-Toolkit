#!/usr/bin/env bash
# Regenerate sbom.json — a CycloneDX 1.6 Software Bill of Materials for the
# app's runtime dependencies (requirements.txt), including every transitive
# dependency with its resolved, installed version.
#
# Deliberately builds SBOM_VENV from a clean virtualenv containing ONLY
# requirements.txt, not the repo's regular dev environment — cyclonedx-bom
# itself (and anything else in requirements-dev.txt) must not leak into the
# SBOM as if it were part of the shipped application.
#
# PIP_VERSION is pinned explicitly (rather than using whatever pip a fresh
# `python3 -m venv` happens to bootstrap) because cyclonedx-py scans the
# whole venv, so pip itself becomes an SBOM component — an unpinned pip
# resolves to whatever version is ambient on the machine that runs this
# script, which drifted the CI check even with requirements.txt otherwise
# unchanged (24.2 locally vs 25.0.1 on a GitHub Actions runner vs 26.1.2
# on another machine, all on the same day).
#
# Usage: scripts/generate_sbom.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PIP_VERSION=26.1.2

SBOM_VENV="$(mktemp -d)/venv"
python3 -m venv "$SBOM_VENV"
"$SBOM_VENV/bin/pip" install --quiet "pip==$PIP_VERSION"
"$SBOM_VENV/bin/pip" install --quiet -r requirements.txt

python3 -m pip show cyclonedx-bom >/dev/null 2>&1 || {
    echo "cyclonedx-bom not installed — run: pip install -r requirements-dev.txt" >&2
    exit 1
}

cyclonedx-py environment "$SBOM_VENV/bin/python" \
    --mc-type application \
    --spec-version 1.6 \
    --output-reproducible \
    --output-file sbom.json

rm -rf "$(dirname "$SBOM_VENV")"
echo "sbom.json regenerated."
