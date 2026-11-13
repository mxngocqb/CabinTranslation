#!/system/bin/sh
pid=$(pidof cabin_edge); [ -n "$pid" ] && kill $pid && echo "stopped $pid"
