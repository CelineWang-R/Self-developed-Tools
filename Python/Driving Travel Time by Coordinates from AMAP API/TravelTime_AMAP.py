import os
import math
import time
from typing import Dict, Tuple, Optional

import pandas as pd
import requests


# =========================
# 配置
# =========================

AMAP_KEY = os.getenv("AMAP_KEY")  # 建议在环境变量中设置
INPUT_XLSX = "PFS Coordinates.xlsx"
OUTPUT_XLSX = "pfs_control_point_driving_results.xlsx"

AMAP_DRIVING_URL = "https://restapi.amap.com/v3/direction/driving"

REQUEST_SLEEP_SECONDS = 0.2  # 防止请求过快，可根据你的配额调整
MAX_RETRIES = 3
TIMEOUT_SECONDS = 20


CONTROL_POINTS = [
    {
        "control_point_name": "Man Kam To",
        "latitude": 22.53741534,
        "longitude": 114.1288131,
    },
    {
        "control_point_name": "Heung Yuen Wai",
        "latitude": 22.55278148,
        "longitude": 114.15385221,
    },
    {
        "control_point_name": "Lok Ma Chau",
        "latitude": 22.51503396,
        "longitude": 114.06562424,
    },
    {
        "control_point_name": "Shenzhen Bay",
        "latitude": 22.4938221,
        "longitude": 113.94543274,
    },
    {
        "control_point_name": "Hong Kong-Zhuhai-Macao Bridge",
        "latitude": 22.31806901,
        "longitude": 113.95131991,
    },
]


# =========================
# WGS84 -> GCJ-02
# =========================

PI = math.pi
A = 6378245.0
EE = 0.00669342162296594323


def out_of_china(lon: float, lat: float) -> bool:
    """
    粗略判断是否在中国坐标偏移适用范围外。
    香港坐标位于该范围内，因此会进行 GCJ-02 转换。
    """
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
    ret = (
        -100.0
        + 2.0 * x
        + 3.0 * y
        + 0.2 * y * y
        + 0.1 * x * y
        + 0.2 * math.sqrt(abs(x))
    )
    ret += (
        (20.0 * math.sin(6.0 * x * PI)
         + 20.0 * math.sin(2.0 * x * PI))
        * 2.0
        / 3.0
    )
    ret += (
        (20.0 * math.sin(y * PI)
         + 40.0 * math.sin(y / 3.0 * PI))
        * 2.0
        / 3.0
    )
    ret += (
        (160.0 * math.sin(y / 12.0 * PI)
         + 320.0 * math.sin(y * PI / 30.0))
        * 2.0
        / 3.0
    )
    return ret


def _transform_lon(x: float, y: float) -> float:
    ret = (
        300.0
        + x
        + 2.0 * y
        + 0.1 * x * x
        + 0.1 * x * y
        + 0.1 * math.sqrt(abs(x))
    )
    ret += (
        (20.0 * math.sin(6.0 * x * PI)
         + 20.0 * math.sin(2.0 * x * PI))
        * 2.0
        / 3.0
    )
    ret += (
        (20.0 * math.sin(x * PI)
         + 40.0 * math.sin(x / 3.0 * PI))
        * 2.0
        / 3.0
    )
    ret += (
        (150.0 * math.sin(x / 12.0 * PI)
         + 300.0 * math.sin(x / 30.0 * PI))
        * 2.0
        / 3.0
    )
    return ret


def wgs84_to_gcj02(lon: float, lat: float) -> Tuple[float, float]:
    """
    输入：WGS84 lon, lat
    输出：GCJ-02 lon, lat
    """
    if out_of_china(lon, lat):
        return lon, lat

    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)

    rad_lat = lat / 180.0 * PI
    magic = math.sin(rad_lat)
    magic = 1 - EE * magic * magic
    sqrt_magic = math.sqrt(magic)

    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrt_magic) * PI)
    dlon = (dlon * 180.0) / (A / sqrt_magic * math.cos(rad_lat) * PI)

    mg_lat = lat + dlat
    mg_lon = lon + dlon
    return mg_lon, mg_lat


def format_amap_coord(lon: float, lat: float) -> str:
    """
    高德要求坐标顺序为：经度,纬度
    小数点后不超过 6 位。
    """
    return f"{lon:.6f},{lat:.6f}"


# =========================
# 高德驾车路径规划请求
# =========================

def call_amap_driving(
    session: requests.Session,
    origin_lon_gcj: float,
    origin_lat_gcj: float,
    dest_lon_gcj: float,
    dest_lat_gcj: float,
) -> Dict:
    """
    调用高德驾车路径规划 API。
    返回第一条 path 的 distance / duration。
    """
    if not AMAP_KEY:
        raise RuntimeError(
            "未找到高德 Web 服务 API Key。请先设置环境变量 AMAP_KEY。"
        )

    params = {
        "key": AMAP_KEY,
        "origin": format_amap_coord(origin_lon_gcj, origin_lat_gcj),
        "destination": format_amap_coord(dest_lon_gcj, dest_lat_gcj),
        "strategy": 0,
        "extensions": "base",
        # output 是可选参数，默认 JSON；这里显式写出方便解析
        "output": "JSON",
    }

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                AMAP_DRIVING_URL,
                params=params,
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "1":
                raise RuntimeError(
                    f"Amap API error: info={data.get('info')}, "
                    f"infocode={data.get('infocode')}, params={params}"
                )

            paths = data.get("route", {}).get("paths", [])
            if not paths:
                raise RuntimeError(f"No route path returned. params={params}")

            path = paths[0]

            distance_m = float(path.get("distance"))
            duration_s = float(path.get("duration"))

            return {
                "distance_m": distance_m,
                "distance_km": distance_m / 1000,
                "duration_s": duration_s,
                "duration_min": duration_s / 60,
                "amap_status": data.get("status"),
                "amap_info": data.get("info"),
                "amap_infocode": data.get("infocode"),
            }

        except Exception as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * attempt)
            else:
                raise last_error


# =========================
# 主流程
# =========================

def main() -> None:
    pfs_df = pd.read_excel(INPUT_XLSX)

    required_cols = ["Site name", "Latitude", "Longitude"]
    missing_cols = [col for col in required_cols if col not in pfs_df.columns]
    if missing_cols:
        raise ValueError(f"Excel 缺少必要字段: {missing_cols}")

    pfs_df = pfs_df.dropna(subset=required_cols).copy()

    # 预先转换检查站坐标
    control_points_gcj = []
    for cp in CONTROL_POINTS:
        cp_lon_gcj, cp_lat_gcj = wgs84_to_gcj02(
            cp["longitude"],
            cp["latitude"],
        )
        control_points_gcj.append({
            **cp,
            "longitude_gcj02": cp_lon_gcj,
            "latitude_gcj02": cp_lat_gcj,
        })

    results = []

    with requests.Session() as session:
        for _, row in pfs_df.iterrows():
            site_name = row["Site name"]
            site_lat_wgs = float(row["Latitude"])
            site_lon_wgs = float(row["Longitude"])

            site_lon_gcj, site_lat_gcj = wgs84_to_gcj02(
                site_lon_wgs,
                site_lat_wgs,
            )

            for cp in control_points_gcj:
                cp_name = cp["control_point_name"]

                # 方向 1：加油站 -> 检查站
                try:
                    outbound = call_amap_driving(
                        session=session,
                        origin_lon_gcj=site_lon_gcj,
                        origin_lat_gcj=site_lat_gcj,
                        dest_lon_gcj=cp["longitude_gcj02"],
                        dest_lat_gcj=cp["latitude_gcj02"],
                    )
                    outbound_error = ""
                except Exception as exc:
                    outbound = {
                        "distance_m": None,
                        "distance_km": None,
                        "duration_s": None,
                        "duration_min": None,
                        "amap_status": None,
                        "amap_info": None,
                        "amap_infocode": None,
                    }
                    outbound_error = str(exc)

                time.sleep(REQUEST_SLEEP_SECONDS)

                # 方向 2：检查站 -> 加油站
                try:
                    inbound = call_amap_driving(
                        session=session,
                        origin_lon_gcj=cp["longitude_gcj02"],
                        origin_lat_gcj=cp["latitude_gcj02"],
                        dest_lon_gcj=site_lon_gcj,
                        dest_lat_gcj=site_lat_gcj,
                    )
                    inbound_error = ""
                except Exception as exc:
                    inbound = {
                        "distance_m": None,
                        "distance_km": None,
                        "duration_s": None,
                        "duration_min": None,
                        "amap_status": None,
                        "amap_info": None,
                        "amap_infocode": None,
                    }
                    inbound_error = str(exc)

                time.sleep(REQUEST_SLEEP_SECONDS)

                results.append({
                    "site_name": site_name,

                    "site_latitude_wgs84": site_lat_wgs,
                    "site_longitude_wgs84": site_lon_wgs,
                    "site_latitude_gcj02": site_lat_gcj,
                    "site_longitude_gcj02": site_lon_gcj,

                    "control_point_name": cp_name,
                    "control_point_latitude_wgs84": cp["latitude"],
                    "control_point_longitude_wgs84": cp["longitude"],
                    "control_point_latitude_gcj02": cp["latitude_gcj02"],
                    "control_point_longitude_gcj02": cp["longitude_gcj02"],

                    "pfs_to_cp_distance_m": outbound["distance_m"],
                    "pfs_to_cp_distance_km": outbound["distance_km"],
                    "pfs_to_cp_duration_s": outbound["duration_s"],
                    "pfs_to_cp_duration_min": outbound["duration_min"],
                    "pfs_to_cp_amap_info": outbound["amap_info"],
                    "pfs_to_cp_amap_infocode": outbound["amap_infocode"],
                    "pfs_to_cp_error": outbound_error,

                    "cp_to_pfs_distance_m": inbound["distance_m"],
                    "cp_to_pfs_distance_km": inbound["distance_km"],
                    "cp_to_pfs_duration_s": inbound["duration_s"],
                    "cp_to_pfs_duration_min": inbound["duration_min"],
                    "cp_to_pfs_amap_info": inbound["amap_info"],
                    "cp_to_pfs_amap_infocode": inbound["amap_infocode"],
                    "cp_to_pfs_error": inbound_error,
                })

                print(
                    f"Done: {site_name} <-> {cp_name} | "
                    f"outbound={outbound['distance_km']} km, "
                    f"inbound={inbound['distance_km']} km"
                )

    result_df = pd.DataFrame(results)
    result_df.to_excel(OUTPUT_XLSX, index=False)
    print(f"Saved to: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()