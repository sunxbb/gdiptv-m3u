import requests
import re
from collections import defaultdict

# ========== 配置区 ==========
urls_raw = [
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/refs/heads/master/GuangdongIPTV_rtp_all.m3u",
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/refs/heads/master/GuangdongIPTV_rtp_4k.m3u"
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

# 画质权重：数值越大画质越高，用于排序
quality_weight = {
    "4K": 6,
    "超高清": 5,
    "超清": 4,
    "HD": 3,
    "高清": 2,
    "标清": 1
}
# 匹配画质后缀正则
quality_reg = re.compile(r"(4K|超高清|超清|HD|高清|标清)")
# 归类用正则，剥离画质后缀得到基础频道名
strip_suffix_reg = re.compile(r"(4K|超高清|超清|HD|高清|标清)$")

def get_std_channel_name(name: str) -> str:
    """去除画质后缀，生成统一分组key"""
    return strip_suffix_reg.sub("", name).strip()

def get_quality_score(name: str) -> int:
    """获取当前频道画质权重，无标签返回0（普通频道放最后）"""
    match = quality_reg.search(name)
    if match:
        tag = match.group(1)
        return quality_weight.get(tag, 0)
    return 0

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

# 下载源文件
print("尝试直连Github Raw...")
all_text = download_text(urls_raw)
if len(all_text) < 2:
    print("\n直连失败，切换国内ghproxy加速镜像...")
    fast_text = download_text(urls_fast)
    all_text.extend(fast_text)

# 分组存储 key=标准化频道名 value=[(画质分数, extinf行, 显示名, 播放地址)]
channel_groups = defaultdict(list)

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
            # 存入分组，带上排序权重
            channel_groups[std_name].append((-score, extinf_cache, display_name, play_url))

# 生成M3U内容
result = ["#EXTM3U"]
total_line_count = 0
group_total = len(channel_groups)

for group_title, item_list in channel_groups.items():
    # 按 -score 升序等价于 score 降序：4K > 超高清 > 超清 > HD > 高清 > 标清
    item_list.sort()
    for score_neg, extinf, disp_name, url in item_list:
        result.append(extinf)
        result.append(url)
        total_line_count += 1

final_m3u = "\n".join(result)
try:
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_m3u)
    print(f"\n===== 完成 =====")
    print(f"频道分组总数：{group_total}")
    print(f"全部播放线路：{total_line_count} 条")
    print(f"输出文件：{output_file}")
except Exception as e:
    print(f"文件保存失败: {str(e)}")
    
