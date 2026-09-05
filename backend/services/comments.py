import json
import random
import urllib.request

from flask import current_app

# 经典热歌 ID，用于拉取热门评论
HOT_SONG_IDS = [
    1962165477,  # 晴天-周杰伦
    186016,      # 稻香
    254574,      # 富士山下
    347230,      # 海阔天空-Beyond
    185809,      # 七里香
    28815250,    # 理想三旬
    28285904,    # 刚好遇见你
    415576439,   # 平凡之路
    1397547912,  # 起风了
    29764065,    # 光年之外
]

FALLBACK_COMMENTS = [
    {"content": "小时候真傻，居然盼着长大。", "nickname": "网易云热评", "songName": "热评墙"},
    {"content": "你那么孤独，却说一个人真好。", "nickname": "网易云热评", "songName": "热评墙"},
    {"content": "我希望她三十岁没嫁，也不希望她三十岁没嫁。", "nickname": "网易云热评", "songName": "热评墙"},
    {"content": "愿你所有快乐无需假装，愿你此生尽兴赤诚善良。", "nickname": "网易云热评", "songName": "热评墙"},
    {"content": "世界上最遥远的距离，不是爱，不是恨，而是熟悉的人渐渐变得陌生。", "nickname": "网易云热评", "songName": "热评墙"},
]


def fetch_hot_comment():
    song_id = random.choice(HOT_SONG_IDS)
    url = f"https://music.163.com/api/v1/resource/comments/R_SO_4_{song_id}?limit=10"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": f"https://music.163.com/song?id={song_id}",
            "Host": "music.163.com",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        comments = payload.get("hotComments") or []
        song_name = (payload.get("song") or {}).get("name") or "网易云音乐"
        candidates = [
            {
                "content": item.get("content", "").strip(),
                "nickname": (item.get("user") or {}).get("nickname", "网易云用户"),
                "songName": song_name,
                "likedCount": item.get("likedCount", 0),
            }
            for item in comments
            if item.get("content")
        ]
        if candidates:
            return random.choice(candidates)
    except Exception as error:
        current_app.logger.warning("fetch netease comment failed: %s", error)

    return dict(random.choice(FALLBACK_COMMENTS), likedCount=0)
