#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$root/lib/ui.sh"
task_tmp=$(mktemp -d)
trap 'rm -f -- "$task_tmp/settings" "$task_tmp/executed"; rmdir -- "$task_tmp"' EXIT
printf 'DOMAIN=$(touch %s/executed)\nSECRET_KEY=literal-value\nUNSUPPORTED=ignore\n' "$task_tmp" > "$task_tmp/settings"
load_saved_settings "$task_tmp/settings"
[[ ! -e "$task_tmp/executed" ]]
[[ $DOMAIN == '$(touch '* && $SECRET_KEY == literal-value ]]
[[ -z ${UNSUPPORTED:-} ]]
HAM_LANG=ru
[[ $(text русский English) == русский ]]
HAM_LANG=en
[[ $(text русский English) == English ]]
output=$(bash "$root/install.sh" --help)
[[ $output == *'interactive RU/EN'* ]]
printf 'UI_TESTS_PASSED: dotenv is data, whitelist, RU, EN, help\n'
