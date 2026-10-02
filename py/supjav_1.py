# -*- coding: utf-8 -*-
"""SupJav supjav.com —— TVBox T4 源。

数据源: supjav.com (WordPress supjav2 主题, Cloudflare 保护)
过盾:   页面全部走 1314/page(/fs) Playwright 真实浏览器 + challenge 重试
播放链: 详情 data-link(hex)
        → supjav.php?l=<hex>        (需 Referer=详情页)
        → 页内 OLID 反转
        → supjav.php?c=<reversed>   (需 Referer=step1)
        → TV 线路: 明文 m3u8 (turboviplay)
          FST 线路: packer 解包 → m3u8 (premilkyway)
        master m3u8 实测免 Referer 直连可播 → 代理转流给 TVBox

分类: supjav 顶部导航 Home/Popular/Censored/Uncensored/Amateur/Chn Sub/
      Reducing Mosaic/Eng Sub (Maker/Cast/Genre 是索引页不做分类)
⚠️ 成人内容站(有码/无码分类) —— 用户已在用(WebHome 版 /root/sj_api.py), 按既有约定维护。
"""
from __future__ import annotations

import base64
import codecs
import json
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request

from core.base import (
    VodDetailItem, VodHandler, VodItem, VodListResult, PlayerResult, HomeResult,
)
from core.cache import TTLCache

_HOST = "https://supjav.com"
_PROXY_BASE = "https://py.fzcrym.link:1314"
_FS_PAGE_API = _PROXY_BASE + "/fs?u="
_PAGE_API = _PROXY_BASE + "/page?u="
_STREAM_API = _PROXY_BASE + "/stream?u="
_SJ_HLS_API = _PROXY_BASE + "/sj_hls?u="
_SJ_IMG_API = _PROXY_BASE + "/sj_img?u="
_LK_BASE = "https://lk1.supremejav.com/supjav.php"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_CATS = [
    ("__home", "最新"),
    ("__popular", "热门"),
    ("censored-jav", "有码 Censored"),
    ("uncensored-jav", "无码 Uncensored"),
    ("amateur", "素人 Amateur"),
    ("chinese-subtitles", "中文字幕 Chn Sub"),
    ("reducing-mosaic", "破解 Reducing Mosaic"),
    ("english-subtitles", "英文字幕 Eng Sub"),
]

_SORTS = [
    {"key": "sort", "name": "排序",
     "value": [{"n": "最新", "v": ""}, {"n": "最多观看", "v": "views"}]},
]

_LINE_ORDER = {"VOE": 0, "ST": 10, "TV": 20, "FST": 90}


def _http_get(url: str, timeout: int = 90) -> str:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        return urllib.request.urlopen(req, timeout=timeout, context=ctx).read().decode("utf-8", "replace")
    except Exception:
        return ""


def _page(url: str, retries: int = 2) -> str:
    """站内页面走 /fs (clearance 快速通道 + FlareSolverr 兜底)。"""
    api = _FS_PAGE_API + urllib.parse.quote(url, safe="")
    for _ in range(max(1, retries)):
        html = _http_get(api, timeout=220)
        if html and "Just a moment" not in html and len(html) > 3000:
            return html
    api2 = _PAGE_API + urllib.parse.quote(url, safe="")
    html = _http_get(api2, timeout=90)
    if html and "Just a moment" not in html and len(html) > 3000:
        return html
    return ""


def _stream(url: str, referer: str = "", timeout: int = 90) -> str:
    api = _STREAM_API + urllib.parse.quote(url, safe="")
    if referer:
        api += "&r=" + urllib.parse.quote(referer, safe="")
    return _http_get(api, timeout=timeout)


def _cards(html: str) -> list[dict]:
    out, seen = [], set()
    blocks = re.split(r'<div class="post">', html or "")[1:]
    for b in blocks:
        m = re.search(r'href="' + re.escape(_HOST) + r'/(\d+)\.html"', b)
        if not m:
            continue
        vid = m.group(1)
        if vid in seen:
            continue
        t = re.search(r'title="([^"]+)"', b)
        title = t.group(1) if t else ""
        title = (title.replace("&amp;", "&").replace("&#8217;", "'")
                 .replace("&quot;", '"').replace("&#8211;", "-")).strip()
        if not title:
            continue
        seen.add(vid)
        pic = ""
        for pat in (r'<img[^>]+data-original="([^"]+)"',
                    r'<img[^>]+data-src="([^"]+)"',
                    r'<img[^>]+src="(https?://[^"]+)"'):
            pm = re.search(pat, b)
            if pm:
                pic = pm.group(1)
                break
        if pic.startswith("//"):
            pic = "https:" + pic
        if pic.startswith("http"):
            pic = _SJ_IMG_API + urllib.parse.quote(pic, safe="")
        code = ""
        cm = re.search(r'\b([A-Z]{2,6}-?\d{2,6}|FC2PPV[\s-]?\d{5,8})\b', title)
        if cm:
            code = cm.group(1)
        out.append(VodItem(vod_id=vid, vod_name=title[:90],
                           vod_pic=pic, vod_remarks=code).to_dict())
    return out


def _pagecount(html: str, cur: int) -> int:
    nums = [int(x) for x in re.findall(r"/page/(\d+)", html or "")]
    if not nums:
        return cur
    mx = max(nums)
    # 末页链接可能很大(有码分类 6455)。上限放宽到 200000, 仅拦明显异常值。
    return mx if 0 < mx <= 200000 else cur


def _unpack(text: str) -> str:
    """Dean Edwards packer 解包"""
    m = re.search(r"}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)", text, re.S)
    if not m:
        return ""
    payload, base, count, keys = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).split("|")
    try:
        payload = payload.encode().decode("unicode_escape")
    except Exception:
        pass
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"

    def enc(num):
        out = ""
        while num > 0:
            out = digits[num % base] + out
            num //= base
        return out or "0"

    table = {}
    for i in range(count):
        if i < len(keys) and keys[i]:
            table[enc(i)] = keys[i]
    return re.sub(r"\b\w+\b", lambda mm: table.get(mm.group(0), mm.group(0)), payload)


def _voe_decode(html: str) -> dict:
    """VOE 系混淆解包 → config dict"""
    m = re.search(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
                  html or "", re.S)
    if not m:
        return {}
    blk = m.group(1).strip()
    try:
        j = json.loads(blk)
        raw = j[0] if isinstance(j, list) and j else blk
    except Exception:
        raw = blk
    s = str(raw)
    for k in ("@$", "^^", "~@", "%?", "*~", "!!", "#&"):
        s = s.replace(k, "_")
    s = s.replace("_", "")

    def b64d(x):
        x = re.sub(r"[^A-Za-z0-9+/=]", "", x)
        x += "=" * (-len(x) % 4)
        return base64.b64decode(x).decode("utf-8", "replace")

    try:
        t = b64d(codecs.encode(s, "rot13"))
        t = "".join(chr(ord(c) - 3) for c in t)
        t = b64d(t[::-1])
        cfg = json.loads(t)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


class Supjav(VodHandler):
    source_name = "supjav"
    display_name = "SupJav"
    HOST = "https://supjav.com"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache = TTLCache(1800)
        self._play_cache = {}
        self._play_ttl = 90

    # ── 播放缓存 ─────────────────────────────────────────────────────

    def _play_cache_get(self, key):
        v = self._play_cache.get(key)
        if not v:
            return None
        if time.time() - v[0] > self._play_ttl:
            self._play_cache.pop(key, None)
            return None
        return v[1]

    def _play_cache_put(self, key, val):
        self._play_cache[key] = (time.time(), val)
        if len(self._play_cache) > 60:
            for k in sorted(self._play_cache,
                            key=lambda x: self._play_cache[x][0])[:20]:
                self._play_cache.pop(k, None)

    # ── home ─────────────────────────────────────────────────────────

    def home(self) -> dict:
        classes = [{"type_id": cid, "type_name": cname} for cid, cname in _CATS]
        filters = {}
        for cid, _ in _CATS:
            if not cid.startswith("__"):
                filters[cid] = _SORTS
        lst = _cards(_page(_HOST + "/"))[:24]
        return HomeResult(classes=classes, filters=filters, list=lst).to_dict()

    # ── category ─────────────────────────────────────────────────────

    def category(self, type_id: str, page: str, ext: str = "") -> dict:
        pg = self.safe_int(page)
        tid = str(type_id).strip()
        # ext 可能是 query-string(sort=views&...) 或 JSON 或空
        # 用 parse_qs 统一解析, 兼容两种
        extd = {}
        if isinstance(ext, dict):
            extd = ext
        elif ext:
            for k, v in urllib.parse.parse_qsl(str(ext)):
                extd[k] = v
        sort = str(extd.get("sort") or "").strip()

        if tid == "__home" and pg > 1:
            return VodListResult().to_dict()
        if tid == "__home":
            url = _HOST + "/"
        elif tid == "__popular":
            url = (_HOST + "/popular/" if pg == 1
                   else _HOST + "/popular/page/%d/" % pg)
        else:
            base = _HOST + "/category/" + tid
            url = base + ("/" if pg == 1 else "/page/%d/" % pg)
            if sort:
                url += "?sort=" + urllib.parse.quote(sort)

        html = _page(url)
        items = _cards(html)
        if not items:
            for _ in range(2):
                html = _page(url, retries=2)
                items = _cards(html)
                if items:
                    break
        return VodListResult(list=items, page=pg,
                             pagecount=1 if tid == "__home" else _pagecount(html, pg),
                             limit=len(items) or 24, total=len(items)).to_dict()

    # ── search ───────────────────────────────────────────────────────

    def search(self, keyword: str, page: str, ext: str = "") -> dict:
        pg = self.safe_int(page)
        kw = urllib.parse.quote(str(keyword or "").strip())
        url = (_HOST + "/?s=" + kw) if pg == 1 else (_HOST + "/page/%d/?s=%s" % (pg, kw))
        html = _page(url)
        items = _cards(html)
        if not items:
            for _ in range(2):
                html = _page(url, retries=2)
                items = _cards(html)
                if items:
                    break
        return VodListResult(list=items, page=pg,
                             pagecount=_pagecount(html, pg),
                             limit=len(items) or 24, total=len(items)).to_dict()

    # ── detail ───────────────────────────────────────────────────────

    def detail(self, ids: str) -> dict:
        vid = str(ids).split(",")[0].strip()
        vid = re.sub(r"\D", "", vid.split("/")[-1].replace(".html", "")) or vid
        durl = _HOST + "/" + vid + ".html"
        html = _page(durl)

        title = ""
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        if tm:
            title = re.sub(r"<[^>]+>", "", tm.group(1))
            title = (title.replace("&amp;", "&").replace("&#8217;", "'")
                     .replace("&#8211;", "-")).strip()

        pic = ""
        pm = re.search(r"background-image:\s*url\((https://img\.supjav\.com/[^)]+)\)", html)
        if pm:
            pic = pm.group(1)
        if not pic:
            im = re.search(r'(https://img\.supjav\.com/[^\s"\'<>)]+\.(?:jpg|jpeg|png|webp)[^\s"\'<>)]*)',
                           html, re.I)
            if im:
                pic = im.group(1)
        if pic.startswith("//"):
            pic = "https:" + pic
        if pic.startswith("http"):
            pic = _SJ_IMG_API + urllib.parse.quote(pic, safe="")

        views = ""
        vm = re.search(r'<span class="views">([^<]+)</span>', html)
        if vm:
            views = vm.group(1).strip()

        tags = []
        for _kind, slug in re.findall(r'href="' + re.escape(_HOST) + r"/(tag|actress)/([^\"\/]+)", html):
            s = slug.replace("-", " ").strip()
            if s and s not in tags:
                tags.append(s)
        year = ""
        ym = re.search(r"/images/(\d{4})/", html)
        if ym:
            year = ym.group(1)

        pairs = []
        seen_nm = {}
        for m in re.finditer(r'data-link="([0-9a-f]{40,})"[^>]*>\s*([^<]{1,20}?)\s*<',
                             html):
            lk, nm = m.group(1), m.group(2).strip()
            if not nm:
                nm = "线路%d" % (len(pairs) + 1)
            key = nm.upper()
            if key in seen_nm:
                continue
            seen_nm[key] = 1
            pairs.append((nm, "正片$%s|%s" % (vid, lk)))
        if not pairs:
            seen_lk = {}
            for lk in re.findall(r'data-link="([0-9a-f]{40,})"', html):
                if lk in seen_lk:
                    continue
                seen_lk[lk] = 1
                pairs.append(("线路%d" % (len(pairs) + 1), "正片$%s|%s" % (vid, lk)))

        def _rank(nm):
            return _LINE_ORDER.get(nm.strip().upper(), 50)

        pairs.sort(key=lambda x: _rank(x[0]))
        froms = [p[0] for p in pairs]
        urls = [p[1] for p in pairs]

        content = title
        if tags:
            content += "\n标签: " + ", ".join(tags[:10])

        vod = {
            "vod_id": vid,
            "vod_name": title or ("SupJav " + vid),
            "vod_pic": pic,
            "vod_year": year,
            "vod_remarks": views,
            "vod_content": content[:600],
            "vod_play_from": "$$$".join(froms) if froms else "SupJav",
            "vod_play_url": "$$$".join(urls) if urls else ("正片$%s|" % vid),
        }
        return {"list": [VodDetailItem(**vod).to_dict()]}

    # ── player ───────────────────────────────────────────────────────

    def _extract_stream(self, s2, ref):
        hits = re.findall(r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*', s2)
        if hits:
            return hits[0], ""
        if "eval(function(p,a,c,k,e" in s2:
            dec = _unpack(s2)
            hits = re.findall(r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*', dec)
            if hits:
                return hits[0], ""
        em = re.search(r"https?://streamtape\.com/e/([A-Za-z0-9]+)", s2)
        if em:
            eurl = "https://streamtape.com/e/%s/" % em.group(1)
            page = _stream(eurl, referer=_HOST + "/")
            for pat in (r"innerHTML\s*=\s*'([^']+)'\s*\+\s*\('([^']+)'\)"
                        r"\.substring\((\d+)\)",
                        r'innerHTML\s*=\s*"([^"]+)"\s*\+\s*\("([^"]+)"\)'
                        r"\.substring\((\d+)\)"):
                mm = re.search(pat, page or "")
                if not mm:
                    continue
                link = mm.group(1) + mm.group(2)[int(mm.group(3)):]
                if link.startswith("//"):
                    link = "https:" + link
                if "dl=" not in link:
                    link += ("&dl=1" if "?" in link else "?dl=1")
                return "", link
        tgt = re.findall(r"window\.location\.href\s*=\s*'([^']+)'", s2)
        tgt += re.findall(r"https?://[a-z0-9.-]+/e/[a-z0-9]{8,}", s2)
        if tgt:
            page = _stream(tgt[0], referer=ref)
            cfg = _voe_decode(page)
            src = str(cfg.get("source") or "")
            if ".m3u8" in src:
                return src, ""
            dau = str(cfg.get("direct_access_url") or "")
            if dau.startswith("http"):
                return "", dau
            if src.startswith("http"):
                return "", src
        return "", ""

    def player(self, flag: str, play_url: str) -> dict:
        raw = str(play_url)
        vid, _, lk = raw.partition("|")
        vid = re.sub(r"\D", "", vid) or vid
        detail = _HOST + "/" + vid + ".html"

        if not lk:
            return PlayerResult(url="").to_dict()

        cached = self._play_cache_get(lk)
        if cached:
            return cached

        s1_url = _LK_BASE + "?l=" + lk
        s1 = _stream(s1_url, referer=detail)
        olid = ""
        om = re.search(r"var\s+OLID\s*=\s*'([0-9a-f]{40,})'", s1 or "")
        if om:
            olid = om.group(1)[::-1]
        else:
            olid = lk[::-1]

        s2 = _stream(_LK_BASE + "?c=" + olid, referer=s1_url)
        if not s2:
            return PlayerResult(url="").to_dict()

        m3u8, direct = self._extract_stream(s2, s1_url)
        if not m3u8 and not direct:
            return PlayerResult(url="").to_dict()

        if direct:
            res = PlayerResult(url=direct, header={"User-Agent": _UA, "Referer": _HOST + "/"}).to_dict()
            self._play_cache_put(lk, res)
            return res

        m3u8 = m3u8.replace("\\/", "/").replace("&amp;", "&")
        low = m3u8.lower()
        if "turbosplayer" in low or "turboviplay" in low:
            play = _SJ_HLS_API + urllib.parse.quote(m3u8, safe="")
        else:
            play = _STREAM_API + urllib.parse.quote(m3u8, safe="")

        res = PlayerResult(url=play, header={"User-Agent": _UA, "Referer": _HOST + "/"}).to_dict()
        self._play_cache_put(lk, res)
        return res

    # ── 诊断 ─────────────────────────────────────────────────────────

    def diag_urls(self) -> list[tuple[str, str]]:
        return [
            ("首页", _HOST + "/"),
            ("有码", _HOST + "/category/censored-jav/"),
            ("搜索", _HOST + "/?s=FC2"),
            ("详情", _HOST + "/45156.html"),
        ]