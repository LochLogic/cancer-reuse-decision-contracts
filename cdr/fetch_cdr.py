"""Download TCGA-CDR Table S1 from the GDC and verify it is the exact file analysed.

The table is not redistributed here. It is open access from the GDC PanCanAtlas
publications page (https://gdc.cancer.gov/about-data/publications/pancanatlas).
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

URL = "https://api.gdc.cancer.gov/data/1b5f413e-a8d1-4d10-92eb-7c4ae739ed81"
SHA256 = "ea594c0fbb6731477c7ac511fab449ca9c38b0d42d269591ed9f5c4090e75a5a"
OUT = Path(__file__).resolve().parent / "raw" / "TCGA-CDR-SupplementalTableS1.xlsx"


def main():
    OUT.parent.mkdir(exist_ok=True)
    data = urllib.request.urlopen(URL, timeout=120).read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        sys.exit("checksum mismatch: got %s, expected %s; the GDC file has changed" % (digest, SHA256))
    OUT.write_bytes(data)
    print("saved %s (%d bytes, sha256 verified)" % (OUT.name, len(data)))


if __name__ == "__main__":
    main()
