#!/usr/bin/env bash
# Linux only: the fixture mounts exist only in a private mount namespace.
set -euo pipefail
if [[ ${1:-} != fixture ]]; then
    exec unshare --mount --propagation private bash "$0" fixture
fi
[[ $(readlink /proc/self/ns/mnt) != "$(readlink /proc/1/ns/mnt)" ]]
mount -t tmpfs tmpfs /opt
state=/opt/remnanode/.ham-xray/test
mkdir -p "$state"
touch /opt/remnanode/docker-compose.yml
cd "$(dirname "$0")/.."
python3() {
    [[ ${1:-} != -u ]] || shift
    case "$2" in
        install)
            [[ "$3 $4" == '--channel verified' ]] || return 1
            [[ ${SIMULATE:-} != error ]] || return 42
            printf '%s\n' PREPARED_STATE=/opt/remnanode/.ham-xray/test ;;
        *) return 1 ;;
    esac
}
export -f python3
output=$(printf '2\n2\n2\nY\n' | bash install.sh 2>&1)
[[ $output == *'Version pinned.'* && $output != *'tests pass?'* ]]
output=$(printf '1\n2\n2\nошибка\nДа\n' | bash install.sh 2>&1)
[[ $output == *'Введите Y'* && $output == *'Версия закреплена.'* ]]
output=$(printf '2\n2\n2\nN\n' | bash install.sh 2>&1)
[[ $output == *'Node unchanged.'* && $output != *PREPARED_STATE* ]]
if output=$(printf '2\n2\n2\nY\n' | SIMULATE=error bash install.sh 2>&1); then exit 1; fi
[[ $output == *'install.sh --status'* && $output != *'Version pinned.'* ]]
printf 'MAINTENANCE_MENU_PASSED\n'
