"""Jable.tv VOD source."""

from __future__ import annotations

import re
import time
from urllib.parse import quote

from core.base import VodHandler, VodItem, VodDetailItem, VodListResult, HomeResult, PlayerResult
from core.http_client import HttpClient
from core.cache import TTLCache
from core import settings


class Jable(VodHandler):
    source_name = "jable"
    display_name = "Jable"

    HOST = "https://jable.tv"
    IMG_CDN = "assets-cdn.jable.tv"
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    # ── regex patterns ─────────────────────────────────────────────────

    _RE_VIDEO_BOX = re.compile(r'class="video-img-box[^"]*"', re.I)
    _RE_VIDEO_ID  = re.compile(r'href="(?:https://jable\.tv)?/videos/([^"/]+)/"', re.I)
    _RE_PIC       = re.compile(r'data-src="(https://assets-cdn\.jable\.tv/[^"]+)"', re.I)
    _RE_TITLE     = re.compile(r'class="title"[^>]*>([\s\S]*?)</h6>', re.I)
    _RE_HTML_TAG  = re.compile(r"<[^>]+>")

    _RE_HLS_VAR   = re.compile(r"var\s+hlsUrl\s*=\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", re.I)
    _RE_HLS_URL   = re.compile(r"(https?://[^\s\"'<>]+\.m3u8[^\s\"'<>]*)", re.I)

    _RE_CAT_ID    = re.compile(r'href="https://jable\.tv/categories/([^"/]+)[^"]*"', re.I)
    _RE_CAT_NAME  = re.compile(
        r'class="[^"]*absolute-center[^"]*"[^>]*>[\s\S]*?<h4[^>]*>([^<]+)</h4>', re.I,
    )

    _RE_OG_TITLE  = re.compile(
        r"(?:property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)[\"']"
        r"|content=[\"']([^\"']+)[\"'][^>]+property=[\"']og:title[\"'])", re.I,
    )
    _RE_OG_IMAGE  = re.compile(
        r"(?:property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)[\"']"
        r"|content=[\"']([^\"']+)[\"'][^>]+property=[\"']og:image[\"'])", re.I,
    )
    _RE_DATE      = re.compile(
        r'<span[^>]+class="[^"]*inactive-color[^"]*"[^>]*>\s*([^<]+)\s*</span>', re.I,
    )

    # ── init ───────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._new_http()
        self._cache = TTLCache(1800)

    def _new_http(self) -> None:
        doh_url = settings.DOH_URL if settings.USE_DOH else None
        self._http = HttpClient(headers={
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.9",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Referer": self.HOST + "/",
        }, timeout=settings.HTTP_TIMEOUT, doh_url=doh_url,
            proxy=settings.source_proxy(self.source_name) or None)

    # ── private helpers ────────────────────────────────────────────────

    def _get(self, url: str, recover: bool = True) -> str:
        """取页面。第一轮失败就重开会话再打一次。

        jable 的 Cloudflare 是三个站里最凶的：同一个 IP 连续请求容易被挑战,
        重开 session 往往能救回来。框架 HttpClient 没有 reset_session(),
        等效做法是 close 旧实例后重建。
        """
        html = self._http.get(url)
        if html or not recover:
            return html
        try:
            self._http.close()
        except Exception:
            pass
        self._new_http()
        return self._http.get(url)

    @classmethod
    def _proxy_pic(cls, url: str) -> str:
        if not url:
            return ""
        return url.replace("preview.jpg", "320x180/1.jpg") if "preview.jpg" in url else url

    def _parse_video_list(self, html: str) -> list[dict]:
        parts = self._RE_VIDEO_BOX.split(html)
        if len(parts) <= 1:
            return []
        items: list[dict] = []
        for block in parts[1:]:
            m = self._RE_VIDEO_ID.search(block)
            if not m:
                continue
            vid = m.group(1)
            pic = ""
            if pm := self._RE_PIC.search(block):
                pic = self._proxy_pic(pm.group(1))
            title = ""
            if tm := self._RE_TITLE.search(block):
                title = self._RE_HTML_TAG.sub("", tm.group(1)).strip()
            if not title:
                continue
            items.append(VodItem(vod_id=vid, vod_name=title, vod_pic=pic).to_dict())
        return items

    def _extract_hls(self, html: str) -> str:
        if m := self._RE_HLS_VAR.search(html):
            return m.group(1)
        if m := self._RE_HLS_URL.search(html):
            return m.group(1)
        return ""

    def _category_url(self, type_id: str, page: int) -> str:
        frm = f"{page:02d}"
        ts = int(time.time() * 1000)
        ajax = (
            f"?mode=async&function=get_block"
            f"&block_id=list_videos_common_videos_list"
            f"&sort_by=post_date&from={frm}&_={ts}"
        )
        prefix_map = {"cat:": "/categories/", "tag:": "/tags/", "top:": "/"}
        for prefix, segment in prefix_map.items():
            if type_id.startswith(prefix):
                return f"{self.HOST}{segment}{type_id[len(prefix):]}/{ajax}"
        return f"{self.HOST}/categories/{type_id}/{ajax}"

    def _fetch_categories(self) -> list[dict]:
        html = self._get(self.HOST + "/categories/")
        if not html:
            return []
        ids = self._RE_CAT_ID.findall(html)
        names = self._RE_CAT_NAME.findall(html)
        cats: list[dict] = []
        seen: set[str] = set()
        for cid, name in zip(ids, names):
            cid, name = cid.strip(), name.strip()
            if not cid or not name or cid in seen:
                continue
            seen.add(cid)
            cats.append({"type_id": f"cat:{cid}", "type_name": name})
        return cats

    # ── public API ─────────────────────────────────────────────────────

    def home(self) -> dict:
        if cached := self._cache.get("home"):
            return cached
        fixed = [{"type_id": "top:new-release", "type_name": "🎬 新片优先"}]
        classes = fixed + self._fetch_categories()
        lst = self._parse_video_list(self._get(self.HOST))
        result = HomeResult(classes=classes, list=lst).to_dict()
        self._cache.set("home", result)
        return result

    def category(self, type_id: str, page: str, ext: str = "") -> dict:
        pg = self.safe_int(page)
        lst = self._parse_video_list(self._get(self._category_url(type_id, pg)))
        return VodListResult(list=lst, page=pg, pagecount=pg + 1 if lst else pg).to_dict()

    def detail(self, ids: str) -> dict:
        results: list[dict] = []
        for vid in ids.split(","):
            vid = vid.strip()
            if not vid:
                continue
            html = self._get(f"{self.HOST}/videos/{vid}/")
            if not html:
                continue

            title = vid
            if m := self._RE_OG_TITLE.search(html):
                title = (m.group(1) or m.group(2)).strip()
            pic = ""
            if m := self._RE_OG_IMAGE.search(html):
                pic = m.group(1) or m.group(2)
            year = ""
            if m := self._RE_DATE.search(html):
                year = m.group(1).strip().removeprefix("上市於 ")

            results.append(VodDetailItem(
                vod_id=vid, vod_name=title, vod_pic=pic, vod_year=year,
                vod_play_from="Jable",
                vod_play_url=f"播放${self._extract_hls(html)}",
            ).to_dict())
        return {"list": results}

    def player(self, flag: str, play_url: str) -> dict:
        return PlayerResult(
            url=play_url,
            header={"User-Agent": self.UA, "Referer": self.HOST + "/"},
        ).to_dict()

    def search(self, keyword: str, page: str, ext: str = "") -> dict:
        pg = self.safe_int(page)
        kw = quote(keyword, safe="")
        if pg == 1:
            url = f"{self.HOST}/search/{kw}/"
        else:
            frm = f"{pg:02d}"
            ts = int(time.time() * 1000)
            url = (
                f"{self.HOST}/search/{kw}/"
                f"?mode=async&function=get_block"
                f"&block_id=list_videos_common_videos_list"
                f"&sort_by=post_date&from={frm}&_={ts}"
            )
        lst = self._parse_video_list(self._get(url))
        return VodListResult(list=lst, page=pg, pagecount=pg + 1 if lst else pg).to_dict()

    # ── 诊断 ───────────────────────────────────────────────────────────

    def diag_urls(self) -> list[tuple[str, str]]:
        return [
            ("home", self.HOST + "/"),
            ("categories", self.HOST + "/categories/"),
            ("category page1", f"{self.HOST}/categories/bdsm/"),
            ("detail", f"{self.HOST}/videos/mifd-735/"),
        ]