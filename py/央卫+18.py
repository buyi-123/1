# coding=utf-8
# 本地电视直播源（央视/卫视双线路）

import sys
sys.path.append('..')
from base.spider import Spider
import json


class Spider(Spider):
    def getName(self):
        return "本地电视直播源"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_name": "y视·线路1", "type_id": "📺y视1"},
            {"type_name": "w视·线路1", "type_id": "📺w视1"},
            {"type_name": "y视·线路2", "type_id": "📺y视2"},
            {"type_name": "w视·线路2", "type_id": "📺w视2"},
        ]
        result['class'] = classes
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        videos = []
        group = CHANNELS.get(tid, [])
        for idx, ch in enumerate(group):
            videos.append({
                "vod_id": tid + "_" + str(idx),
                "vod_name": ch["name"],
                "vod_pic": "",
                "vod_remarks": tid,
                "vod_play_url": ch["url"]
            })
        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 1
        result['limit'] = len(videos)
        result['total'] = len(videos)
        return result

    def detailContent(self, ids):
        result = {}
        id = ids[0]
        tid, idx = id.rsplit("_", 1)
        idx = int(idx)
        group = CHANNELS.get(tid, [])
        if idx < len(group):
            ch = group[idx]
            vod = {
                "vod_id": id,
                "vod_name": ch["name"],
                "vod_pic": "",
                "vod_remarks": tid,
                "vod_content": ch["name"],
                "vod_play_from": "直播线路",
                "vod_play_url": ch["url"]
            }
            result['list'] = [vod]
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": ""
        }
        return result


CHANNELS = {
    "📺y视1": [
        {"name": "CCTV1", "url": "http://112.92.129.96:9898/hls/18/index.m3u8"},
        {"name": "CCTV2", "url": "http://112.92.129.96:9898/hls/19/index.m3u8"},
        {"name": "CCTV3", "url": "http://112.92.129.96:9898/hls/20/index.m3u8"},
        {"name": "CCTV4", "url": "http://112.92.129.96:9898/hls/21/index.m3u8"},
        {"name": "CCTV5", "url": "http://112.92.129.96:9898/hls/22/index.m3u8"},
        {"name": "CCTV5+", "url": "http://112.92.129.96:9898/hls/23/index.m3u8"},
        {"name": "CCTV6", "url": "http://112.92.129.96:9898/hls/24/index.m3u8"},
        {"name": "CCTV7", "url": "http://112.92.129.96:9898/hls/25/index.m3u8"},
        {"name": "CCTV8", "url": "http://112.92.129.96:9898/hls/26/index.m3u8"},
        {"name": "CCTV9", "url": "http://112.92.129.96:9898/hls/27/index.m3u8"},
        {"name": "CCTV10", "url": "http://112.92.129.96:9898/hls/28/index.m3u8"},
        {"name": "CCTV11", "url": "http://112.92.129.96:9898/hls/29/index.m3u8"},
        {"name": "CCTV12", "url": "http://112.92.129.96:9898/hls/30/index.m3u8"},
        {"name": "CCTV13", "url": "http://112.92.129.96:9898/hls/31/index.m3u8"},
        {"name": "CCTV14", "url": "http://112.92.129.96:9898/hls/32/index.m3u8"},
        {"name": "CCTV15", "url": "http://112.92.129.96:9898/hls/33/index.m3u8"},
        {"name": "CCTV16", "url": "http://112.92.129.96:9898/hls/127/index.m3u8"},
        {"name": "CCTV17", "url": "http://112.92.129.96:9898/hls/34/index.m3u8"},
        {"name": "CHC影迷电影", "url": "http://112.92.129.96:9898/hls/53/index.m3u8"},
        {"name": "CHC家庭影院", "url": "http://112.92.129.96:9898/hls/118/index.m3u8"},
        {"name": "CHC动作电影", "url": "http://112.92.129.96:9898/hls/119/index.m3u8"},
    ],
    "📺w视1": [
        {"name": "深圳卫视", "url": "http://112.92.129.96:9898/hls/16/index.m3u8"},
        {"name": "湖南卫视", "url": "http://112.92.129.96:9898/hls/35/index.m3u8"},
        {"name": "东方卫视", "url": "http://112.92.129.96:9898/hls/36/index.m3u8"},
        {"name": "北京卫视", "url": "http://112.92.129.96:9898/hls/37/index.m3u8"},
        {"name": "江苏卫视", "url": "http://112.92.129.96:9898/hls/38/index.m3u8"},
        {"name": "安徽卫视", "url": "http://112.92.129.96:9898/hls/39/index.m3u8"},
        {"name": "湖北卫视", "url": "http://112.92.129.96:9898/hls/40/index.m3u8"},
        {"name": "山东卫视", "url": "http://112.92.129.96:9898/hls/41/index.m3u8"},
        {"name": "辽宁卫视", "url": "http://112.92.129.96:9898/hls/45/index.m3u8"},
        {"name": "江西卫视", "url": "http://112.92.129.96:9898/hls/48/index.m3u8"},
        {"name": "贵州卫视", "url": "http://112.92.129.96:9898/hls/49/index.m3u8"},
        {"name": "浙江卫视", "url": "http://112.92.129.96:9898/hls/54/index.m3u8"},
        {"name": "海南卫视", "url": "http://112.92.129.96:9898/hls/63/index.m3u8"},
        {"name": "广西卫视", "url": "http://112.92.129.96:9898/hls/64/index.m3u8"},
        {"name": "河南卫视", "url": "http://112.92.129.96:9898/hls/66/index.m3u8"},
        {"name": "甘肃卫视", "url": "http://112.92.129.96:9898/hls/69/index.m3u8"},
        {"name": "东南卫视", "url": "http://112.92.129.96:9898/hls/101/index.m3u8"},
    ],
    "📺y视2": [
        {"name": "CCTV1", "url": "http://121.57.88.206:898/hls/1/index.m3u8"},
        {"name": "CCTV2", "url": "http://121.57.88.206:898/hls/2/index.m3u8"},
        {"name": "CCTV3", "url": "http://121.57.88.206:898/hls/3/index.m3u8"},
        {"name": "CCTV4", "url": "http://121.57.88.206:898/hls/4/index.m3u8"},
        {"name": "CCTV5", "url": "http://121.57.88.206:898/hls/5/index.m3u8"},
        {"name": "CCTV6", "url": "http://121.57.88.206:898/hls/6/index.m3u8"},
        {"name": "CCTV7", "url": "http://121.57.88.206:898/hls/7/index.m3u8"},
        {"name": "CCTV8", "url": "http://121.57.88.206:898/hls/8/index.m3u8"},
        {"name": "CCTV9", "url": "http://121.57.88.206:898/hls/9/index.m3u8"},
        {"name": "CCTV10", "url": "http://121.57.88.206:898/hls/10/index.m3u8"},
        {"name": "CCTV11", "url": "http://121.57.88.206:898/hls/11/index.m3u8"},
        {"name": "CCTV12", "url": "http://121.57.88.206:898/hls/12/index.m3u8"},
        {"name": "CCTV13", "url": "http://121.57.88.206:898/hls/13/index.m3u8"},
        {"name": "CCTV14", "url": "http://121.57.88.206:898/hls/14/index.m3u8"},
        {"name": "CCTV15", "url": "http://121.57.88.206:898/hls/15/index.m3u8"},
        {"name": "CCTV16", "url": "http://121.57.88.206:898/hls/16/index.m3u8"},
        {"name": "CCTV17", "url": "http://121.57.88.206:898/hls/17/index.m3u8"},
        {"name": "CCTV5+", "url": "http://121.57.88.206:898/hls/18/index.m3u8"},
    ],
    "📺w视2": [
        {"name": "浙江卫视", "url": "http://121.57.88.206:898/hls/20/index.m3u8"},
        {"name": "江苏卫视", "url": "http://121.57.88.206:898/hls/21/index.m3u8"},
        {"name": "广东卫视", "url": "http://121.57.88.206:898/hls/22/index.m3u8"},
        {"name": "东方卫视", "url": "http://121.57.88.206:898/hls/23/index.m3u8"},
        {"name": "辽宁卫视", "url": "http://121.57.88.206:898/hls/24/index.m3u8"},
        {"name": "山东卫视", "url": "http://121.57.88.206:898/hls/25/index.m3u8"},
        {"name": "安徽卫视", "url": "http://121.57.88.206:898/hls/27/index.m3u8"},
        {"name": "北京卫视", "url": "http://121.57.88.206:898/hls/28/index.m3u8"},
        {"name": "东南卫视", "url": "http://121.57.88.206:898/hls/29/index.m3u8"},
        {"name": "湖南卫视", "url": "http://121.57.88.206:898/hls/32/index.m3u8"},
        {"name": "深圳卫视", "url": "http://121.57.88.206:898/hls/34/index.m3u8"},
         {"name": "香蕉台", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/117.ts"},
          {"name": "松视3台", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/90.ts"},
        ]
        }
   
