import pandas as pd
import json

csv_path = "xiangzhou_gas_stations.csv"
geojson_path = "xiangzhou_gas_stations.geojson"

df = pd.read_csv(csv_path, encoding="utf-8-sig")

features = []

for _, row in df.iterrows():
    lng = row["wgs84_lng"]
    lat = row["wgs84_lat"]

    if pd.isna(lng) or pd.isna(lat):
        continue

    properties = row.drop(["wgs84_lng", "wgs84_lat"]).to_dict()

    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(lng), float(lat)]
        },
        "properties": properties
    }

    features.append(feature)

geojson = {
    "type": "FeatureCollection",
    "features": features
}

with open(geojson_path, "w", encoding="utf-8") as f:
    json.dump(geojson, f, ensure_ascii=False, indent=2)

print(f"Saved to {geojson_path}")