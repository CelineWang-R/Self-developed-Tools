import os
import re
import pandas as pd
import extract_msg
from datetime import datetime

# 用户输入文件夹路径
folder = input("请输入.msg文件所在的文件夹路径: ").strip()

data = []

for filename in os.listdir(folder):
    if not filename.lower().endswith(".msg"):
        continue

    filepath = os.path.join(folder, filename)
    msg = extract_msg.Message(filepath)

    # ⚙️ 强制将邮件内容作为纯文本处理
    try:
        body = msg.body or msg.htmlBody or ""
    except Exception:
        body = ""

    # 移除多余空格与HTML标签（防止被识别为富文本）
    body = re.sub(r"<[^>]+>", "", body)
    body = body.replace("\r", "").strip()

    # 从文件名提取 Station 和 Date
    match = re.search(r"FEOSO\s+(.*?)\s+SS\s+-.*?_(\d{8})", filename, re.IGNORECASE)
    if not match:
        continue
    station = match.group(1).strip().upper()
    date = datetime.strptime(match.group(2), "%Y%m%d").strftime("%Y-%m-%d")

    # 🔍 找到产品价格表部分
    # 例如：
    # Product Name    Current Price ($/Litre)    New Price ($/Litre)    Change ($/Litre)
    # Synergy Extra   27.44    27.64    +0.20
    pattern = re.compile(
        r"Product\s*Name.*?\n(.*?)\n\n", re.DOTALL | re.IGNORECASE
    )
    match_table = pattern.search(body)
    if not match_table:
        # fallback: 找到“Product Name”到“Thank you”之间的文本
        match_table = re.search(
            r"Product\s*Name.*?(?=Thank you)", body, re.DOTALL | re.IGNORECASE
        )
    if not match_table:
        continue

    table_text = match_table.group(1).strip()

    # 将表格内容按行拆分
    lines = [l.strip() for l in table_text.split("\n") if l.strip()]

    # 提取每一行的内容（允许空格、制表符分隔）
    for line in lines:
        # 允许1个或多个空格或制表符分隔
        parts = re.split(r"[\t ]{2,}", line)
        if len(parts) >= 4:
            product, current, new, change = parts[:4]
            data.append({
                "Station": station,
                "Date": date,
                "Product Name": product.strip(),
                "Current Price ($/Litre)": current.strip(),
                "New Price ($/Litre)": new.strip(),
                "Change ($/Litre)": change.strip(),
            })

# 汇总并导出结果
df = pd.DataFrame(data)
output_path = os.path.join(folder, "Price_Adjustment_Summary.xlsx")
df.to_excel(output_path, index=False)

print(f"✅ 已提取完成，共 {len(df)} 行数据")
print(f"💾 输出文件: {output_path}")
