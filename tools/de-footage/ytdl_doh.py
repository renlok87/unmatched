"""yt-dlp with a process-local DNS-over-HTTPS fallback.

The local router answers NXDOMAIN for youtube.com. When the system resolver
fails, this asks dns.google over HTTPS and hands the A records to the socket
layer. No system settings or hosts file are changed.
"""
import json
import socket
import sys
import urllib.request

_orig_getaddrinfo = socket.getaddrinfo
_cache = {}


def _doh(host):
    if host in _cache:
        return _cache[host]
    url = "https://dns.google/resolve?name=%s&type=A" % host
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.load(r)
    ips = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]
    _cache[host] = ips
    return ips


def _getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror:
        if not isinstance(host, str) or host.replace(".", "").isdigit():
            raise
        ips = _doh(host)
        if not ips:
            raise
        res = []
        for ip in ips:
            res.extend(_orig_getaddrinfo(ip, port, socket.AF_INET, type, proto, flags))
        return res


socket.getaddrinfo = _getaddrinfo

if __name__ == "__main__":
    import yt_dlp

    sys.exit(yt_dlp.main(sys.argv[1:]))
