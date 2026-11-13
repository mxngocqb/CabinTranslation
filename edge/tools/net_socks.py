#!/usr/bin/env python3
"""Count a process's TCP/UDP sockets connected to a non-loopback peer (evidence of no network use).

    python3 net_socks.py <pid>      -> prints an integer

Reads /proc/<pid>/fd (socket inodes) and /proc/<pid>/net/{tcp,tcp6,udp,udp6}; needs no `ss`/`netstat`
(Qualcomm Linux images ship neither reliably). Listening/unconnected sockets (peer 0.0.0.0 / ::) and
loopback peers (127.0.0.0/8, ::1, ::ffff:127.x) are not counted.
"""
import os
import sys


def main(pid: str) -> int:
    inodes = set()
    try:
        fds = os.listdir(f"/proc/{pid}/fd")
    except OSError:
        return 0
    for fd in fds:
        try:
            link = os.readlink(f"/proc/{pid}/fd/{fd}")
        except OSError:
            continue
        if link.startswith("socket:["):
            inodes.add(link[8:-1])
    n = 0
    for proto in ("tcp", "tcp6", "udp", "udp6"):
        try:
            lines = open(f"/proc/{pid}/net/{proto}").read().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            f = line.split()
            if len(f) < 10 or f[9] not in inodes:
                continue
            peer = f[2].split(":")[0].upper()
            if set(peer) <= {"0"}:                                   # listening / not connected
                continue
            if peer.endswith("7F") or peer == "00000000000000000000000001000000":   # 127.x (LE), ::ffff:127.x, ::1
                continue
            n += 1
    return n


if __name__ == "__main__":
    print(main(sys.argv[1]))
