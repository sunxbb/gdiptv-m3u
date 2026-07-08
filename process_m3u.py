import requests
import re
from collections import defaultdict

# ========== 配置区 ==========
urls_raw = [
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/refs/heads/master/GuangdongIPTV_rtp_hd.m3u",
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/master/GuangdongIPTV_rtp_4k.m3u"
]
urls_fast = [
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/master/GuangdongIPTV_rtp_hd.m3u",
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/master/GuangdongIPTV_rtp_4k.m3u"
]
replace_prefix = "http://192.168.0.251:4022/udp/"
output_file = "GuangdongIPTV_http.m3u"
timeout = 15
# ==========================

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}

# 画质权重（统一小写key，大小写不敏感匹配）
quality_weight = {
    "4k超高清": 6,
    "4k": 6,
    "超高清": 5,
    "超清": 4,
    "hd": 3,
    "高清": 2,
    "标清": 1
}
# 匹配画质、带宽标识，忽略大小写
quality_reg = re.compile(r"(4k超高清|4K超高清|4K|超高清|超清|HD|高清|标清|\d+M)", re.IGNORECASE)

def get_quality_info(raw_name: str):
    """
    处理原始名称：去首尾空格，计算主画质分 + 次级排序分
    返回 (主分数, 次级分数)
    次级分：4K超高清=2，纯4K=1，其余0，同画质4K超高清置顶
    """
    raw_clean = raw_name.strip()
    matches = quality_reg.findall(raw_clean)
    max_score = 0
    sub_score = 0

    for tag in matches:
        tag_strip = tag.strip()
        tag_lower = tag_strip.lower()
        if tag_lower in quality_weight:
            max_score = max(max_score, quality_weight[tag_lower])
            # 次级排序权重
            if tag_lower == "4k超高清":
                sub_score = 2
            elif tag_lower == "4k":
                sub_score = max(sub_score, 1)
    return max_score, sub_score

def clean_group_title(group_text: str) -> str:
    """清洗分类名：去除前缀 IPTV-，清除首尾空格"""
    txt = group_text.strip()
    if txt.startswith("IPTV-"):
        txt = txt.replace("IPTV-", "", 1).strip()
    return txt

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
    print("\n直连失败，切换ghproxy镜像下载...")
    fast_text = download_text(urls_fast)
    all_text.extend(fast_text)

# 存储结构 key = 去空格后的 tvg-name
# 元组：(-主分, -次级分, 原始EXTINF, 代理URL, 原始线路备注)
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
            if not extinf_cache:
                continue
            # 提取 tvg-name 并去空格
            tvg_match = re.search(r'tvg-name="([^"]+)"', extinf_cache)
            if not tvg_match:
                continue
            tvg_name = tvg_match.group(1).strip()

            # 提取 group-title 并清洗掉 IPTV-
            group_match = re.search(r'group-title="([^"]+)"', extinf_cache)
            clean_group = ""
            if group_match:
                raw_group = group_match.group(1)
                clean_group = clean_group_title(raw_group)
                # 替换原EXTINF里的group-title
                extinf_cache = re.sub(r'group-title="[^"]+"', f'group-title="{clean_group}"', extinf_cache)

            # 提取逗号后原始显示名，去首尾空格，直接作为线路备注
            name_match = re.search(r",(.+)$", extinf_cache)
            if not name_match:
                raw_display = tvg_name
            else:
                raw_display = name_match.group(1).strip()

            # 获取画质分数、次级排序
            score, sub_score = get_quality_info(raw_display)
            proxy_url = line.replace("rtp://", replace_prefix)

            # 存入分组，raw_display直接当线路备注
            channel_groups[tvg_name].append((-score, -sub_score, extinf_cache, proxy_url, raw_display))

# 组装输出M3U
result = ["#EXTM3U"]
total_lines = 0
total_channels = len(channel_groups)

for tvg_name, line_list in channel_groups.items():
    # 先按主画质排序，同画质按次级分（4K超高清优先）
    line_list.sort()
    for neg_score, neg_sub, extinf, url, note in line_list:
        # 统一逗号后显示名为干净无空格tvg-name，APP自动合并线路
        new_extinf = re.sub(r",.*$", f",{tvg_name}", extinf)
        # $后直接放原始完整线路名
        final_url = f"{url}${note}"
        result.append(new_extinf)
        result.append(final_url)
        total_lines += 1

# 写入文件
output_content = "\n".join(result)
try:
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_content)
    print(f"\n===== 处理完成 =====")
    print(f"独立频道总数：{total_channels}")
    print(f"总线路数量：{total_lines}")
    print(f"输出文件：{output_file}")
except Exception as e:
    print(f"文件写入失败：{str(e)}")
