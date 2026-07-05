import requests
import re
from collections import defaultdict

# ========== 配置区 ==========
urls_raw = [
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/refs/heads/master/GuangdongIPTV_rtp_all.m3u",
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/master/GuangdongIPTV_rtp_4k.m3u"
]
urls_fast = [
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/master/GuangdongIPTV_rtp_all.m3u",
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/master/GuangdongIPTV_rtp_4k.m3u"
]
replace_prefix = "http://192.168.0.251:4022/udp/"
output_file = "GuangdongIPTV_http.m3u"
timeout = 15
# ==========================

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}

# 画质权重（越高画质越优先）
quality_weight = {
    "4K": 6,
    "4k超高清": 6,
    "超高清": 5,
    "超清": 4,
    "HD": 3,
    "高清": 2,
    "标清": 1
}
# 匹配画质关键词（支持中间带空格场景）
quality_reg = re.compile(r"(4k超高清|4K|超高清|超清|HD|高清|标清)", re.IGNORECASE)
# 剥离画质后缀用于频道分组
strip_suffix_reg = re.compile(r"\s*(4k超高清|4K|超高清|超清|HD|高清|标清)$", re.IGNORECASE)

def get_std_channel_name(name: str) -> str:
    """去除末尾画质后缀，得到基础频道名用于分组"""
    return strip_suffix_reg.sub("", name).strip()

def get_quality_score(name: str) -> int:
    """提取画质分数，无画质标识返回0"""
    match = quality_reg.search(name)
    if not match:
        return 0
    tag = match.group(1)
    tag_lower = tag.lower()
    if tag_lower == "4k超高清":
        return quality_weight["4k超高清"]
    return quality_weight.get(tag, 0)

def download_text(url_list) -> list:
    content_list = []
    for url in url_list:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            text = resp.text.strip()
            if text:
                content_list.append(text)
                print(f"✅ 成功下载: {url}")
        except Exception as err:
            print(f"❌ 链接失败 {url} | 错误: {str(err)[:120]}")
    return content_list

# 下载源
print("尝试直连Github Raw...")
all_text = download_text(urls_raw)
if len(all_text) < 2:
    print("\n直连失败，切换国内ghproxy加速镜像...")
    fast_text = download_text(urls_fast)
    all_text.extend(fast_text)

# 结构：key=标准频道名，value=字典{播放地址: (画质分, extinf行, 显示名)}
channel_groups = defaultdict(dict)

for text in all_text:
    lines = text.splitlines()
    extinf_cache = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            extinf_cache = line
        elif line.startswith("rtp://"):
            play_url = line.replace("rtp://", replace_prefix)
            name_match = re.search(r",(.+)$", extinf_cache)
            if not name_match:
                continue
            display_name = name_match.group(1).strip()
            std_name = get_std_channel_name(display_name)
            score = get_quality_score(display_name)
            # 用播放地址做key自动去重，重复地址会覆盖只保留第一条
            channel_groups[std_name][play_url] = (score, extinf_cache, display_name)

# 组装输出
result = ["#EXTM3U"]
total_unique = 0
group_count = len(channel_groups)

for group_name, url_map in channel_groups.items():
    # 转为列表：(负分数, extinf, 显示名, 播放地址)，方便画质降序
    item_list = []
    for play_url, (score, extinf, disp_name) in url_map.items():
        item_list.append((-score, extinf, disp_name, play_url))
    # 按画质从高到低排序
    item_list.sort()
    # 写入m3u
    for neg_score, extinf, disp, url in item_list:
        result.append(extinf)
        result.append(url)
        total_unique += 1

# 保存文件
final_content = "\n".join(result)
try:
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_content)
    print(f"\n===== 处理完成 =====")
    print(f"频道分组总数：{group_count}")
    print(f"去重后独立线路总数：{total_unique}")
    print(f"输出文件：{output_file}")
except Exception as e:
    print(f"文件保存失败: {str(e)}")
