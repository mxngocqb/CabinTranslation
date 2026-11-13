#!/usr/bin/env python3
"""HTTPS front for the on-board UI, so a phone/laptop on the same LAN can use the microphone.

Browsers only allow getUserMedia (microphone) on https:// or localhost. cabin_edge serves plain HTTP on
127.0.0.1:8080; this proxy listens on 0.0.0.0:8443 with a self-signed certificate (generated once into
./cert/) and forwards every request to 127.0.0.1:8080. Python 3 standard library only; no inference here.

    python3 https_proxy.py [--port 8443] [--backend http://127.0.0.1:8080]
Open https://<board-ip>:8443/ and accept the certificate warning once.
"""
import argparse
import http.client
import http.server
import os
import ssl
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))


def ensure_cert(d):
    crt, key = os.path.join(d, "cabin.crt"), os.path.join(d, "cabin.key")
    if not (os.path.exists(crt) and os.path.exists(key)):
        os.makedirs(d, exist_ok=True)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "825",
                        "-subj", "/CN=CabinTranslation", "-keyout", key, "-out", crt],
                       check=True, capture_output=True)
    return crt, key


def make_handler(backend):
    u = urllib.parse.urlparse(backend)

    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _forward(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else None
            hdr = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection")}
            c = http.client.HTTPConnection(u.hostname, u.port, timeout=120)
            try:
                c.request(self.command, self.path, body=body, headers=hdr)
                r = c.getresponse()
                data = r.read()
            except OSError as e:
                self.send_error(502, f"cabin_edge not reachable: {e}")
                return
            finally:
                c.close()
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = _forward

        def log_message(self, fmt, *args):
            sys.stderr.write("[https] %s %s\n" % (self.address_string(), fmt % args))

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--backend", default="http://127.0.0.1:8080")
    a = ap.parse_args()
    crt, key = ensure_cert(os.path.join(HERE, "cert"))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)

    class TLSServer(http.server.ThreadingHTTPServer):
        # The TLS handshake runs in the per-connection thread (not in accept()), with a timeout, so one
        # stalled client (browser pre-connect, plain http:// to this port, ...) cannot block the listener.
        daemon_threads = True
        request_queue_size = 64

        def finish_request(self, request, client_address):
            try:
                request.settimeout(15)
                tls = ctx.wrap_socket(request, server_side=True)
                tls.settimeout(130)
            except (ssl.SSLError, OSError):
                request.close()
                return
            self.RequestHandlerClass(tls, client_address, self)

    srv = TLSServer(("0.0.0.0", a.port), make_handler(a.backend))
    print(f"https proxy on https://0.0.0.0:{a.port}/ -> {a.backend}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
