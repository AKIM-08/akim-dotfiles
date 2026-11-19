#!/usr/bin/env bash
# meters.sh <cpu|memory|disk|battery> [color 1-7] - one colored usage bar for fastfetch
#
# Used by ~/.config/fastfetch/config.jsonc ("command" modules). Drawing the bars here instead of
# with fastfetch's own percent bars keeps them the same on every fastfetch version (its bar
# options were renamed in 2.50) and lets them use the terminal palette, which pywal fills from
# the wallpaper: the filled part is palette color N, the rest is the dim color 8.

what="${1:-}"
col="${2:-1}"
W=16

bar() {
    local p=$1 n i
    (( p < 0 )) && p=0
    (( p > 100 )) && p=100
    n=$(( (p * W + 50) / 100 ))
    printf '\e[3%sm' "$col"
    for (( i = 0; i < n; i++ )); do printf '■'; done
    printf '\e[90m'
    for (( i = n; i < W; i++ )); do printf '■'; done
    printf '\e[0m'
}

line() {   # line <percent> <detail>
    bar "$1"
    printf '  \e[1;97m%3s%%\e[0m  \e[90m%s\e[0m\n' "$1" "$2"
}

gib() { awk -v b="$1" 'BEGIN { printf "%.1f", b / 1073741824 }'; }

case "$what" in
    cpu)
        read -r _ a b c d e f g h _ < /proc/stat
        idle1=$(( d + e )); total1=$(( a + b + c + d + e + f + g + h ))
        sleep 0.25
        read -r _ a b c d e f g h _ < /proc/stat
        idle2=$(( d + e )); total2=$(( a + b + c + d + e + f + g + h ))
        dt=$(( total2 - total1 )); (( dt > 0 )) || dt=1
        line $(( (100 * (dt - (idle2 - idle1))) / dt )) "$(nproc 2>/dev/null || echo '?') threads"
        ;;
    memory)
        read -r total avail < <(awk '/^MemTotal:/ { t = $2 } /^MemAvailable:/ { a = $2 } END { print t, a }' /proc/meminfo)
        used=$(( (total - avail) * 1024 )); total=$(( total * 1024 ))
        line $(( used * 100 / total )) "$(gib "$used") GiB / $(gib "$total") GiB"
        ;;
    disk)
        read -r size used < <(df -P -B1 / 2>/dev/null | awk 'NR == 2 { print $2, $3 }')
        [ -n "$size" ] && [ "$size" -gt 0 ] || exit 0
        line $(( used * 100 / size )) "$(gib "$used") GiB / $(gib "$size") GiB"
        ;;
    battery)
        for b in /sys/class/power_supply/BAT*; do
            [ -r "$b/capacity" ] || continue
            status=$(tr '[:upper:]' '[:lower:]' < "$b/status" 2>/dev/null)
            line "$(cat "$b/capacity")" "${status:-unknown}"
            exit 0
        done
        printf '\e[90mno battery\e[0m\n'
        ;;
    *)
        echo "usage: meters.sh cpu|memory|disk|battery [color 1-7]" >&2
        exit 2
        ;;
esac
