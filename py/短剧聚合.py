# -*- coding: utf-8 -*-
"""
@header({
  searchable: 2,
  filterable: 1,
  quickSearch: 1,
  title: '短剧库',
  '类型': '短剧',
  lang: 'ds'
})
"""

# 本资源来源于互联网公开渠道，仅可用于个人学习爬虫技术。
# 严禁将其用于任何商业用途，下载后请于 24 小时内删除，搜索结果均来自源站，本人不承担任何责任。

from base.spider import Spider
import sys, json, base64, gzip, urllib3
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')


class Spider(Spider):

    host = 'http://127.0.0.1:8998'
    headers = {
        'User-Agent': 'MOBILE_UA'
    }

    class_name = '红果&围观&河马&山海&好看&百度&星芽&七猫&大芒&西饭&星星&薏米&悟圣&七星&酷我&牛牛&喜福&爽爽&五五&黄豆&黄豆2&黄果&黄果2&黄果旧版&黄剧&野果&51短剧&橙果&香蕉&黄瓜&狂飙&91短剧&2048短剧&短剧one'
    class_url = 'hongguo&weiguan&hema&shanhai&haokan&baidu&xingya&qimao&damang&xifan&xingxing&yimi&wusheng&qixing&kuwo&niuniu&xifu&shuang&wuwu&huangdou&huangdou2&huangguo&huangguo2&huangguoold&huangju&yeguo&dj51&chengguo&xiangjiao&huanggua&kuangbiao&dj91&md2048&duanjuone'

    # 平台名表：顺序与 class_name / class_url 一致
    plat_names = {
        'hongguo': '红果', 'weiguan': '围观', 'hema': '河马', 'shanhai': '山海',
        'haokan': '好看', 'baidu': '百度', 'xingya': '星芽', 'qimao': '七猫',
        'damang': '大芒', 'xifan': '西饭', 'xingxing': '星星', 'yimi': '薏米',
        'wusheng': '悟圣', 'qixing': '七星', 'kuwo': '酷我', 'niuniu': '牛牛',
        'xifu': '喜福', 'shuang': '爽爽', 'wuwu': '五五', 'huangdou': '黄豆',
        'huangdou2': '黄豆2', 'huangguo': '黄果', 'huangguo2': '黄果2',
        'huangguoold': '黄果旧版', 'huangju': '黄剧', 'yeguo': '野果',
        'dj51': '51短剧', 'chengguo': '橙果', 'xiangjiao': '香蕉',
        'huanggua': '黄瓜', 'kuangbiao': '狂飙', 'dj91': '91短剧',
        'md2048': '2048短剧', 'duanjuone': '短剧one'
    }

    # gzip + base64 的 filter 定义
    filter_def = 'H4sIAAlpumoC/61a21MTzRL/X3iWktzBp+OjD6fqPPly6qtTC4nJYrLBXAT8yir4Qrgol0QQQSLIRS5CkAhqIET+mZ3dzX9xerOzMz2bJRChCq2a6d6Znu5f32byd1csqUSj2WTXo//+3fU8Mtr1qGtAynQ96FKkRAQGZHpSr9Rg/FKKZyNNLgWmtbGanitr78rabskkwlRKUp53x5KZrtcPLB69tKFeXJCZPQdPKiLFGZN2edjKMZBMyAOM5fGTVg5Jbt3GpsPy3eGUlJAcm1B6c3EHQ3MLSpdkm/jX678edA1H5GhWUjrUD8nvN3L79orxOF0sFoF1O1tJ//67MTZDVxqUleiIKY0tOFnYMbbzlBrNvooBMcqojak5fWnDPrdp6XQsgujk+Ce5KLO1pYyMiNr4W326QolxWVJMnTdPkY5JSgxG93kQMKF2ssRMqLzgBtaWT7h1RmRlMMttv1Qix58pKQMyNg/Jzz82aWzZ51PkEb4mubwwxvJkbZ3U31H6C/g8+ioW4Txfpsh5jVFjgt535tTaFKU9y8K2XCi1WiZrdW1rl5JfURdL3Kx6CyRS8nnHgLO8EXtBfzIMEiNltdGjNr2if1ln8kqKiROu5S/rRuUrpZoUkBATyWwNEUfl25rH+LFCDq7Yrll5BFn24Mr4+cYBYDjPaBYZ6PIfI1en1FFZwfo1VgsAYNv02YgJYKT8Q235AznOw/+274BgYWREfX6CG99EqmX+poH6JTmcvUtAeAFr9WdvpcJGrk6q/1BaOJuOIe3On6i1bWN/TMvlmVUlJSzJoxL4DwZbG0Vd7yM3WA9SgLE9blsPKAMoKBuFWXL8iRJN4PcjyLRH2/XGAVZZsFE7XLYFQOPDV3LwkX1pWle5yfQ3A9Mtwp6fgY2YdpvWccQA9XJXL0yKkSCeVeIyDvJOQ0ezLmbWyrvq78/wvzazSPmGswCJYWC+ldM1Pr3TVr5onzfJWpnFPTAsaAeWSY5yF4DwER3tNJVB9CGlC/ukEDRxrrpFAFMvP5LiilpdVC8OKRfIP4qto61sQJIhX+pCpBNTTZs42Fg5JfkZQU5QcjRqZdXmyV/ICanjaml+35gr0AV73AXp9jh8HoytTdgQ83hDPvekDxSve7QIhDwOTKu1VQAI+7A36J7rAiEuo3q+qX0q2oQ+JPxJEbIc+8LnDvkAFq4VXSBDrwO+lOLDwu8VkXB9fv5F6VCtLtuEQBBVE7Pa0SbJ5/g+fe4Rz9/T43BtJoDPPduH+gL8i9OaXrNtFOoNcck+5YyTt+yLHveSLNTrRxY41cb2tOlC4/0VkxqfdWbRmKiaUa1qKzfkCbpHNH9vT7tKx9/DjWJc1cluTR8/NIpHHPQhT8C9UgkiaDQOjvSl70z73JDG+Cxayut3hHZbwX6u4MbhijbzVq2+JZUKPzw3GdmvqOcFbWUe/JvTA+4JLuQNoR3zeEd+bm3tymBRJOTxYhCo53bp5vPxU5H3k5C42B4+BE8w6YleWwAOLpwHhS0U4IGCvtz5DTHN+PapsbXC6VzDxtQZ+TZrW62PC0nGf5HCEbnKke0T9iG2wERRO7MzbMDLYQL5svFhX0jdQWQgIW37kEMJKTuAFAzdFxmfInO5xpQdJXqRNoVs4wu6lzweb7DPPan7kCVPFqBH0GcOuKJQ+Frb4qVKwM+BoR1tkeUSmdwBFNt6DApOR6r2eYMevltj8SdZKPKtkBz5H/q87dneXvd6AzmmUEV5OSq0f470ZXsHpFCtsK4fFVnkQGAZ/wEw5wEtRBNSGHpVyE4dtgvTFV5MSLJQRrQpOdu3m0KF0lKDtummrBZe3xtjZUlEgR5wRM66q8tM57jNqBd5Hh0GiQadJY2jmGFFzLN7aOxv1to1MnRcxlvOa1c+ktlQohS1B2BWq7aGw5LyEsxzizLfJbGEJbNaNgtayT058laMVYPmv3u9EYCCkJ82FcGHdavgmoKMyon7vZZoc4PQ5gbA9erktncyCzuN7XnmYs8wrV2j2Nb52oCznWOR+Umy8J2do/mZdSmWtYTuUNU4FFoRzE3NQlEIKDA2x9zKOMtv3NKm1S8JqZiW7n8AUqEZ8LhD0OfoYuyo7mhL7KDuaDfstEWlfJ4d7rS/0GdLav2zljvVSywDIXVAii6eChHfgw6ydkZ2PoIXkDpPrVzCUrUxvmjVC/rHCTNKM/B6fI40T+qLwGxT/fj6Ff6sStP49c1mcJaYYsMTpOpQ5Cz83SVKY8SAl9BZOsCZjdHowNUN6MDVs+iAdyHfucrpwPWSgQ5cMU8HTBaoZhju6MDVlemAfTe5pl7Y4KADXtL8VGvL5iU7k1aYYtky23GVUXd1EhwHgu5BINAuP3rc1e93167X1+4mhQEtbRUz9wE0yMSNraKQBYQpsUwXzCZMiS21kIGFKbE8E7p8YUpUqaA7YYqvN2fUj9hKzQFbY7quLdv5jw4YbQNd5NCBnTiG7+TLdMCR9Au0am9kDUQjCOq/ldcKlRAdsDXfVMiV3U7SgSt86cA1qdOBayFBB669Nx3cyttxsU0H9HHBBLl5idrxex9/gRPK3vKStnTOaYlkFBU7WqGkn21xajoipQZinLz00/iwwMnPpJfJlJxBN/zHs3ptETHIClQhjqN4OzxLY3e5sfnDLqOhikbPgAJyzZdA8Qby8RPhKREYEuITy26JzL1HD5VQb6SxuJ2/tFr1qXCDmIoMJBNQD4fRRdiYcVVUq2+gLLGL1chwJJ25v6MBfW4LGgVONw8k3Ko/fmKhAS0hoMHtxTj9ED8ZW8d0crict14ib9acfEPJTETJyFLcoXHvffV4xtW6Xiu7pbR/P33Y2DhVzwuc6MHhUJ+ZaikKYU47/tGSuyxbQlnGbZkdCkuZSBqp6Z2xOSseH70f0mMn4+FOPaM2oa2XyPwGmV6z332k/u4eDILpglkEYiyZLJ4WFgFNJov3OpyYRB+WfbDj6FQa48r6FyDfbgcjf/DLBuxp9hXLYMBzl4Bp2gfb12oeeFvRlJiSAx6H/qOP2NQ1zmzysCl+Y2daAXHQCV7UOnax92ieeMBs7zpXnrCo+TAz4PhBAra7I1VgvIihx7oeEu+Grg9sjrgmOHN/Kjmc5rcWJtZk6R4iMo5h1oaCfTOxCPhvCrWD5kW2EE9h40fCNFuuXjH2JgXFmbzCNC9P9s1eq1rVphcwL55u944JvMK0+MwhXLI3efE0a3qapaZ6dQxWQ7zCtFivCm8lTXnxtBDTpLs4c2sauQNcHenSDbACLu8Ftg9cwp1F6+ZB77l5hP4/gLUQUroDgyMDMsrM5W1jb0LgUZKphBT/XzqWTGUcYUc8Wzgbz9hsNJ72ee4infOHLTdZosUMiMP0ItYmpGPykKw48iylDUmy8GDtsKCpcfMnRI+4KZtnTYS9Pf7eDk/rWBs+6faiB8yLmlGZtMD7+AniCTpY1MvP5Os7xMDX0Kp5/eIbOSlCZ4QY0J3O46dqtQxdHSl/IOfvsSTo2aWuXuwZU1+1t3N4EaTALQO6pJ09/nhkMvBip8/TQgzhq1KysG2c5LT3q3h51Oev1o3VeXJ4QHbPsYRe528szivq5S7mQG+PtaK2vEoKOX2xhHdBr49NGln7zRveoWQ6k3Y4q4Ak/ps/Cw1JJXJfVSjJzxln9nGfpSI8MDx98p+H+t43WJBSX8pDTSle/x8bWWRc6CkAAA=='

    # ------- 生命周期 -------
    def init(self, extend=""):
        pass

    def getName(self):
        return '短剧库'

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        pass

    # ------- 首页分类 -------
    def homeContent(self, filter):
        names = self.class_name.split('&')
        urls = self.class_url.split('&')
        classes = []
        for i in range(min(len(names), len(urls))):
            classes.append({'type_id': urls[i], 'type_name': names[i]})

        result = {'class': classes}
        if filter:
            try:
                raw = base64.b64decode(self.filter_def)
                decoded = gzip.decompress(raw).decode('utf-8')
                result['filters'] = json.loads(decoded)
            except Exception:
                pass
        return result

    # ------- 首页推荐 -------
    def homeVideoContent(self):
        res = self.fetch(
            f'{self.host}/api/home?plat=hongguo&page=1',
            headers=self.headers, verify=False
        ).json()
        return {'list': self._parse_list((res.get('data') or {}).get('list'))}

    # ------- 分类列表 -------
    def categoryContent(self, tid, pg, filter, extend):
        cat = ''
        if isinstance(extend, dict):
            cat = extend.get('cat', '') or ''

        url = f'{self.host}/api/category?plat={tid}&page={pg}'
        if cat:
            url += f'&cat={quote(str(cat))}'

        res = self.fetch(url, headers=self.headers, verify=False).json()
        data = res.get('data') or {}
        videos = self._parse_list(data.get('list'))

        pagecount = data.get('pagecount') or data.get('page_count') or 1
        try:
            pagecount = int(pagecount)
        except Exception:
            pagecount = 1

        try:
            page = int(pg)
        except Exception:
            page = 1

        return {
            'list': videos,
            'page': page,
            'pagecount': pagecount,
            'limit': 20,
            'total': pagecount * 20
        }

    # ------- 搜索 -------
    def searchContent(self, key, quick, pg='1'):
        url = f'{self.host}/api/search?wd={quote(key)}&page={pg}'
        res = self.fetch(url, headers=self.headers, verify=False).json()
        data = res.get('data') or {}
        if isinstance(data, list):
            videos = self._parse_list(data)
        else:
            videos = self._parse_list(data.get('list'))
        try:
            page = int(pg)
        except Exception:
            page = 1
        return {'list': videos, 'page': page}

    # ------- 详情 -------
    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else ids
        vid = str(vid)

        res = self.fetch(
            f'{self.host}/api/detail?id={quote(vid)}',
            headers=self.headers, verify=False
        ).json()
        d = res.get('data') or {}

        plat_key = vid.split(':', 1)[0] if ':' in vid else ''
        plat_name = self.plat_names.get(plat_key, '短剧库')

        play_urls = []
        for ep in (d.get('episodes') or []):
            name = ep.get('name') or ('第' + str(ep.get('no', '')) + '集')
            play_urls.append(f"{name}${ep.get('url', '')}")

        video = {
            'vod_id': vid,
            'vod_name': d.get('vod_name', ''),
            'type_name': d.get('vod_class', ''),
            'vod_pic': d.get('vod_pic', ''),
            'vod_content': d.get('vod_content', ''),
            'vod_play_from': plat_name,
            'vod_play_url': '#'.join(play_urls)
        }
        return {'list': [video]}

    # ------- 播放 -------
    def playerContent(self, flag, video_id, vip_flags):
        headers = {
            'User-Agent': 'MOBILE_UA'
        }
        try:
            api = f'{self.host}/api/play?url={quote(str(video_id), safe="")}'
            res = self.fetch(api, headers=self.headers, verify=False).json()
            if res and res.get('code') == 200 and (res.get('data') or {}).get('url'):
                return {
                    'parse': 0,
                    'jx': 0,
                    'url': res['data']['url'],
                    'header': headers
                }
        except Exception:
            pass
        return {
            'parse': 0,
            'jx': 0,
            'url': video_id,
            'header': headers
        }

    # ------- 工具 -------
    def _parse_list(self, items):
        videos = []
        for v in (items or []):
            videos.append({
                'vod_id': v.get('vod_id', ''),
                'vod_name': v.get('vod_name', ''),
                'vod_pic': v.get('vod_pic', ''),
                'vod_remarks': v.get('vod_remarks', ''),
                'vod_content': v.get('vod_content', '')
            })
        return videos