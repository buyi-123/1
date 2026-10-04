"""黄果剧场 (huangguo.video) Python 点播爬虫（TVBox / 默影视，Chaquopy）

站点结构（2026-10-04 实测）：
- 列表/分类/搜索：/videos?category=1|2|3|4&tags=N&rating=N&q=xx&page=N，卡片 <article class="video-card">
- 二级筛选：tags（1=都市/2=人妻/4=同人/5=校园/6=职场/7=古风/8=乱伦/40=玄幻），
  rating（1=安全/2=裸露/3=限制级）
- 最新发布：/videos（不带 category）
- 视频详情：/video/xxx，播放地址在 data-hls（.../master.m3u8），海报在 data-poster
- 连续剧详情：/series/xxx，剧集列表在 data-episode-list 区域（"第N集" + /video/xxx）
- 卡片比例：aspect-[9/16] 竖版，style ratio 按站点实际取 0.56
- 播放链路：data-hls 是 master.m3u8（含 480p/720p/1080p 三个 variant，
  variant 地址带 ?n= 时间戳 token）。playerContent 里解析 master 挑最高清晰度 variant。

网络层：requests.Session 长连接优先（keep-alive），self.fetch() 兜底；
单次请求 10s 超时、失败重试 1 次。详情页连续剧不再逐集抓 HLS（N+1 改为 1+播放时解析）。

配置示例（放进 TVBox 主配置 "sites" 数组，把本文件放到 ./vod/ 目录）：
[
  {
    "key": "huangguo",
    "name": "黄果剧场",
    "type": 3,
    "api": "./vod/huangguo_spider.py",
    "lang": "zh-CN",
    "searchable": 1,
    "quickSearch": 1,
    "filterable": 1,
    "changeable": 0
  }
]
"""

import re
import json
from urllib.parse import quote, urlsplit

try:
    import requests
except Exception:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except Exception:  # 独立运行（本机校验）时兜底
    BaseSpider = object

BASE = "https://huangguo.video"
PAGE_SIZE = 20
# 第一个栏目 = 最新发布（映射到 /videos 不带 category）
CATEGORIES = [
    {"type_id": "latest", "type_name": "最新发布"},
    {"type_id": "1", "type_name": "MV音乐剧"},
    {"type_id": "2", "type_name": "短片"},
    {"type_id": "3", "type_name": "连续剧"},
    {"type_id": "4", "type_name": "片段"},
]
# 二级筛选（2026-10-04 实测：各分类情节标签各不相同；latest 取 16 标签并集）
# 尺度分级按用户要求默认全部，不做筛选
# 标签按每行 4 个拆成多个筛选维度：App 每个维度独占一行，超屏标签自然换行，无需横滑
_TAGS_BY_CAT = {
    "latest": [("都市", "1"), ("人妻", "2"), ("衍生", "3"), ("同人", "4"),
               ("校园", "5"), ("职场", "6"), ("古风", "7"), ("乱伦", "8"),
               ("NTR", "9"), ("穿越", "39"), ("玄幻", "40"), ("露出", "42"),
               ("女同", "55"), ("男同", "56"), ("欧美", "57"), ("二次元", "59")],
    "1": [("都市", "1"), ("人妻", "2"), ("校园", "5"), ("职场", "6"),
          ("NTR", "9"), ("露出", "42"), ("欧美", "57")],
    "2": [("都市", "1"), ("人妻", "2"), ("同人", "4"), ("校园", "5"),
          ("职场", "6"), ("古风", "7"), ("乱伦", "8"), ("NTR", "9"),
          ("穿越", "39"), ("玄幻", "40"), ("女同", "55"), ("男同", "56"),
          ("欧美", "57"), ("二次元", "59")],
    "3": [("都市", "1"), ("人妻", "2"), ("衍生", "3"), ("同人", "4"),
          ("校园", "5"), ("职场", "6"), ("古风", "7"), ("乱伦", "8"),
          ("NTR", "9"), ("穿越", "39"), ("玄幻", "40"), ("女同", "55"),
          ("男同", "56"), ("欧美", "57"), ("二次元", "59")],
    "4": [("都市", "1"), ("人妻", "2"), ("校园", "5"), ("职场", "6"),
          ("古风", "7"), ("乱伦", "8"), ("二次元", "59")],
}
_SORTS = [("最新发布", "newest"), ("最多播放", "views"), ("最多收藏", "favorites")]
_TAG_KEYS = ["tags", "tags2", "tags3", "tags4"]  # 多行标签维度 key，后行覆盖前行


def _chunk(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def _chunk_smart(tags):
    """按用户规则分行：每行4个标签；最后剩余≤5个放一行；剩余6个拆4+2（不留1个孤儿）。"""
    rows = []
    i, n = 0, len(tags)
    while i < n:
        rem = n - i
        if rem <= 5:
            rows.append(tags[i:])
            break
        if rem == 6:
            rows.append(tags[i:i + 4])
            rows.append(tags[i + 4:])
            break
        rows.append(tags[i:i + 4])
        i += 4
    return rows


FILTERS = {}
for _tid, _tags in _TAGS_BY_CAT.items():
    _dims = []
    # 标签多选（App 点已选中可再点取消，不选即全部，故不需要"全部"选项）
    # 分行规则：每行4个；最后剩余≤5个放一行；剩余6个拆4+2（不留1个孤儿）
    _rows = _chunk_smart(_tags)
    for _i, _ck in enumerate(_rows):
        _dims.append({
            "key": _TAG_KEYS[_i] if _i < len(_TAG_KEYS) else "tags%d" % (_i + 1),
            "name": "情节标签",
            "value": [{"n": n, "v": v} for n, v in _ck],
        })
    _dims.append({
        "key": "sort", "name": "排序",
        "value": [{"n": n, "v": v} for n, v in _SORTS],
    })
    FILTERS[_tid] = _dims
del _tid, _tags, _dims, _i, _ck
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

CARD_RE = re.compile(r'<article class="(?:video-card|search-content-card)[\s\S]*?</article>')
TITLE_RE = re.compile(r'<p class="[^"]*font-display[^"]*"[^>]*>([^<]*)</p>')
PIC_RE = re.compile(r'<img[^>]*src="([^"]*)"')
REMARK_RE = re.compile(r'bg-black/55[^>]*>([^<]*)<')
TAG_RE = re.compile(r'text-gold-dim[^>]*>([^<]*)<')
HREF_RE = re.compile(r'<a[^>]+href="([^"]*)"')
H1_RE = re.compile(r'<h1[^>]*>([^<]*)</h1>')
DESC_RE = re.compile(r'<meta name="description" content="([^"]*)"')
OGIMG_RE = re.compile(r'<meta property="og:image" content="([^"]*)"')
POSTER_RE = re.compile(r'data-poster="([^"]*)"')
HLS_RE = re.compile(r'data-hls="([^"]*)"')
TOTAL_RE = re.compile(r'(\d+)\s*集')
PAGER_RE = re.compile(r'href="[^"]*page=(\d+)"[^>]*>\s*(\d+)\s*<')
ANCHOR_RE = re.compile(r'<a[^>]+href="/video/([a-z0-9]+)"[\s\S]*?</a>')
STREAM_RE = re.compile(r'#EXT-X-STREAM-INF[^\n]*')


class Spider(BaseSpider):
    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}
        else:
            self.options = {}
        self._sess = None

    def getName(self):
        return "黄果剧场"

    # ---------------- 网络层：Session 长连接优先，self.fetch() 兜底 ----------------
    def _get_session(self):
        if self._sess is None and requests is not None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/json;q=0.9",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            self._sess = s
        return self._sess

    def _get(self, url, referer=None, timeout=10, retries=1):
        """同步 GET 文本：Session 长连接 + 1 次重试；失败回退 self.fetch()。"""
        headers = {}
        if referer:
            headers["Referer"] = referer
        last_err = None
        for attempt in range(retries + 1):
            try:
                s = self._get_session()
                if s is not None:
                    r = s.get(url, headers=headers or None, timeout=timeout,
                              allow_redirects=True)
                    if r.status_code == 200:
                        r.encoding = r.encoding or "utf-8"
                        return r.text
                    last_err = "http_%d" % r.status_code
                    continue
                # 无 requests 时走 self.fetch() 兜底（默影视 requests.get 包装）
                try:
                    r = self.fetch(url, headers=headers or None, timeout=timeout)
                    if r and getattr(r, "status_code", 0) == 200:
                        return r.text
                except Exception as e:
                    last_err = e
            except Exception as e:
                last_err = e
        return ""

    def _pick_variant(self, master_url):
        """解析 master.m3u8，挑最高清晰度 variant（绝对地址）；失败回退 master。"""
        try:
            txt = self._get(master_url, referer=BASE + "/")
        except Exception:
            return master_url
        if not txt or "#EXT-X-STREAM-INF" not in txt:
            return master_url
        base_dir = master_url.rsplit("/", 1)[0] + "/"
        lines = txt.splitlines()
        variants = []
        for i, line in enumerate(lines):
            if "#EXT-X-STREAM-INF" not in line:
                continue
            uri = ""
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    uri = lines[j].strip()
                    break
            if not uri:
                continue
            rm = re.search(r"RESOLUTION=(\d+)x(\d+)", line)
            res = int(rm.group(2)) if rm else 0
            bw = re.search(r"BANDWIDTH=(\d+)", line)
            bwv = int(bw.group(1)) if bw else 0
            variants.append((res, bwv, uri))
        if not variants:
            return master_url
        variants.sort(key=lambda x: (x[0], x[1]), reverse=True)
        uri = variants[0][2]
        if uri.startswith("http://") or uri.startswith("https://"):
            return uri
        if uri.startswith("/"):
            return BASE + uri
        return base_dir + uri

    def homeContent(self, filter):
        # 零网络：class + filters 全静态（阶段 3.6）
        result = {"class": list(CATEGORIES), "filters": dict(FILTERS)}
        return result

    def homeVideoContent(self):
        # 推荐置空：16 标签已在"最新发布"下，推荐页与之重复（阶段 3.6）
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend if isinstance(extend, dict) else {}
        try:
            return self._list(str(tid), pg, "", extend)
        except Exception as e:
            return {
                "list": [], "page": 1, "pagecount": 1, "limit": PAGE_SIZE,
                "total": 0, "msg": "分类加载失败：" + type(e).__name__,
            }

    def searchContent(self, key, quick, pg="1"):
        del quick
        try:
            # 全站搜索：站点实际搜索地址 /search?q=（/videos?q= 不是真搜索）
            url = "%s/search?q=%s" % (BASE, quote(str(key or "")))
            html_text = self._get(url, referer=BASE + "/")
            cards = [self._parse_card(b) for b in CARD_RE.findall(html_text or "")]
            cards = [c for c in cards if c]
            return {
                "list": cards, "page": 1, "pagecount": 1,
                "limit": len(cards), "total": len(cards),
            }
        except Exception as e:
            return {
                "list": [], "page": 1, "pagecount": 1, "limit": PAGE_SIZE,
                "total": 0, "msg": "搜索失败：" + type(e).__name__,
            }

    def _build_url(self, cat, pg, keyword, extend=None):
        extend = extend if isinstance(extend, dict) else {}
        if cat == "latest":
            url = "%s/videos" % BASE
        else:
            url = "%s/videos?category=%s" % (BASE, quote(cat))
        params = []
        # 多行标签多选：合并所有行的非空选择，逗号分隔（网站原生多选，需同时满足）
        # 行1的"全部"仅表示本行未选，不影响其他行
        tag_vals = []
        for k in _TAG_KEYS:
            v = str(extend.get(k, "") or "").strip()
            if v:
                tag_vals.append(v)
        if tag_vals:
            seen = set()
            uniq = []
            for tv in tag_vals:
                for part in tv.split(","):
                    p = part.strip()
                    if p and p not in seen:
                        seen.add(p)
                        uniq.append(p)
            if uniq:
                params.append("tags=" + quote(",".join(uniq)))
        sort = str(extend.get("sort", "") or "").strip()
        if sort and sort != "newest":
            params.append("sort=" + quote(sort))
        if keyword:
            params.append("q=" + quote(keyword))
        page = max(1, int(pg) if str(pg).isdigit() else 1)
        if page > 1:
            params.append("page=%d" % page)
        if params:
            sep = "&" if "?" in url else "?"
            url += sep + "&".join(params)
        return url

    def _list(self, cat, pg, keyword, extend=None):
        url = self._build_url(cat, pg, keyword, extend)
        html_text = self._get(url, referer=BASE + "/")
        cards = [self._parse_card(b) for b in CARD_RE.findall(html_text or "")]
        cards = [c for c in cards if c]
        return {
            "list": cards,
            "page": max(1, int(pg) if str(pg).isdigit() else 1),
            "pagecount": self._pagecount(html_text or ""),
            "limit": PAGE_SIZE,
            "total": len(cards),
        }

    @staticmethod
    def _clean(text):
        # P2：片名/集名里的 $ # 全角化，避免与分隔符冲突
        return str(text or "").replace("$", "＄").replace("#", "＃").strip()

    def _parse_card(self, block):
        href_m = HREF_RE.search(block)
        if not href_m:
            return None
        href = href_m.group(1)
        kind = "series" if href.startswith("/series/") else "video"
        code = href.rstrip("/").split("/")[-1]
        title_m = TITLE_RE.search(block)
        title = self._clean(title_m.group(1)) if title_m else ""
        pic_m = PIC_RE.search(block)
        pic = self._absolute(pic_m.group(1)) if pic_m else ""
        remark_m = REMARK_RE.search(block)
        remark = remark_m.group(1).strip() if remark_m else ""
        tags = TAG_RE.findall(block)[:3]
        return {
            "vod_id": "%s/%s" % (kind, code),
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark or "/".join(tags),
            "vod_class": "/".join(tags),
            "vod_type": "连续剧" if kind == "series" else "视频",
            # 站点卡片实际为 9/16 竖版，按网站实际取 0.56（P10 意图：比例正确不畸变）
            "style": {"type": "rect", "ratio": 0.56},
        }

    def _pagecount(self, html_text):
        pages = [int(n) for _, n in PAGER_RE.findall(html_text)]
        return max(1, max(pages)) if pages else 1

    def detailContent(self, ids):
        # P1：遍历 ids，不截断
        items = []
        for ident in ids or []:
            try:
                item = self._parse_detail(str(ident))
                if item:
                    items.append(item)
            except Exception:
                continue
        if not items:
            return {"list": [], "msg": "详情加载失败"}
        return {"list": items}

    def _parse_detail(self, ident):
        parts = str(ident).split("/")
        kind = parts[0]
        code = parts[1] if len(parts) >= 2 else ident
        item = {
            "vod_id": ident,
            "vod_name": "",
            "vod_pic": "",
            "vod_play_from": "黄果剧场",
            "vod_play_url": "",
        }
        if kind == "series":
            text = self._get("%s/series/%s" % (BASE, code), referer=BASE + "/")
            text = text or ""
            item["vod_name"] = self._clean(self._first(H1_RE, text))
            item["vod_pic"] = self._absolute(
                self._first(OGIMG_RE, text) or self._first(POSTER_RE, text)
            )
            item["vod_content"] = self._first(DESC_RE, text) or ""
            # 剧集只拼 /video/{code}，HLS 解析后移到 playerContent（详情 1 次请求，不再 N+1）
            ep_area = text
            m_area = re.search(r'data-episode-list[\s\S]*', text)
            if m_area:
                ep_area = m_area.group(0)
            urls = []
            seen = set()
            idx = 0
            for am in ANCHOR_RE.finditer(ep_area):
                ep_code = am.group(1)
                if ep_code in seen:
                    continue
                seen.add(ep_code)
                inner = am.group(0)
                lm = re.search(r'第\s*\d+\s*[集话]|正片|预告', inner)
                label = self._clean(lm.group(0).replace(" ", "")) if lm else ("第%d集" % (idx + 1))
                idx += 1
                urls.append("%s$/video/%s" % (label, ep_code))
            total_m = TOTAL_RE.search(text)
            if total_m:
                item["vod_remark"] = "全%s集" % total_m.group(1)
            item["vod_play_url"] = "#".join(urls)
        else:
            text = self._get("%s/video/%s" % (BASE, code), referer=BASE + "/")
            text = text or ""
            item["vod_name"] = self._clean(self._first(H1_RE, text)) or "正片"
            item["vod_pic"] = self._absolute(
                self._first(POSTER_RE, text) or self._first(OGIMG_RE, text)
            )
            item["vod_content"] = self._first(DESC_RE, text) or ""
            # 单视频：data-hls 直接从已抓页面提取，不再二次请求
            m = HLS_RE.search(text)
            master = self._absolute(m.group(1)) if m else ""
            item["vod_play_url"] = "正片$%s" % master if master else ""
        return item

    def playerContent(self, flag, id, vipFlags):
        del flag, vipFlags
        try:
            cur = str(id or "").split("#")[0]
            sep = cur.rfind("$")
            play_id = (cur[sep + 1:] if sep >= 0 else cur).strip()
            if not play_id:
                return {"parse": 0, "jx": 0, "url": "", "msg": "空播放地址"}
            # /video/xxx → 抓页面取 data-hls；已是 master 直链则直接用
            if "/video/" in play_id and "master.m3u8" not in play_id:
                code = play_id.rstrip("/").split("/")[-1]
                page = self._get("%s/video/%s" % (BASE, code), referer=BASE + "/")
                m = HLS_RE.search(page or "")
                if not m:
                    return {"parse": 1, "url": play_id,
                            "header": {"Referer": BASE + "/"}}
                master = self._absolute(m.group(1))
            else:
                master = self._absolute(play_id)
            # master -> 最高清晰度 variant，避免播放器不跟随 variant 导致黑屏
            playable = self._pick_variant(master)
            try:
                p = urlsplit(playable)
                ref = "%s://%s/" % (p.scheme, p.netloc) if p.netloc else BASE + "/"
            except Exception:
                ref = BASE + "/"
            return {
                "parse": 0,
                "jx": 0,
                "url": playable,
                "header": {"Referer": ref, "User-Agent": USER_AGENT},
                "format": "application/x-mpegURL",
            }
        except Exception as e:
            return {"parse": 0, "jx": 0, "url": "", "msg": "播放失败：" + type(e).__name__}

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return str(url or "").split("?")[0].lower().endswith(
            (".m3u8", ".mpd", ".mp4", ".mkv", ".flv")
        )

    def destroy(self):
        self.options = {}

    @staticmethod
    def _absolute(url):
        v = str(url or "").strip()
        if not v:
            return ""
        if v.startswith("http://") or v.startswith("https://"):
            return v
        if v.startswith("/"):
            return BASE + v
        return v

    @staticmethod
    def _first(regex, text):
        m = regex.search(text)
        return m.group(1) if m else ""
