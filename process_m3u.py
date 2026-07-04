import requests

urls = [
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/refs/heads/master/GuangdongIPTV_rtp_hd.m3u",
    "https://raw.githubusercontent.com/Tzwcard/ChinaTelecom-GuangdongIPTV-RTP-List/refs/heads/master/GuangdongIPTV_rtp_4k.m3u"
]

replace_prefix = "http://192.168.0.251:4022/udp/"
merged_content = ""

for url in urls:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = response.text
        new_content = content.replace("rtp://", replace_prefix)
        merged_content += new_content.strip() + "\n"
    except Exception as e:
        print(f"下载失败：{url}\n错误：{e}")

try:
    with open("GuangdongIPTV_http.m3u", "w", encoding="utf-8") as f:
        f.write(merged_content)
    print("合并并处理完成。")
except Exception as e:
    print("保存文件失败：", str(e))
