# -*- coding: utf-8 -*-
"""MissAV missav.ws —— TVBox T4 源。

数据源: https://missav.ws | 播放: surrit.com m3u8(Referer 防盗链)
取流:  playlist 直采 → Dean packer 解包 → uuid 拼 surrit(三段式)
       master 显式选最高分辨率变体(resolveHls)
CF:    直连失败走 1314/page 页面代理 + 多重试
搜索:  /cn/search/{kw} 主 + /search/{kw} 回退
⚠️ 通用 JAV 聚合站(与已维护 supjav 同类)。含麻豆传媒等分类。
"""
from __future__ import annotations

import gzip
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

_HOST = "https://missav.ws"
_PROXY_PAGE = "https://py.fzcrym.link:1314/page?u="
_PROXY_STREAM = "https://py.fzcrym.link:1314/stream?u="

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

_CATS = [
    ("cnsub", "中文字幕", "/dm278/cn/chinese-subtitle"),
    ("new", "最近更新", "/dm539/cn/new"),
    ("release", "新作上市", "/dm635/cn/release"),
    ("leak", "无码流出", "/dm817/cn/uncensored-leak"),
    ("today", "今日热门", "/dm301/cn/today-hot"),
    ("weekly", "本周热门", "/dm170/cn/weekly-hot"),
    ("monthly", "本月热门", "/dm273/cn/monthly-hot"),
    ("vr", "VR", "/cn/genres/VR"),
    ("siro", "SIRO", "/dm36/cn/siro"),
    ("luxu", "LUXU", "/dm34/cn/luxu"),
    ("gana", "GANA", "/dm34/cn/gana"),
    ("maan", "PRESTIGE", "/dm1004/cn/maan"),
    ("scute", "S-CUTE", "/dm38/cn/scute"),
    ("ara", "ARA", "/dm34/cn/ara"),
    ("fc2", "FC2", "/dm597/cn/fc2"),
    ("heyzo", "HEYZO", "/dm2208642/cn/heyzo"),
    ("tokyohot", "东京热", "/dm42/cn/tokyohot"),
    ("1pondo", "一本道", "/dm5199603/cn/1pondo"),
    ("caribbean", "Caribbeancom", "/dm7704788/cn/caribbeancom"),
    ("caribpr", "Caribbeancompr", "/dm91887/cn/caribbeancompr"),
    ("10musume", "10musume", "/dm7208981/cn/10musume"),
    ("pacopa", "pacopacomama", "/dm3600557/cn/pacopacomama"),
    ("gachinco", "Gachinco", "/dm150/cn/gachinco"),
    ("xxxav", "XXX-AV", "/dm42/cn/xxxav"),
    ("married", "人妻斩", "/dm37/cn/marriedslash"),
    ("nv4610", "顽皮4610", "/dm33/cn/naughty4610"),
    ("nv0930", "顽皮0930", "/dm37/cn/naughty0930"),
    ("madou", "麻豆传媒", "/dm63/cn/madou"),
    ("twav", "TWAV", "/dm31/cn/twav"),
    ("furuke", "Furuke", "/dm15/cn/furuke"),
    ("klive", "韩国直播", "/cn/klive"),
    ("clive", "中国直播", "/cn/clive"),
]
_CAT_MAP = {cid: path for cid, name, path in _CATS}


# ── 判定工具 ─────────────────────────────────────────────────────────

def _is_video_url(href):
    if not href or (not href.startswith("/") and not href.startswith("http")):
        return False
    path = re.sub(r"^https?://[^/]+", "", href.split("#")[0].split("?")[0]).rstrip("/")
    seg = path.split("/")[-1] if path else ""
    if not re.search(r"\d", seg):
        return False
    if re.match(r"^(page|genres|actresses|makers|search|playlists|labels|series)$", seg, re.I):
        return False
    if "/search" in path:
        return False
    return bool(re.match(r"^/(?:dm\d+/)?[a-z]{2}/[a-z0-9][a-z0-9-]*$", path, re.I))


def _code_of(url):
    slug = re.sub(r"[?#].*$", "", str(url)).rstrip("/").split("/")[-1] or ""
    m = re.match(r"^([a-z]+)-?(\d+)", slug, re.I)
    if m:
        return (m.group(1) + "-" + m.group(2)).upper()
    return slug.upper()


# ── HTTP(直连 + CF 页面代理) ─────────────────────────────────────────

def _http_get(url, timeout=20, retries=2, referer=None):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip",
    }
    if referer:
        headers["Referer"] = referer
    for _ in range(max(1, retries)):
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout,
                                          context=ctx)
            data = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
            return data.decode("utf-8", "replace")
        except Exception:
            time.sleep(1)
    return ""


def _is_cf(h):
    return (not h or len(h) < 2000 or
            "just a moment" in h.lower() or
            "cf-challenge" in h.lower() or
            "attention required" in h.lower())


def _http_get_proxy(url, timeout=30):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(_PROXY_PAGE + urllib.parse.quote(url, safe=""),
                                     headers={"User-Agent": _UA, "Accept": "text/html,*/*"})
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return resp.read().decode("utf-8", "replace")
    except Exception:
        return ""


def _fetch(url, ref=None, timeout=25):
    """先走 /page 页面代理(秒回,稳过 CF), 失败才直连兜底。
    代理侧自带 clearance+challenge 重试, 客户端无需重复多轮。"""
    h = _http_get_proxy(url, timeout=timeout)
    if h and not _is_cf(h) and len(h) > 3000:
        return h
    d = _http_get(url, timeout=15, retries=1, referer=ref or _HOST + "/")
    if d and not _is_cf(d):
        return d
    # 代理可能间歇慢, 最后再试一次代理
    h2 = _http_get_proxy(url, timeout=timeout)
    if h2 and not _is_cf(h2) and len(h2) > 3000:
        return h2
    return h2 if h2 else d


# ── 取流(三段式 + 最高分辨率) ────────────────────────────────────────

def _unpack_evals(raw):
    out = ""
    for m in re.finditer(r"}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)", raw, re.DOTALL):
        try:
            p = m.group(1).replace("\\'", "'").replace("\\\\", "\\")
            a = int(m.group(2)); c = int(m.group(3)); k = m.group(4).split("|")
            i = c
            while i:
                i -= 1
                if i < len(k) and k[i]:
                    p = re.sub(r"\b" + str(i) + r"\b", k[i], p)
            out += p + "\n"
        except Exception:
            pass
    return out


def _extract_stream(raw, uuid_hint=""):
    if raw:
        m = re.search(r"https?://[^\"'\s\\]+/[a-f0-9-]{36}/playlist\.m3u8", raw, re.I)
        if m:
            return m.group(0)
        up = _unpack_evals(raw)
        if up:
            m = re.search(r"https?://[^\"'\s\\]+/[a-f0-9-]{36}/playlist\.m3u8", up, re.I)
            if m:
                return m.group(0)
            m = re.search(r"https?://surrit\.com/([a-f0-9-]{36})/", up, re.I)
            if m:
                return "https://surrit.com/" + m.group(1) + "/playlist.m3u8"
            m = re.search(r"https?://[^\"'\s\\]+\.m3u8[^\"'\s\\]*", up, re.I)
            if m:
                return m.group(0).replace("\\/", "/")
    if uuid_hint:
        return "https://surrit.com/" + uuid_hint + "/playlist.m3u8"
    return ""


def _resolve_hls_best(master_url):
    try:
        txt = ""
        # surrit/fourhoi 直连可播(带 Referer); /stream 代理过不了 CF → 直接直连
        txt = _http_get(master_url, retries=1, referer=_HOST + "/")
        if not txt or "#EXT-X-STREAM-INF" not in txt:
            return master_url
        best_url, best_h = "", 0
        lines = txt.splitlines()
        for i, ln in enumerate(lines):
            if "#EXT-X-STREAM-INF" not in ln.upper():
                continue
            res = re.search(r"RESOLUTION=\d+x(\d+)", ln, re.I)
            h = int(res.group(1)) if res else 0
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith("#")):
                j += 1
            if j < len(lines) and h > best_h:
                best_h = h
                vurl = lines[j].strip().replace("&amp;", "&")
                if not vurl.startswith("http"):
                    vurl = urllib.parse.urljoin(master_url, vurl)
                if vurl.startswith(_PROXY_STREAM):
                    vurl = urllib.parse.unquote(vurl[len(_PROXY_STREAM):])
                best_url = vurl
        return best_url or master_url
    except Exception:
        return master_url


# ── 卡片 ─────────────────────────────────────────────────────────────

def _parse_cards(html):
    items = []
    seen = set()
    for part in re.split(r'class="thumbnail[^"]*"', html or "")[1:]:
        href = ""
        for m in re.finditer(r'<a[^>]+href="([^"]+)"', part):
            hh = m.group(1).replace("&amp;", "&")
            if hh.startswith("/") and _is_video_url(hh):
                href = hh
                break
            if hh.startswith("http") and "missav.ws" in hh and _is_video_url(hh):
                href = hh
                break
        if not href:
            continue
        if href.startswith("/"):
            href = _HOST + href
        if href in seen:
            continue
        seen.add(href)
        pic = ""
        m = re.search(r'<img[^>]+data-src="([^"]+)"', part)
        if not m:
            m = re.search(r'<img[^>]+src="([^"]+)"', part)
        if m:
            pic = m.group(1)
            if pic.startswith("data:"):
                m2 = re.search(r'<img[^>]+data-src="([^"]+)"', part)
                pic = m2.group(1) if m2 else ""
        title = ""
        m = re.search(r'<img[^>]+alt="([^"]+)"', part)
        if m:
            title = m.group(1)
        if not title:
            m = re.search(r'class="[^"]*text-secondary[^"]*"[^>]*>([^<]+)</a>', part)
            if m:
                title = m.group(1).strip()
        if not title:
            title = href.split("/")[-1]
        title = re.sub(r"\s*\d+\s*(?:分钟|分鐘|min|sec)\b.*$", "", title, flags=re.I).strip()
        uuid = ""
        m = re.search(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", part)
        if m:
            uuid = m.group(0)
        dur = ""
        m = re.search(r'class="[^"]*absolute[^"]*"[^>]*>([\d:]+)</span>', part)
        if m:
            dur = m.group(1)
        remark = _code_of(href)
        if dur:
            remark += " " + dur
        item = {"vod_id": href, "vod_name": title, "vod_pic": pic,
                "vod_remarks": remark}
        if uuid:
            item["_uuid"] = uuid
        items.append(item)
    return items


# ── 分页页数探测 ─────────────────────────────────────────────────────

def _max_page(html, pg, items, cap=500):
    mx = max(pg, 1)
    for p in re.findall(r"[?&]page=(\d+)", html or ""):
        try:
            mx = max(mx, int(p))
        except Exception:
            pass
    if mx > cap:
        mx = pg + 1 if items else pg
    return mx


class Missav(VodHandler):
    source_name = "missav"
    display_name = "MissAV"
    HOST = "https://missav.ws"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache = TTLCache(1800)

    # ── home ─────────────────────────────────────────────────────────

    def home(self) -> dict:
        classes = [{"type_id": cid, "type_name": name} for cid, name, _ in _CATS]
        lst = _parse_cards(_fetch(_HOST + "/dm539/cn/new"))
        for it in lst:
            it.pop("_uuid", None)
        return HomeResult(classes=classes, filters={}, list=lst).to_dict()

    # ── category ─────────────────────────────────────────────────────

    def category(self, type_id: str, page: str, ext: str = "") -> dict:
        try:
            path = _CAT_MAP.get(str(type_id), "/dm539/cn/new")
            pg = self.safe_int(page)
            url = _HOST + path if pg <= 1 else "%s%s?page=%d" % (_HOST, path, pg)
            html = _fetch(url)
            items = _parse_cards(html)
            if not items:
                html = _http_get_proxy(url)
                items = _parse_cards(html)
            for it in items:
                it.pop("_uuid", None)
            mx = _max_page(html, pg, items)
            return VodListResult(list=items, page=pg, pagecount=mx,
                                 limit=24, total=len(items)).to_dict()
        except Exception:
            return VodListResult(list=[], page=1, pagecount=1,
                                 limit=24, total=0).to_dict()

    # ── search ───────────────────────────────────────────────────────

    def search(self, keyword: str, page: str, ext: str = "") -> dict:
        try:
            pg = self.safe_int(page)
            kw = urllib.parse.quote(str(keyword or "").strip())
            suffix = "?page=%d" % pg if pg > 1 else ""
            urls = ["%s/cn/search/%s%s" % (_HOST, kw, suffix),
                    "%s/search/%s%s" % (_HOST, kw, suffix)]
            items, html = [], ""
            for u in urls:
                html = _fetch(u)
                items = _parse_cards(html)
                if items:
                    break
            for it in items:
                it.pop("_uuid", None)
            mx = _max_page(html, pg, items, cap=200)
            return VodListResult(list=items, page=pg, pagecount=mx,
                                 limit=24, total=len(items)).to_dict()
        except Exception:
            return VodListResult().to_dict()

    # ── detail ───────────────────────────────────────────────────────

    def detail(self, ids: str) -> dict:
        try:
            did = str(ids).split(",")[0].strip()
            url = did if did.startswith("http") else _HOST + "/" + did
            html = _fetch(url)

            title = ""
            m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            if m:
                title = m.group(1)
            if not title:
                m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
                if m:
                    title = m.group(1).strip()
            title = re.sub(r"\s*[|\-]\s*MissAV.*$", "", title).strip()

            pic = ""
            m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if m:
                pic = m.group(1)

            uuid_m = re.search(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", html)
            uuid = uuid_m.group(0) if uuid_m else ""
            stream = _extract_stream(html, uuid)

            models, tags = [], []
            for m in re.finditer(r'<div class="text-secondary[^"]*">([\s\S]*?)</div>', html):
                row = m.group(1)
                label_m = re.search(r"<span[^>]*>([^<]+)</span>", row)
                label = label_m.group(1).rstrip(":：") if label_m else ""
                links = re.findall(r'<a[^>]+href="([^"]*)"[^>]*>([^<]+)</a>', row)
                if re.search(r"女优|女優|Actress", label, re.I):
                    for h, n in links:
                        if "/actresses" in h and n.strip() and n.strip() not in models:
                            models.append(n.strip())
                elif re.search(r"类型|類別|Genre|Tag|标签|標籤", label, re.I):
                    for h, n in links:
                        if ("/genres" in h or "/tags" in h) and n.strip() and len(n.strip()) <= 16:
                            if n.strip() not in tags:
                                tags.append(n.strip())

            content = title
            if models:
                content += "\n\n女优: " + "、".join(models[:8])
            if tags:
                content += "\n标签: " + "、".join(tags[:12])

            code = _code_of(url)
            play_lines = []
            if stream:
                # 直链(带 Referer 由播放器携带), 不走 /stream 代理(surrit 被 CF 拦)
                play_lines.append("直链$%s" % stream)

            vod = {
                "vod_id": did,
                "vod_name": title or code or did,
                "vod_pic": pic,
                "vod_content": content,
                "vod_play_from": "MissAV",
                "vod_play_url": "#".join(play_lines),
                "vod_remarks": code,
            }
            return {"list": [VodDetailItem(**vod).to_dict()]}
        except Exception:
            return {"list": []}

    # ── player ───────────────────────────────────────────────────────

    def player(self, flag: str, play_url: str) -> dict:
        try:
            raw_url = str(play_url)
            if raw_url.startswith(_PROXY_STREAM):
                inner = raw_url[len(_PROXY_STREAM):]
                master = urllib.parse.unquote(inner)
            else:
                master = raw_url
            best = _resolve_hls_best(master)
            # surrit 直连全链可播(带 Referer); /stream 代理对 surrit 过不了 CF(返回拦截页)
            # → 直接给 TVBox 原始直链, 由播放器带 Referer 拉流
            return PlayerResult(url=best, header={"User-Agent": _UA,
                                                  "Referer": _HOST + "/"}).to_dict()
        except Exception:
            return PlayerResult(url=str(play_url)).to_dict()

    # ── 诊断 ─────────────────────────────────────────────────────────

    def diag_urls(self) -> list[tuple[str, str]]:
        return [
            ("最近更新", _HOST + "/dm539/cn/new"),
            ("中文字幕", _HOST + "/dm278/cn/chinese-subtitle"),
            ("搜索", _HOST + "/cn/search/FC2"),
            ("麻豆", _HOST + "/dm63/cn/madou"),
        ]