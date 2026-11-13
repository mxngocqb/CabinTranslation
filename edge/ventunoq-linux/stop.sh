#!/bin/sh
# Stop the interpreter server started by start.sh
for p in $(pgrep -f "cabin_edge(_npu)? --config"); do kill "$p" 2>/dev/null; done
sleep 1
for p in $(pgrep -f "cabin_edge(_npu)? --config"); do kill -9 "$p" 2>/dev/null; done
for p in $(pgrep -f "https_proxy.py"); do kill "$p" 2>/dev/null; done
true
