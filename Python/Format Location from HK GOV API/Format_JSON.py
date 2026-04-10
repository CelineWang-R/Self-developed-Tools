import json
import pandas as pd
from pyproj import Transformer

# 1️⃣ Load JSON file
with open("locationSearch.json", encoding="utf-8") as f:
    data = json.load(f)

# 2️⃣ Create a DataFrame
df = pd.DataFrame(data)

# 3️⃣ Convert HK80 (EPSG:2326) → WGS84 (EPSG:4326)
transformer = Transformer.from_crs(2326, 4326, always_xy=True)
df["lon"], df["lat"] = zip(*df.apply(lambda r: transformer.transform(r["x"], r["y"]), axis=1))

# 4️⃣ Reorder / rename columns for clarity
df = df[[
    "nameEN", "addressEN", "districtEN",
    "nameZH", "addressZH", "districtZH",
    "x", "y", "lat", "lon"
]]
df.rename(columns={
    "nameEN": "Name (EN)",
    "addressEN": "Address (EN)",
    "districtEN": "District (EN)",
    "nameZH": "Name (ZH)",
    "addressZH": "Address (ZH)",
    "districtZH": "District (ZH)",
    "x": "HK80_X",
    "y": "HK80_Y",
    "lat": "Latitude",
    "lon": "Longitude"
}, inplace=True)

# 5️⃣ Save to Excel
df.to_excel("esso_hk_list.xlsx", index=False)
print("✅ Done! Saved to esso_hk_list.xlsx")
