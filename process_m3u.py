import requests
import re
from collections import defaultdict

# ========== 配置区 ==========
# 原始Github源
urls_raw = [
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/refs/heads/master/GuangdongIPTV_rtp_hd.m3u",
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/refs/heads/master/GuangdongIPTV_rtp_4k.m3u"
]
# 国内加速镜像备选（Github访问失败自动切换）
urls_fast = [
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/master/GuangdongIPTV_rtp_hd.m3u",
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/master/GuangdongIPTV_rtp_4k.m3u"
]
replace_prefix = "http://192.168.0.251:4022/udp/"  # udpxy地址
output_file = "GuangdongIPTV_http.m3u"
timeout = 15
# ==========================

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}

# 分组存储 key=标准化频道名 value=[(extinf完整行, 显示名, 播放地址)]
channel_groups = defaultdict(list)
# 正则：清除画质后缀用于归类
suffix_reg = re.compile(r"(4K|超高清|超清|HD|高清|标清)$")

def get_std_channel_name(name: str) -> str:
    """去除画质后缀，统一归类名称"""
    return suffix_reg.sub("", name).strip()

def download_text(url_list) -> list:
    """循环尝试多个地址，返回成功的文本内容列表"""
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

# 先尝试原生地址，失败走国内加速
print("尝试直连Github Raw...")
all_text = download_text(urls_raw)
if len(all_text) < 2:
    print("\n直连失败，切换国内ghproxy加速镜像...")
    fast_text = download_text(urls_fast)
    all_text.extend(fast_text)

# 解析所有m3u内容，按频道分组
for text in all_text:
    lines = text.splitlines()
    extinf_cache = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 缓存频道信息行
        if line.startswith("#EXTINF:"):
            extinf_cache = line
        # 播放地址行，执行分组逻辑
        elif line.startswith("rtp://"):
            play_url = line.replace("rtp://", replace_prefix)
            # 提取频道名称 ,频道名
            name_match = re.search(r",(.+)$", extinf_cache)
            if not name_match:
                continue
            display_name = name_match.group(1).strip()
            std_name = get_std_channel_name(display_name)
            # 存入分组
            channel_groups[std_name].append((extinf_cache, display_name, play_url))

# 生成最终m3u文本
result = ["#EXTM3U"]
total_line_count = 0
group_total = len(channel_groups)

# 按分组依次输出，同频道所有清晰度连在一起
for group_title, channel_items in channel_groups.items():
    for extinf, disp_name, url in channel_items:
        result.append(extinf)
        result.append(url)
        total_line_count += 1

# 写入文件
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
