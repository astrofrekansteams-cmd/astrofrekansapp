"""Download the JPL DE421 ephemeris kernel.

DE421 is public domain (NASA/JPL), ~16 MB, and covers 1900-2050 - enough for
every natal chart and forecast the product needs. Run once per environment;
the Docker image bakes it in at build time.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

URL = "https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de421.bsp"
MIN_BYTES = 10_000_000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", default="data/ephemeris", help="Target directory")
    parser.add_argument("--url", default=URL)
    args = parser.parse_args()

    destination = Path(args.dest)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "de421.bsp"

    if target.exists() and target.stat().st_size > MIN_BYTES:
        print(f"Ephemeris already present: {target}")
        return 0

    print(f"Downloading {args.url} -> {target}")
    urllib.request.urlretrieve(args.url, target)  # noqa: S310 - fixed JPL URL

    size = target.stat().st_size
    if size < MIN_BYTES:
        target.unlink(missing_ok=True)
        print(f"Download looks truncated ({size} bytes).", file=sys.stderr)
        return 1

    print(f"Done: {size / 1_048_576:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
