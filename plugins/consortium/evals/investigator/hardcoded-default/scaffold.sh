#!/usr/bin/env bash
exec "$(dirname "${BASH_SOURCE[0]}")/../../_fixtures/make_case_repo.sh" "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" "$PWD"
