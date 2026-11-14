"""Reproduce the role-4 official inventory, anchor selection, and spatial audit.

Read-only with respect to original Notion attachments and existing model inputs.
No model learning or route optimization is performed. Required reference XLSX
snapshots are described in data/reference/spatial_sources.json.
"""
import collections
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data/reference"
ORIGINAL = ROOT / "docs/notion/01_data_preprocessing"
BUS_URL = "https://data.seoul.go.kr/dataList/OA-15067/S/1/datasetView.do"
RAIL_URL = "https://data.kric.go.kr/rips/M_01_01/detail.do?id=32"


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def xlsx_rows(path):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = iter(book.active.values)
    header = next(sheet)
    result = [dict(zip(header, row)) for row in sheet if row[0] is not None]
    book.close()
    return result


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def haversine(lat1, lon1, lat2, lon2):
    p, q = map(math.radians, (lat1, lat2))
    value = math.sin((q-p)/2)**2 + math.cos(p)*math.cos(q)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(value)))


def main():
    original = csv_rows(ORIGINAL / "01_region_stations_clean.csv")
    original_ids = {row["station_id"] for row in original}
    baseline = json.loads((ROOT / "network.json").read_text(encoding="utf-8"))
    baseline_ids = {row["id"] for row in baseline["stops"]}
    official = xlsx_rows(REF / "seoul_bus_stops_20260902.xlsx")
    inventory = []
    for row in sorted(official, key=lambda r: str(r["NODE_ID"])):
        ars = str(row["ARS_ID"]).zfill(5)
        if not ars.startswith("13"):
            continue
        sid = str(row["NODE_ID"])
        inventory.append(dict(station_id=sid, ars_id=ars,
            station_name=row["정류소명"], latitude=row["Y좌표"], longitude=row["X좌표"],
            stop_type_ko=row["정류소타입"], district_code="13", district_name="서대문구",
            membership_method="official_ARS_prefix13", node_prefix112=int(sid.startswith("112")),
            in_original_808=int(sid in original_ids), in_baseline_282=int(sid in baseline_ids),
            source_snapshot="2026-09-02", source_dataset="OA-15067", source_url=BUS_URL))
    ids = {row["station_id"] for row in inventory}
    assert len(ids) == len(inventory), "Duplicate official NODE_ID"
    assert baseline_ids <= ids, "Baseline contains IDs outside official ARS13 inventory"
    write_csv(REF / "seodaemun_bus_stops_official.csv", inventory)
    write_csv(REF / "seodaemun_missing_from_original808.csv",
              [row for row in inventory if row["station_id"] not in original_ids])

    names = {"홍대입구":"hongik", "이대":"ewha", "아현":"ahyeon", "충정로":"chungjeongno",
             "홍제":"hongje", "무악재":"muakjae", "독립문":"dongnimmun", "애오개":"aeogae",
             "서대문":"seodaemun", "증산":"jeungsan", "디지털미디어시티":"dmc", "서강대":"sogang", "가좌":"gajwa"}
    anchors = []
    rail = xlsx_rows(REF / "kric_urban_rail_stations_20260630.xlsx")
    for row in rail:
        try:
            lat, lon = float(row["역위도"]), float(row["역경도"])
        except (ValueError, TypeError):
            continue
        if not 37.4 < lat < 37.8:
            continue
        nearest = min(haversine(lat, lon, float(stop["latitude"]), float(stop["longitude"])) for stop in inventory)
        if nearest > 500:
            continue
        name = re.sub(r"\([^)]*\)", "", str(row["역사명"]))
        name = name[:-1] if name.endswith("역") else name
        group = ("sinchon_gyeongui" if row["노선번호"] == "I4108" else "sinchon_line2") if name == "신촌" else names[name]
        label = "신촌(경의중앙선)" if group == "sinchon_gyeongui" else "신촌(2호선)" if group == "sinchon_line2" else name
        date = row["데이터기준일자"]
        date = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else date
        anchors.append(dict(hub_id=group, hub_name=label,
            anchor_id=str(row["노선번호"])+":"+str(row["역번호"]), anchor_type="rail_station_reference_point",
            station_code=str(row["역번호"]), line_code=row["노선번호"], line_name=row["노선명"],
            latitude=lat, longitude=lon, address=row["역사도로명주소"], nearest_official_stop_m=round(nearest,3),
            record_date=date, source_dataset="KRIC standard station 20260630", source_url=RAIL_URL,
            coordinate_caveat="station reference point, not entrance; straight-line screening only"))
    for sid in ("112000031", "112000032", "112900188"):
        row = next(row for row in inventory if row["station_id"] == sid)
        anchors.append(dict(hub_id="yonsei_front", hub_name="연대앞", anchor_id="bus:"+sid,
            anchor_type="yonsei_front_official_bus_stop_reference", station_code=sid, line_code="", line_name="",
            latitude=row["latitude"], longitude=row["longitude"], address=row["station_name"],
            nearest_official_stop_m=0, record_date="2026-09-02",
            source_dataset="OA-15067 selected Yonsei-front bus anchors", source_url=BUS_URL,
            coordinate_caveat="official bus-stop point; project grouping, not surveyed campus gate or walking entrance"))
    write_csv(REF / "hub_anchors_official.csv", sorted(anchors,key=lambda row:(row["hub_id"],row["anchor_id"])))

    overlap = ids & original_ids
    seen, zero, invalid, total = set(), [], 0, 0
    for archive in sorted(ORIGINAL.glob("11_road_distance_part*.zip")):
        with zipfile.ZipFile(archive) as zipped:
            for name in zipped.namelist():
                with zipped.open(name) as source:
                    for row in csv.DictReader(io.TextIOWrapper(source, encoding="utf-8-sig")):
                        total += 1
                        origin, destination = row["from_station_id"], row["to_station_id"]
                        if origin not in overlap or destination not in overlap:
                            continue
                        pair = origin, destination
                        if pair in seen:
                            raise ValueError(f"Duplicate road pair: {pair}")
                        seen.add(pair)
                        distance = float(row["road_m"])
                        invalid += int(not math.isfinite(distance) or distance < 0)
                        if distance == 0 and origin != destination:
                            zero.append(dict(from_station_id=origin,to_station_id=destination,
                                             road_m=distance,straight_m=row.get("straight_m")))
    snap = csv_rows(ORIGINAL / "12_station_osm_snap.csv")
    report = dict(snapshot_date_kst="2026-11-15", official_source_date="2026-09-02",
        official_all_seoul_rows=len(official), official_node112_count=sum(str(r["NODE_ID"]).startswith("112") for r in official),
        official_ARS13_count=len(ids), district_membership="ARS_ID prefix13; corroborated official OA22187 20260930 district table; not polygon containment",
        official_ARS13_node_non112_count=sum(not row["station_id"].startswith("112") for row in inventory),
        baseline_count=len(baseline_ids), baseline_coverage_fraction=len(baseline_ids)/len(ids),
        baseline_missing_official_count=len(ids-baseline_ids), original808_official_overlap_count=len(overlap),
        original808_missing_official_count=len(ids-overlap), original808_coverage_fraction=len(overlap)/len(ids),
        official_type_counts=dict(collections.Counter(row["stop_type_ko"] for row in inventory)),
        original_overlap_type_counts=dict(collections.Counter(row["stop_type_ko"] for row in inventory if row["station_id"] in overlap)),
        source112_noncentral_count=sum(row["village_bus_stoppable"] == "1" for row in original if row["station_id"] in baseline_ids),
        official_all_noncentral_count=sum(row["stop_type_ko"] != "중앙차로" for row in inventory),
        official_bounds={"latitude":[min(float(r["latitude"]) for r in inventory),max(float(r["latitude"]) for r in inventory)],
                         "longitude":[min(float(r["longitude"]) for r in inventory),max(float(r["longitude"]) for r in inventory)]},
        road_input_rows=total, road_covered_stop_count=len(overlap), road_available_directed_pairs=len(seen),
        road_expected_pairs_within_overlap=len(overlap)*(len(overlap)-1), road_expected_pairs_full_official=len(ids)*(len(ids)-1),
        road_missing_pairs_full_official=len(ids)*(len(ids)-1)-len(seen), road_invalid_in_overlap=invalid,
        zero_road_pairs_in_overlap=zero, source_overlap_snap_quality=dict(collections.Counter(r["distance_quality"] for r in snap if r["station_id"] in overlap)),
        source_files=[])
    for filename in ("kric_urban_rail_stations_20260630.xlsx", "seoul_bus_route_inventory_20260930.xlsx", "seoul_bus_stops_20260902.xlsx"):
        path = REF / filename
        report["source_files"].append(dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size,
                                         sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (ROOT / "docs/evidence/spatial_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Official ARS13 stops: {len(inventory)}; original road-covered: {len(overlap)}; anchors: {len(anchors)}")


if __name__ == "__main__":
    main()
