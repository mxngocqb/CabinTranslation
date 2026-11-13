"""Pull 6 QAIRT 2.50.0.260828 libs out of Qualcomm's 2.6 GB SDK zip with HTTP range reads; verify SHA-256.
usage: python fetch_qairt.py <out_dir>"""
import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = ("https://softwarecenter.qualcomm.com/api/download/software/sdks/"
       "Qualcomm_AI_Runtime_Community/All/2.50.0.260828/v2.50.0.260828.zip")
ROOT = "qairt/2.50.0.260828/lib/"
FILES = {  # pinned in google-litert-hackathon scripts/setup_npu.py
    "libQnnTFLiteDelegate.so": ("aarch64-oe-linux-gcc11.2/", "88d5ec6b722d21fc165a4519aa772822ab1b4e3a8548c3ed51046e2821aa9047"),
    "libQnnHtpPrepare.so": ("aarch64-oe-linux-gcc11.2/", "7c9a8a59ce090bb0766f5ff660809ef58e0a5e65d1c6ba46c7fa182f8d032682"),
    "libQnnHtp.so": ("aarch64-oe-linux-gcc11.2/", "823f764d434869919c7e01825ba76da7db828225525b0d27a4c21f4b2841e25b"),
    "libQnnSystem.so": ("aarch64-oe-linux-gcc11.2/", "65c1faa1c2175128fd3c3c8a8edb276e93520666afd9696977e947e6d7a3d1d2"),
    "libQnnHtpV75Stub.so": ("aarch64-oe-linux-gcc11.2/", "c9ca7044e946248ce8bbac85c54f720e9d732793fada9160ef82d037629e7046"),
    "libQnnHtpV75Skel.so": ("hexagon-v75/unsigned/", "2f6cfe5aae553d8ec88b6741bf8598a557375eacfc58056c2667fc43fda64f6a"),
}


class Remote(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        # the server answers HEAD with 403; a 1-byte range GET gives the size in Content-Range
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-0"}), timeout=60) as r:
            self.url, self.size = r.url, int(r.headers["Content-Range"].split("/")[-1])

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def readinto(self, b):
        if not len(b) or self.pos >= self.size:
            return 0
        end = min(self.pos + len(b), self.size) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            assert r.status == 206, r.status
            data = r.read()
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rf = Remote(URL)
    print("zip size", rf.size)
    z = zipfile.ZipFile(io.BufferedReader(rf, 1 << 20))
    for name, (folder, sha) in FILES.items():
        data = z.read(ROOT + folder + name)
        got = hashlib.sha256(data).hexdigest()
        if got != sha:
            sys.exit(f"SHA mismatch {name}: {got}")
        (out / name).write_bytes(data)
        print("ok", name, len(data))


if __name__ == "__main__":
    main()
