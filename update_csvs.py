import csv
import re
from pathlib import Path
from typing import Dict

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent

KO_FILES = [ROOT / "ko_kr1.lua", ROOT / "ko_kr2.lua", ROOT / "ko_kr3.lua"]


def build_english_to_korean() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for path in KO_FILES:
        with path.open(encoding="utf-8") as f:
            for line in f:
                match = re.search(r"\{\s*\"(\d+)\"\s*,\s*\"([^\"]*)\"", line)
                if not match:
                    continue
                korean = match.group(2)
                comment_match = re.search(r"--\s*(.+?)\s*$", line)
                if not comment_match:
                    continue
                english = comment_match.group(1).strip()
                if english and english not in mapping:
                    mapping[english] = korean
    mapping.update(
        {
            "Jacob and Esau": "야곱과 에사우",
            "Jacob & Esau": "야곱과 에사우",
            "Soul of Jacob and Esau": "야곱과 에사우의 영혼",
        }
    )
    # provide simple article variations to improve matching
    for english, korean in list(mapping.items()):
        if english.startswith(("The ", "A ", "An ")):
            continue
        mapping.setdefault(f"The {english}", korean)
        mapping.setdefault(f"A {english}", korean)
        mapping.setdefault(f"An {english}", korean)
    return mapping


def build_character_mapping(english_to_korean: Dict[str, str]) -> Dict[str, str]:
    char_map: Dict[str, str] = {}
    for english, korean in english_to_korean.items():
        if english.startswith("Soul of "):
            base = english[len("Soul of ") :]
            if korean.endswith("의 영혼"):
                char_map[base.lower()] = korean[:-4]
            elif korean.endswith("의 영혼?"):
                char_map[base.lower()] = korean[:-5]
            else:
                char_map[base.lower()] = korean
    # manual aliases for secret variations
    # ensure Jacob & Esau uses the preferred transliteration
    char_map["jacob and esau"] = "야곱과 에사우"
    aliases = {
        "the forgotten": "포가튼",
        "the keeper": "키퍼",
        "the lost": "로스트",
        "the lamb": "어린 양",
        "forgotten": "포가튼",
        "maggy": "막달레나",
        "lazarus": char_map.get("lazarus", "나사로"),
        "lazarus risen": "부활한 나사로",
        "jacob & esau": "야곱과 에사우",
        "jacob and esau": "야곱과 에사우",
        "keeper": char_map.get("the keeper", "키퍼"),
        "forgotten": "포가튼",
    }
    for key, value in aliases.items():
        char_map.setdefault(key, value)
    return char_map


def parse_collectible_names() -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for path in KO_FILES:
        with path.open(encoding="utf-8") as f:
            lines = f.readlines()
        in_block = False
        depth = 0
        for line in lines:
            lower = line.lower()
            if not in_block:
                if "collectibles" in lower and "=" in line and "{" in line:
                    in_block = True
                    depth = line.count("{") - line.count("}")
                    match = re.search(r"\{\s*\"(\d+)\"\s*,\s*\"([^\"]*)\"", line)
                    if match:
                        mapping[int(match.group(1))] = match.group(2)
                    continue
            else:
                match = re.search(r"\{\s*\"(\d+)\"\s*,\s*\"([^\"]*)\"", line)
                if match:
                    mapping[int(match.group(1))] = match.group(2)
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    in_block = False
    return mapping


def fetch_item_metadata() -> Dict[int, Dict[str, str]]:
    url = "https://bindingofisaacrebirth.fandom.com/wiki/Items"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    tables = soup.find_all("table", class_="wikitable")
    mapping: Dict[int, Dict[str, str]] = {}
    for table, item_type in zip(tables[:2], ["Active", "Passive"]):
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if not cols:
                continue
            id_text = cols[1].get_text(strip=True)
            if not id_text:
                continue
            id_part = id_text.split(".")[-1]
            if not id_part.isdigit():
                continue
            item_id = int(id_part)
            quality = cols[-1].get_text(strip=True) if len(cols) >= 6 else ""
            mapping[item_id] = {"Type": item_type, "Quality": quality}
    return mapping


def translate_generic(name: str, mapping: Dict[str, str]) -> str:
    if not name:
        return ""
    if name in mapping:
        return mapping[name]
    if name.lower() in mapping:
        return mapping[name.lower()]
    return ""


def translate_character(name: str, char_map: Dict[str, str], eng_map: Dict[str, str]) -> str:
    if not name:
        return ""
    normalized = name.lower().replace("&", "and").strip()
    normalized = normalized.replace("the ", "the ", 1)
    if normalized in char_map:
        return char_map[normalized]
    if name in eng_map:
        return eng_map[name]
    if name.lower() in eng_map:
        return eng_map[name.lower()]
    return ""


def update_ui_items(item_names: Dict[int, str], wiki_meta: Dict[int, Dict[str, str]], eng_map: Dict[str, str]) -> None:
    path = ROOT / "ui_items.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    updated = []
    for row in rows:
        try:
            item_id = int(row["ItemID"])
        except ValueError:
            item_id = None
        korean = ""
        if item_id is not None and item_id in item_names:
            korean = item_names[item_id]
        if not korean:
            name = row.get("ItemName", "")
            korean = translate_generic(name, eng_map)
        meta = wiki_meta.get(item_id, {}) if item_id is not None else {}
        updated.append({
            "ItemID": row["ItemID"],
            "ItemName": row.get("ItemName", ""),
            "Korean": korean,
            "UnlockedFlag": row.get("UnlockedFlag", ""),
            "Type": meta.get("Type", ""),
            "Quality": meta.get("Quality", ""),
        })
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ItemID", "ItemName", "Korean", "UnlockedFlag", "Type", "Quality"])
        writer.writeheader()
        writer.writerows(updated)


def update_generic_csv(filename: str, key_column: str, translator) -> None:
    path = ROOT / filename
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    fieldnames = reader.fieldnames if reader.fieldnames else []
    if "Korean" not in fieldnames:
        insert_index = fieldnames.index(key_column) + 1 if key_column in fieldnames else len(fieldnames)
        fieldnames = fieldnames[:insert_index] + ["Korean"] + fieldnames[insert_index:]
    updated_rows = []
    for row in rows:
        name = row.get(key_column, "")
        korean = translator(name)
        row_copy = dict(row)
        row_copy["Korean"] = korean
        updated_rows.append(row_copy)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)


def main() -> None:
    eng_map = build_english_to_korean()
    char_map = build_character_mapping(eng_map)
    item_names = parse_collectible_names()
    wiki_meta = fetch_item_metadata()

    update_ui_items(item_names, wiki_meta, eng_map)

    update_generic_csv("ui_challenges.csv", "ChallengeName", lambda name: translate_generic(name, eng_map))
    update_generic_csv(
        "ui_characters.csv",
        "Character",
        lambda name: translate_character(name, char_map, eng_map),
    )
    update_generic_csv(
        "ui_completion_marks.csv",
        "CharacterName",
        lambda name: translate_character(name, char_map, eng_map),
    )
    update_generic_csv("ui_numeric_fields.csv", "FieldName", lambda name: translate_generic(name, eng_map))
    update_generic_csv("ui_secrets.csv", "SecretName", lambda name: translate_generic(name, eng_map))


if __name__ == "__main__":
    main()
