"""Small downloader that skips files already on disk."""

import shutil
import urllib.request
from pathlib import Path


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip {dest}")
        return
    print(f"get  {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "geont-bench/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response, open(tmp, "wb") as handle:
            shutil.copyfileobj(response, handle)
        tmp.replace(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    print(f"saved {dest} ({dest.stat().st_size} bytes)")
