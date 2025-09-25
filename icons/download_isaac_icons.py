# download_isaac_icons_strict.py
import os, re, sys, time, hashlib, subprocess
from urllib.parse import urlparse, urljoin
from typing import List, Tuple, Dict, Optional

# --- deps auto-install ---
def ensure_deps():
    try:
        import requests  # noqa
        from bs4 import BeautifulSoup  # noqa
    except Exception:
        print("[INFO] Installing required packages: requests, beautifulsoup4 ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4"])
ensure_deps()

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; IsaacIconFetcher/1.1; +https://bindingofisaacrebirth.fandom.com/)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
IMG_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://bindingofisaacrebirth.fandom.com/",
}

BASES = [
    ("https://bindingofisaacrebirth.fandom.com/wiki/Items",       "out/items_icons"),
    ("https://bindingofisaacrebirth.fandom.com/wiki/Trinkets",    "out/trinkets_icons"),
]

# --- utils ---
def slugify(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[\\/:*?\"<>|]", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^\w\-_\.]", "", text)
    return text or "unnamed"

def pick_best_img_src(img) -> str:
    # order: data-src -> src -> first srcset
    for key in ("data-src", "src"):
        url = (img.get(key) or "").strip()
        if url:
            return url
    srcset = (img.get("srcset") or "").strip()
    if srcset:
        first = srcset.split(",")[0].strip().split(" ")[0]
        if first:
            return first
    return ""

def normalize_url(url: str, page_url: str) -> str:
    if not url:
        return url
    if url.startswith("//"):
        url = "https:" + url
    if not bool(urlparse(url).netloc):
        url = urljoin(page_url, url)
    return url

def file_ext_from_url(url: str) -> str:
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
        return ext
    return ".png"

def safe_write(path: str, content: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)

def hash12(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]

def fetch(url: str, headers: Dict, retries: int = 3, sleep_sec: float = 0.7) -> requests.Response:
    last_exc = None
    for _ in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                return r
            time.sleep(sleep_sec)
        except Exception as e:
            last_exc = e
            time.sleep(sleep_sec)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Failed to GET {url}")

# --- table parsing helpers ---
def header_indices(tbl: BeautifulSoup) -> Dict[str, int]:
    """
    헤더 텍스트 -> 인덱스 매핑 (소문자 비교).
    우선 첫 번째 thead / 첫 번째 tr 의 th들 기준.
    """
    # thead 우선
    head_tr = None
    thead = tbl.find("thead")
    if thead:
        head_tr = thead.find("tr")
    if not head_tr:
        # tbody의 첫 tr이 헤더일 수 있음
        head_tr = tbl.find("tr")
    result = {}
    if not head_tr:
        return result
    ths = head_tr.find_all(["th", "td"], recursive=False)
    for i, th in enumerate(ths):
        label = (th.get_text(" ", strip=True) or "").strip().lower()
        result[label] = i
    return result

def find_col_index(hmap: Dict[str, int], keys: List[str]) -> Optional[int]:
    """
    헤더 맵에서 keys 중 하나를 포함(부분일치)하는 인덱스 찾기.
    """
    low_keys = [k.lower() for k in keys]
    # 정확히 일치 먼저
    for k in list(hmap.keys()):
        if k in low_keys:
            return hmap[k]
    # 부분 일치
    for k, idx in hmap.items():
        for want in low_keys:
            if want in k:
                return idx
    return None

def rows_excluding_header(tbl: BeautifulSoup) -> List[BeautifulSoup]:
    # thead가 있으면 tbody의 tr, 없으면 첫 tr 제외
    body = tbl.find("tbody")
    if body:
        trs = body.find_all("tr", recursive=False)
    else:
        trs = tbl.find_all("tr", recursive=False)
        if trs:
            trs = trs[1:]  # 첫 tr은 헤더로 간주
    # 공백/구분 행 제거
    clean = []
    for tr in trs:
        tds = tr.find_all(["td", "th"], recursive=False)
        if len(tds) == 0:
            continue
        clean.append(tr)
    return clean

def collect_icons_from_table(tbl: BeautifulSoup, page_url: str) -> List[Tuple[str, str]]:
    """
    주어진 wikitable에서 'Icon' 열의 이미지 + 'Name' 열 텍스트를 수집한다.
    """
    out = []
    hmap = header_indices(tbl)
    if not hmap:
        return out

    icon_idx = find_col_index(hmap, ["icon"])
    if icon_idx is None:
        return out  # Icon 열 없는 테이블은 스킵(인포박스/설명표 방지)

    name_idx = find_col_index(hmap, ["name", "item", "trinket"])  # Name 우선, 없으면 item/trinket

    for tr in rows_excluding_header(tbl):
        cells = tr.find_all(["td", "th"], recursive=False)
        if icon_idx >= len(cells):
            continue
        icon_cell = cells[icon_idx]

        # 같은 행에서 이름 추출
        name_text = ""
        if name_idx is not None and name_idx < len(cells):
            name_td = cells[name_idx]
            # a 태그 우선 -> 텍스트
            a = name_td.find("a")
            if a and (a.get("title") or a.get_text(strip=True)):
                name_text = (a.get("title") or a.get_text(strip=True)).strip()
            if not name_text:
                name_text = (name_td.get_text(" ", strip=True) or "").strip()

        # icon 셀의 img만 수집 (다른 열의 이미지는 무시)
        imgs = icon_cell.find_all("img")
        if not imgs:
            continue
        # 여러 개가 있더라도 보통 첫 번째가 아이콘
        img = imgs[0]
        src = pick_best_img_src(img)
        src = normalize_url(src, page_url)
        if not src:
            continue
        out.append((src, name_text))
    return out

def collect_table_imgs_strict(soup: BeautifulSoup, page_url: str) -> List[Tuple[str, str]]:
    """
    진짜 'wikitable' 클래스의 표들에서만, 그리고 'Icon' 열에서만 아이콘을 수집.
    """
    out = []
    tables = soup.select("table.wikitable")
    if not tables:
        # 더 이상 임의의 table로 fallback 하지 않음 (요청: 표 외부 금지)
        return out
    for tbl in tables:
        out.extend(collect_icons_from_table(tbl, page_url))
    return out

def unique_by_url(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen = set()
    uniq = []
    for url, name in pairs:
        key = url.split("?")[0]
        if key not in seen:
            seen.add(key)
            uniq.append((url, name))
    return uniq

def download_all(page_url: str, out_dir: str) -> Dict[str, int]:
    print(f"[INFO] Page: {page_url}")
    html = fetch(page_url, HEADERS).text
    soup = BeautifulSoup(html, "html.parser")
    pairs = collect_table_imgs_strict(soup, page_url)
    pairs = unique_by_url(pairs)

    print(f"[INFO] Found {len(pairs)} icon(s) strictly from Icon column in wikitables")
    ok = 0
    skipped = 0
    failed = 0

    for idx, (img_url, name) in enumerate(pairs, 1):
        ext = file_ext_from_url(img_url)
        base = slugify(name) if name else f"icon_{idx}"
        if not base or base.lower() in {"icon", "image", "file", "thumb"}:
            base = f"icon_{idx}"
        fname = f"{base}__{hash12(img_url)}{ext}"
        fpath = os.path.join(out_dir, fname)

        if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
            skipped += 1
            continue

        try:
            resp = fetch(img_url, IMG_HEADERS, retries=4, sleep_sec=0.8)
            safe_write(fpath, resp.content)
            ok += 1
            if ok % 20 == 0:
                print(f"[OK] {ok} saved ...")
            time.sleep(0.2)
        except Exception as e:
            failed += 1
            print(f"[FAIL] {img_url} -> {e}")

    return {"found": len(pairs), "saved": ok, "skipped": skipped, "failed": failed}

def main():
    total = {"found": 0, "saved": 0, "skipped": 0, "failed": 0}
    for url, outdir in BASES:
        os.makedirs(outdir, exist_ok=True)
        stats = download_all(url, outdir)
        print(f"[STATS] {url} -> {stats}")
        for k in total:
            total[k] += stats[k]
    print("\n[SUMMARY]")
    print(f"  Found : {total['found']}")
    print(f"  Saved : {total['saved']}")
    print(f"  Skipped(existing) : {total['skipped']}")
    print(f"  Failed: {total['failed']}")
    if total["failed"] == 0:
        print("작업 완료! Icon 열에서만 아이콘을 저장했어.")
    else:
        print("일부 실패가 있어. 위 [FAIL] 로그를 확인해줘.")

if __name__ == "__main__":
    main()
