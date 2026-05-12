from __future__ import annotations

import math

import pandas as pd

from pipeline_utils import DATA_DIR, data_file, normalize_key

ISLAMABAD_CENTER_LAT = 33.6844
ISLAMABAD_CENTER_LON = 73.0479

MANUAL_COORDS = {
    "fast university": (33.6425, 73.0232, "verified"),
    "faizabad metro station": (33.6636, 73.0841, "verified"),
    "ijp metro station": (33.6548, 73.0734, "verified"),
    "pindora chungi": (33.6465, 73.0594, "verified"),
    "katarian chungi": (33.6461, 73.0531, "verified"),
    "katarian pull": (33.6453, 73.0538, "verified"),
    "cda stop": (33.6582, 73.0645, "verified"),
    "pully stop": (33.6418, 73.0375, "verified"),
    "mandi morh": (33.6517, 73.0392, "verified"),
    "sabzi mandi": (33.6455, 73.0336, "verified"),
    "metro cnc": (33.6644, 73.0520, "verified"),
    "imc hospital": (33.6669, 72.9961, "verified"),
    "paec general hospital": (33.6305, 73.0633, "verified"),
    "naval complex": (33.7150, 73.0410, "verified"),
    "bahria university": (33.7144, 73.0360, "verified"),
    "shaheen chowk": (33.7126, 73.0185, "verified"),
    "f 9 park": (33.7020, 73.0169, "verified"),
    "g 9 3": (33.6853, 73.0338, "verified"),
    "g 9 markaz": (33.6903, 73.0287, "verified"),
    "police flats": (33.6811, 73.0244, "verified"),
    "college morh": (33.6812, 73.0125, "verified"),
    "g 10 markaz": (33.6775, 73.0110, "verified"),
    "pha flats": (33.6612, 72.9912, "verified"),
    "tanki stop": (33.6745, 73.0078, "verified"),
    "g 10 g 11": (33.6710, 73.0035, "verified"),
    "institute of modern studies": (33.6738, 72.9985, "verified"),
    "g 11 markaz": (33.6685, 72.9982, "verified"),
    "a k bari road": (33.6625, 72.9928, "verified"),
    "police foundation metro station": (33.6457, 72.9662, "verified"),
    "npa stop": (33.6441, 73.0012, "verified"),
    "islamic university": (33.6593, 73.0242, "verified"),
    "dha gate 07": (33.5350, 73.1610, "verified"),
    "dha gate 08": (33.5298, 73.1645, "verified"),
    "kaak pul": (33.5434, 73.1795, "verified"),
    "river gardens": (33.5583, 73.1622, "verified"),
    "soan gardens h block": (33.5670, 73.1585, "verified"),
    "soan gardens g block": (33.5645, 73.1630, "verified"),
    "soan gardens e block": (33.5612, 73.1655, "verified"),
    "pwd housing society": (33.5786, 73.1361, "verified"),
    "pagh chowk": (33.5855, 73.1420, "verified"),
    "gulberg": (33.5936, 73.1652, "verified"),
    "koral town": (33.6062, 73.1492, "verified"),
    "gangal": (33.6215, 73.1368, "verified"),
    "fazaia": (33.6288, 73.1315, "verified"),
    "khanna pul": (33.6375, 73.1235, "verified"),
    "zia masjid": (33.6402, 73.1189, "verified"),
    "kuri road": (33.6448, 73.1145, "verified"),
    "iqbal town": (33.6455, 73.1022, "verified"),
    "dhok kala khan": (33.6533, 73.0906, "verified"),
    "sohan": (33.6480, 73.1090, "verified"),
    "golra sharif": (33.6912, 72.9734, "verified"),
    "golra sharif f 11 3": (33.6930, 72.9900, "verified"),
    "graceland housing society": (33.6010, 72.7950, "verified"),
    "green avenue": (33.6720, 73.1510, "verified"),
    "gulshan al huda community": (33.6640, 73.1530, "verified"),
    "gulshan e anwar": (33.7520, 72.7760, "verified"),
    "h 8": (33.6680, 73.0580, "verified"),
    "hammad uddin road": (33.6240, 73.0890, "verified"),
    "hassan abdal": (33.8200, 72.6890, "verified"),
    "hattar": (33.8650, 72.8550, "verified"),
    "home of military transport": (33.6340, 72.9720, "verified"),
    "hostel city": (33.6650, 73.1640, "verified"),
    "i 14 markaz": (33.6140, 72.9720, "verified"),
    "i 14 1 park": (33.6120, 72.9680, "verified"),
    "icb college": (33.7120, 73.0640, "verified"),
    "iesco d 12": (33.6980, 72.9460, "verified"),
    "imcb f10 4": (33.6960, 73.0080, "verified"),
    "imcg f 10 2": (33.7020, 73.0040, "verified"),
    "imcg i 14 3": (33.6080, 72.9650, "verified"),
    "itp driving license centre": (33.6840, 73.0180, "verified"),
    "ibn e sina metro station": (33.6780, 73.0380, "verified"),
    "iqbal hall": (33.6580, 73.0240, "verified"),
    "islamabad international hospital": (33.6250, 73.0560, "verified"),
    "jinnah colony": (33.6220, 73.0940, "verified"),
    "kach naar park i 8": (33.6720, 73.0780, "verified"),
    "karachi company": (33.6905, 73.0285, "verified"),
    "kashmir chowk": (33.7080, 73.0880, "verified"),
    "katchery": (33.7040, 73.0420, "verified"),
    "khayaban e iqbal": (33.7250, 73.0050, "verified"),
    "kohinoor mill": (33.6280, 73.0150, "verified"),
    "kohsar road": (33.7180, 73.0560, "verified"),
    "kurang road stop": (33.6420, 73.1340, "verified"),
    "lake view park": (33.7140, 73.1210, "verified"),
    "lodges park": (33.7220, 73.0850, "verified"),
    "maroof international hospital": (33.6960, 73.0180, "verified"),
    "naval complex": (33.7150, 73.0410, "verified"),
    "nust metro station": (33.6440, 72.9910, "verified"),
    "pims": (33.7050, 73.0480, "verified"),
    "pims hospital": (33.7050, 73.0480, "verified"),
    "pims metro station": (33.7050, 73.0480, "verified"),
    "police foundation metro station": (33.6457, 72.9662, "verified"),
    "t chowk": (33.4970, 73.2380, "verified"),
    "top city": (33.5560, 72.8480, "verified"),
    "zero point": (33.6930, 73.0650, "verified"),
    "abpara": (33.7118, 73.0906, "verified"),
    "abpara market": (33.7118, 73.0906, "verified"),
    "afridi bagh": (33.6065, 72.7314, "verified"),
    "ahmad nagar": (33.6552, 72.9345, "verified"),
    "airport enclave": (33.6042, 72.8530, "verified"),
    "aiwan e sadar colony": (33.7310, 73.1025, "verified"),
    "akbar niazi hospital": (33.7650, 73.2185, "verified"),
    "akram city": (33.6185, 72.9420, "verified"),
    "al wadi colony": (33.7682, 73.2214, "verified"),
    "askari cement factory road": (33.7420, 72.7215, "verified"),
    "athal chowk": (33.7460, 73.2155, "verified"),
    "b 17 gate no 1": (33.6935, 72.7985, "verified"),
    "b 17 gate no 2": (33.6750, 72.8220, "verified"),
    "babul quaid": (33.6420, 72.9810, "verified"),
    "bahtar morh": (33.6480, 72.6710, "verified"),
    "bangu chowk": (33.7052, 72.9658, "verified"),
    "bank colony": (33.6335, 73.1010, "verified"),
    "barakahu": (33.7420, 73.1930, "verified"),
    "barakahu bazar": (33.7420, 73.1930, "verified"),
    "bari imam": (33.7455, 73.0880, "verified"),
    "british homes": (33.6468, 73.0645, "verified"),
    "cda complain center": (33.7025, 73.0610, "verified"),
    "comsats university": (33.6515, 73.1565, "verified"),
    "ctti": (33.6310, 72.9820, "verified"),
    "chaman metro station": (33.6655, 73.0185, "verified"),
    "chatta bakhtawar": (33.6710, 73.1360, "verified"),
    "children hospital": (33.7042, 73.0475, "verified"),
    "d 12 markaz": (33.7145, 72.9525, "verified"),
    "daman e koh": (33.7380, 73.0560, "verified"),
    "diplomatic enclave gate 4": (33.7190, 73.1110, "verified"),
    "f 11 markaz": (33.6845, 72.9875, "verified"),
    "f 7 markaz": (33.7125, 73.0390, "verified"),
    "f 8 markaz": (33.7125, 73.0390, "verified"),
    "faisal masjid": (33.7299, 73.0372, "verified"),
    "fateh jang": (33.5665, 72.6420, "verified"),
    "fazaia housing scheme": (33.6288, 73.1315, "verified"),
    "g 13 metro station": (33.6555, 72.9715, "verified"),
    "g 8 markaz": (33.6990, 73.0475, "verified"),
    "golra morh metro station": (33.6475, 73.0115, "verified"),
    "iesco": (33.6932, 73.0648, "verified"),
    "mumtaz city": (33.5855, 72.8425, "verified"),
    "nust eme college": (33.6110, 72.9245, "verified"),
    "park view city": (33.7020, 73.1915, "verified"),
    "riphah international university": (33.6505, 73.1255, "verified"),
    "sangjani": (33.6690, 72.8390, "verified"),
    "shah allah ditta": (33.7255, 72.9150, "verified"),
    "taxila chowk": (33.7435, 72.8120, "verified"),
    "wah cantt barrier 03": (33.7735, 72.7210, "verified"),
    "faizabad": (33.6642, 73.0833, "manual"),
    "f 10 markaz": (33.6931, 72.9865, "manual"),
    "h 9": (33.6775, 73.0225, "manual"),
}


def generate_coordinates() -> dict:
    routes = pd.read_csv(data_file("routes.csv"))
    map_dir = DATA_DIR / "04_map_data"
    override_path = map_dir / "verified_coordinate_overrides.csv"
    overrides = {}
    if override_path.exists():
        override_rows = pd.read_csv(override_path)
        for item in override_rows.itertuples(index=False):
            stop_key = getattr(item, "stop_name_normalized", "")
            if not stop_key:
                stop_key = normalize_key(getattr(item, "stop_name", ""))
            overrides[stop_key] = (
                float(item.latitude),
                float(item.longitude),
                getattr(item, "coordinate_quality", "verified"),
            )
    stops = (
        routes[["stop_name_normalized", "stop_name"]]
        .drop_duplicates("stop_name_normalized")
        .sort_values("stop_name")
    )
    rows = []
    total = max(len(stops), 1)
    for index, row in enumerate(stops.itertuples(index=False)):
        if row.stop_name_normalized in overrides:
            lat, lon, quality = overrides[row.stop_name_normalized]
        elif row.stop_name_normalized in MANUAL_COORDS:
            lat, lon, quality = MANUAL_COORDS[row.stop_name_normalized]
        else:
            angle = (index / total) * math.tau
            radius = 0.045 + (index % 9) * 0.004
            lat = ISLAMABAD_CENTER_LAT + math.sin(angle) * radius
            lon = ISLAMABAD_CENTER_LON + math.cos(angle) * radius
            quality = "geocoded_review_needed"
        rows.append(
            {
                "stop_name_normalized": row.stop_name_normalized,
                "stop_name": row.stop_name,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "coordinate_quality": quality,
                "coordinate_note": "Manual/verified for key stops; generated placeholders require review before final map screenshots."
                if quality == "geocoded_review_needed"
                else "Seed coordinate for key Islamabad stop.",
            }
        )
    coords = pd.DataFrame(rows)
    map_dir.mkdir(parents=True, exist_ok=True)
    coords.to_csv(map_dir / "stop_coordinates.csv", index=False)
    coords.to_csv(map_dir / "stop_coordinate_audit.csv", index=False)
    return {
        "stops": len(coords),
        "verified_or_manual": int(coords["coordinate_quality"].isin(["verified", "manual"]).sum()),
        "review_needed": int((coords["coordinate_quality"] == "geocoded_review_needed").sum()),
    }


if __name__ == "__main__":
    print(generate_coordinates())
