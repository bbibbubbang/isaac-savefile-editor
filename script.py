import base64
from typing import Dict

filename = r""

"""
item start offset (no base): 0xAB8
item end offset (no base): 0xD97?
base offset: 0x2AE
some useful data offsets: (not tested, thank you afterbirth save editor)
"0x4", "Mom Kills",
"0x8", "Broken Rocks",
"0xC", "Broken Tinted Rocks",
"0x10", "Poop Destroyed",
// "0x14",   "???", Blank
"0x18", "Death Cards Used?", //?
"0x1C", "??? (0x1C)", //?
"0x20", "Arcades Visited?", //?
"0x24", "Deaths",
"0x28", "Isaac Kills?",
"0x2C", "Shop Keepers Destroyed",
"0x30", "Satan Kills?",
"0x34", "Shell Game Playcount",
"0x38", "Angel Items Taken?",
"0x3C", "Devil Deals Taken?",
"0x40", "Blood Donations?",
"0x44", "Slots Destroyed",
"0x48", "??? (0x48)",
"0x4C", "Pennies Donated",✅
"0x50", "Eden Tokens",✅
"0x54", "Win Streak", 
"0x58", "Best Streak", ✅
"0x5C", "??? Kills?",
"0x60", "Lamb Kills?",
"0x64", "??? (0x64)",
"0x1A8", "Loss Streak", 
"0x1B0", "??? (0x1B0)",
"0x1B4", "??? (0x1B4)",
"0x1B8", "Pennies Donated (Greed)",
"0x254", "Greed Donations (Isaac)",
"0x258", "Greed Donations (Maggy)",
"0x25C", "Greed Donations (Cain)",
"0x260", "Greed Donations (Judas)",
"0x264", "Greed Donations (???)",
"0x268", "Greed Donations (Eve)",
"0x26C", "Greed Donations (Samson)",
"0x270", "Greed Donations (Azazel)",
"0x274", "Greed Donations (Lazarus)",
"0x278", "Greed Donations (Eden)",
"0x27C", "Greed Donations (The Lost)",
"0x280", "Greed Donations (Lilith)",
"0x284", "Greed Donations (Keeper)",
"0x298", "Caves Cleared",
"0x29C", "Basements Cleared",
"0x2A0", "??? (0x2A0)",
"0x2A4", "Depths Cleared"
"""

characters = ["Isaac", "Maggy", "Cain", "Judas", "???", "Eve", "Samson", "Azazel", 
              "Lazarus", "Eden", "The Lost", "Lilith", "Keeper", "Apollyon", "Forgotten", "Bethany",
              "Jacob & Esau", "T Isaac", "T Maggy", "T Cain", "T Judas", "T ???", "T Eve", "T Samson", "T Azazel", 
              "T Lazarus", "T Eden", "T Lost", "T Lilith", "T Keeper", "T Apollyon", "T Forgotten", "T Bethany",
              "T Jacob"]
checklist_order = ["Isaac's Heart", "Isaac", "Satan", "Boss Rush", "Chest", "Dark Room", "Mega Satan", "Hush", "Greed", "Delirium", "Mother", "Beast"]


ITEM_FLAG_SEEN = 0x01
ITEM_FLAG_TOUCHED = 0x02
ITEM_FLAG_COLLECTED = 0x04
ITEM_UNLOCK_CLEAR_MASK = ITEM_FLAG_SEEN | ITEM_FLAG_TOUCHED | ITEM_FLAG_COLLECTED

COMPLETION_FLAG_NORMAL = 0x01
COMPLETION_FLAG_HARD = 0x02
COMPLETION_FLAG_GREED = 0x04
COMPLETION_FLAG_GREEDIER = 0x08
COMPLETION_DEFAULT_UNLOCK_MASK = COMPLETION_FLAG_NORMAL | COMPLETION_FLAG_HARD
COMPLETION_GREED_UNLOCK_MASK = COMPLETION_FLAG_GREED | COMPLETION_FLAG_GREEDIER

_ENTRY_LENGTHS = [1, 4, 4, 1, 1, 1, 1, 4, 4, 1, 546]
_SECRET_SECTION_INDEX = 0
_BESTIARY_SECTION_INDEX = 10
_BESTIARY_GROUP_COUNT = 4
_BESTIARY_HEADER_SIZE = 8
_BESTIARY_ENTRY_SIZE = 8

DEAD_GOD_BESTIARY_SECTION_BASE64 = (
    "BAAAAIwDAAAAAKAACAAAAAABoAADAAAAAAKgAAQAAAAAALAABQAAAAABsAADAAAAAADAAAYAAAAA"
    "AOAABQAAAAAB4AABAAAAAADwAAQAAAAAAfAAAQAAAAABAAECAAAAAAIAAQIAAAAAACABEAAAAAAA"
    "MAEGAAAAAAEwAQIAAAAAAEABBwAAAAAAUAEBAAAAAABwAQQAAAAAAXABAwAAAAACcAEFAAAAAACA"
    "AQUAAAAAAYABAQAAAAACgAECAAAAAACQAQgAAAAAApABAwAAAAADkAEBAAAAAACgAQMAAAAAAaAB"
    "BwAAAAAAsAECAAAAAADAAQIAAAAAANABAwAAAAAB0AEHAAAAAAPQAQEAAAAAAOABAQAAAAAAAAIC"
    "AAAAAAAgAgQAAAAAADACAgAAAAACMAIDAAAAAABAAgEAAAAAAWACAgAAAAAAcAIBAAAAAAFwAgEA"
    "AAAAAJACAQAAAAACkAIBAAAAAACgAgIAAAAAAaACAQAAAAAAsAIDAAAAAAGwAgEAAAAAAcACAQAA"
    "AAAA0AICAAAAAADgAgEAAAAAAeACAgAAAAAA8AIBAAAAAAHwAgIAAAAAAAADAQAAAAABAAMEAAAA"
    "AAAQAwMAAAAAARADAQAAAAAAIAMCAAAAAAEgAwIAAAAAADADAQAAAAAVMAMDAAAAAB8wAwMAAAAA"
    "AEADAgAAAAABQAMBAAAAAABQAwEAAAAAAGADCgAAAAABcAMCAAAAAAJwAwIAAAAAAIADAQAAAAAA"
    "oAMBAAAAAAGgAwMAAAAAAMADAgAAAAAA0AMGAAAAAALQAwIAAAAAA9ADAQAAAAAA4AMBAAAAAALg"
    "AwEAAAAAAPADBQAAAAAAAAQCAAAAAAAQBAEAAAAAARAEAQAAAAAAMAQBAAAAAAFABAIAAAAAAFAE"
    "AwAAAAAAcAQBAAAAAADQBAEAAAAAAOAEAQAAAAAB4AQFAAAAAArwBAIAAAAAAAAFAgAAAAAAEAUL"
    "AAAAAAEQBQIAAAAAAEAFAgAAAAAAUAUYAAAAAABwBQIAAAAAAIAFAQAAAAABwAUBAAAAAADQBQEA"
    "AAAAAOAFAgAAAAAAAAYDAAAAAAAQBgEAAAAAADAGBAAAAAAAQAYBAAAAAAFABgQAAAAAAFAGAwAA"
    "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"
)

try:
    _DEAD_GOD_BESTIARY_SECTION = base64.b64decode(
        DEAD_GOD_BESTIARY_SECTION_BASE64
    )
except Exception:
    _DEAD_GOD_BESTIARY_SECTION = b""

def rshift(val, n): 
    return val>>n if val >= 0 else (val+0x100000000)>>n

def getSectionOffsets(data):
    ofs = 0x14
    sectData = [-1, -1, -1]
    sectionOffsets = [0] * len(_ENTRY_LENGTHS)
    for i in range(len(_ENTRY_LENGTHS)):
        for j in range(3):
            sectData[j] = int.from_bytes(data[ofs:ofs+2], 'little', signed=False)
            ofs += 4
        if sectionOffsets[i] == 0:
            sectionOffsets[i] = ofs
        for j in range(sectData[2]):
            ofs += _ENTRY_LENGTHS[i]
    return sectionOffsets


def _get_section_entry_count(data, section_index):
    ofs = 0x14
    sectData = [-1, -1, -1]
    for i in range(len(_ENTRY_LENGTHS)):
        for j in range(3):
            sectData[j] = int.from_bytes(data[ofs:ofs+2], 'little', signed=False)
            ofs += 4
        count = sectData[2]
        if i == section_index:
            return count
        ofs += _ENTRY_LENGTHS[i] * count
    raise IndexError("section_index out of range")


def getSecretCount(data):
    return _get_section_entry_count(data, _SECRET_SECTION_INDEX)


def getBestiaryOffsets(data):
    section_offsets = getSectionOffsets(data)
    if len(section_offsets) <= _BESTIARY_SECTION_INDEX:
        raise IndexError("Bestiary section offset not available")
    base_offset = section_offsets[_BESTIARY_SECTION_INDEX]
    offsets: list[int] = []
    current = base_offset
    for _ in range(_BESTIARY_GROUP_COUNT):
        if current + _BESTIARY_HEADER_SIZE > len(data):
            raise ValueError("Bestiary data is truncated")
        offsets.append(current)
        encoded_count = int.from_bytes(
            data[current + 4 : current + 8], "little", signed=False
        )
        entry_count = encoded_count // 4
        current += _BESTIARY_HEADER_SIZE + entry_count * _BESTIARY_ENTRY_SIZE
    return offsets


def _read_bestiary_groups(data, offsets):
    headers = []
    maps = []
    orders = []
    for offset in offsets:
        header = bytearray(data[offset : offset + _BESTIARY_HEADER_SIZE])
        encoded_count = int.from_bytes(header[4:8], "little", signed=False)
        entry_count = encoded_count // 4
        mapping = {}
        order = []
        position = offset + _BESTIARY_HEADER_SIZE
        for _ in range(entry_count):
            chunk = bytes(data[position : position + _BESTIARY_ENTRY_SIZE])
            prefix = chunk[:4]
            mapping[prefix] = chunk
            order.append(prefix)
            position += _BESTIARY_ENTRY_SIZE
        headers.append(header)
        maps.append(mapping)
        orders.append(order)
    return headers, maps, orders


def _read_bestiary_section_from_bytes(data: bytes):
    headers = []
    maps = []
    orders = []
    position = 0
    for _ in range(_BESTIARY_GROUP_COUNT):
        if position + _BESTIARY_HEADER_SIZE > len(data):
            return None
        header = bytes(data[position : position + _BESTIARY_HEADER_SIZE])
        encoded_count = int.from_bytes(header[4:8], "little", signed=False)
        entry_count = encoded_count // 4
        position += _BESTIARY_HEADER_SIZE

        mapping = {}
        order = []
        for _ in range(entry_count):
            if position + _BESTIARY_ENTRY_SIZE > len(data):
                return None
            chunk = bytes(data[position : position + _BESTIARY_ENTRY_SIZE])
            prefix = chunk[:4]
            mapping[prefix] = chunk
            order.append(prefix)
            position += _BESTIARY_ENTRY_SIZE

        headers.append(header)
        maps.append(mapping)
        orders.append(order)

    if position < len(data) and any(data[position:]):
        return None

    return headers, maps, orders


def _load_reference_bestiary(reference_data):
    candidates = []
    if reference_data:
        candidates.append(reference_data)
    if _DEAD_GOD_BESTIARY_SECTION:
        candidates.append(_DEAD_GOD_BESTIARY_SECTION)

    for candidate in candidates:
        try:
            offsets = getBestiaryOffsets(candidate)
        except (IndexError, ValueError):
            parsed = _read_bestiary_section_from_bytes(candidate)
        else:
            parsed = _read_bestiary_groups(candidate, offsets)

        if parsed:
            return parsed

    return None


def updateCheckListUnlocks(data, char_index, new_checklist_data):
    if char_index == 14:
        clu_ofs = getSectionOffsets(data)[1] + 0x32C
        for i in range(len(new_checklist_data)):
            current_ofs = clu_ofs + i * 4
            data = alterInt(data, current_ofs, new_checklist_data[i])
            if i == 8:
                clu_ofs += 0x4
            if i == 9:
                clu_ofs += 0x37C
            if i == 10:
                clu_ofs += 0x84
    elif char_index > 14:
        clu_ofs = getSectionOffsets(data)[1] + 0x31C
        for i in range(len(new_checklist_data)):
            current_ofs = clu_ofs + char_index * 4 + i * 19 * 4
            data = alterInt(data, current_ofs, new_checklist_data[i])
            if i == 8:
                clu_ofs += 0x4C
            if i == 9:
                clu_ofs += 0x3C
            if i == 10:
                clu_ofs += 0x3C
    else:
        clu_ofs = getSectionOffsets(data)[1] + 0x6C
        for i in range(len(new_checklist_data)):
            current_ofs = clu_ofs + char_index * 4 + i * 14 * 4
            data = alterInt(data, current_ofs, new_checklist_data[i])
            if i == 5:
                clu_ofs += 0x14
            if i == 8:
                clu_ofs += 0x3C
            if i == 9:
                clu_ofs += 0x3B0
            if i == 10:
                clu_ofs += 0x50
    return data

def getChecklistUnlocks(data, char_index):
    checklist_data = []
    if char_index == 14:
        clu_ofs = getSectionOffsets(data)[1] + 0x32C
        for i in range(12):
            current_ofs = clu_ofs + i * 4
            checklist_data.append(getInt(data, current_ofs))
            if i == 8:
                clu_ofs += 0x4
            if i == 9:
                clu_ofs += 0x37C
            if i == 10:
                clu_ofs += 0x84
    elif char_index > 14:
        clu_ofs = getSectionOffsets(data)[1] + 0x31C
        for i in range(12):
            current_ofs = clu_ofs + char_index * 4 + i * 19 * 4
            checklist_data.append(getInt(data, current_ofs))
            if i == 8:
                clu_ofs += 0x4C
            if i == 9:
                clu_ofs += 0x3C
            if i == 10:
                clu_ofs += 0x3C
    else:
        clu_ofs = getSectionOffsets(data)[1] + 0x6C
        for i in range(12):
            current_ofs = clu_ofs + char_index * 4 + i * 14 * 4
            checklist_data.append(getInt(data, current_ofs))
            if i == 5:
                clu_ofs += 0x14
            if i == 8:
                clu_ofs += 0x3C
            if i == 9:
                clu_ofs += 0x3B0
            if i == 10:
                clu_ofs += 0x50
    return checklist_data

def getItems(data):
    item_data = []
    offs = getSectionOffsets(data)[3]
    for i in range(1, 733):
        entry_offset = offs + (i - 1) * _ITEM_ENTRY_STRIDE + 1
        item_data.append(getInt(data, entry_offset, num_bytes=1))
    return item_data

def getChallenges(data):
    challenge_data = []
    offs = getSectionOffsets(data)[6]
    for i in range(1, 46):
        challenge_data.append(getInt(data, offs+i, num_bytes=1))
    return challenge_data

def getSecrets(data):
    secrets_data = []
    offs = getSectionOffsets(data)[_SECRET_SECTION_INDEX]
    secret_count = getSecretCount(data)
    for i in range(1, secret_count + 1):
        secrets_data.append(getInt(data, offs+i, num_bytes=1))
    return secrets_data


def calcAfterbirthChecksum(data, ofs, length):
    CrcTable = [
        0x00000000, 0x09073096, 0x120E612C, 0x1B0951BA, 0xFF6DC419, 0xF66AF48F, 0xED63A535, 0xE46495A3, 
        0xFEDB8832, 0xF7DCB8A4, 0xECD5E91E, 0xE5D2D988, 0x01B64C2B, 0x08B17CBD, 0x13B82D07, 0x1ABF1D91, 
        0xFDB71064, 0xF4B020F2, 0xEFB97148, 0xE6BE41DE, 0x02DAD47D, 0x0BDDE4EB, 0x10D4B551, 0x19D385C7, 
        0x036C9856, 0x0A6BA8C0, 0x1162F97A, 0x1865C9EC, 0xFC015C4F, 0xF5066CD9, 0xEE0F3D63, 0xE7080DF5, 
        0xFB6E20C8, 0xF269105E, 0xE96041E4, 0xE0677172, 0x0403E4D1, 0x0D04D447, 0x160D85FD, 0x1F0AB56B, 
        0x05B5A8FA, 0x0CB2986C, 0x17BBC9D6, 0x1EBCF940, 0xFAD86CE3, 0xF3DF5C75, 0xE8D60DCF, 0xE1D13D59, 
        0x06D930AC, 0x0FDE003A, 0x14D75180, 0x1DD06116, 0xF9B4F4B5, 0xF0B3C423, 0xEBBA9599, 0xE2BDA50F, 
        0xF802B89E, 0xF1058808, 0xEA0CD9B2, 0xE30BE924, 0x076F7C87, 0x0E684C11, 0x15611DAB, 0x1C662D3D, 
        0xF6DC4190, 0xFFDB7106, 0xE4D220BC, 0xEDD5102A, 0x09B18589, 0x00B6B51F, 0x1BBFE4A5, 0x12B8D433, 
        0x0807C9A2, 0x0100F934, 0x1A09A88E, 0x130E9818, 0xF76A0DBB, 0xFE6D3D2D, 0xE5646C97, 0xEC635C01,
        0x0B6B51F4, 0x026C6162, 0x196530D8, 0x1062004E, 0xF40695ED, 0xFD01A57B, 0xE608F4C1, 0xEF0FC457, 
        0xF5B0D9C6, 0xFCB7E950, 0xE7BEB8EA, 0xEEB9887C, 0x0ADD1DDF, 0x03DA2D49, 0x18D37CF3, 0x11D44C65, 
        0x0DB26158, 0x04B551CE, 0x1FBC0074, 0x16BB30E2, 0xF2DFA541, 0xFBD895D7, 0xE0D1C46D, 0xE9D6F4FB, 
        0xF369E96A, 0xFA6ED9FC, 0xE1678846, 0xE860B8D0, 0x0C042D73, 0x05031DE5, 0x1E0A4C5F, 0x170D7CC9, 
        0xF005713C, 0xF90241AA, 0xE20B1010, 0xEB0C2086, 0x0F68B525, 0x066F85B3, 0x1D66D409, 0x1461E49F, 
        0x0EDEF90E, 0x07D9C998, 0x1CD09822, 0x15D7A8B4, 0xF1B33D17, 0xF8B40D81, 0xE3BD5C3B, 0xEABA6CAD, 
        0xEDB88320, 0xE4BFB3B6, 0xFFB6E20C, 0xF6B1D29A, 0x12D54739, 0x1BD277AF, 0x00DB2615, 0x09DC1683, 
        0x13630B12, 0x1A643B84, 0x016D6A3E, 0x086A5AA8, 0xEC0ECF0B, 0xE509FF9D, 0xFE00AE27, 0xF7079EB1, 
        0x100F9344, 0x1908A3D2, 0x0201F268, 0x0B06C2FE, 0xEF62575D, 0xE66567CB, 0xFD6C3671, 0xF46B06E7, 
        0xEED41B76, 0xE7D32BE0, 0xFCDA7A5A, 0xF5DD4ACC, 0x11B9DF6F, 0x18BEEFF9, 0x03B7BE43, 0x0AB08ED5, 
        0x16D6A3E8, 0x1FD1937E, 0x04D8C2C4, 0x0DDFF252, 0xE9BB67F1, 0xE0BC5767, 0xFBB506DD, 0xF2B2364B, 
        0xE80D2BDA, 0xE10A1B4C, 0xFA034AF6, 0xF3047A60, 0x1760EFC3, 0x1E67DF55, 0x056E8EEF, 0x0C69BE79, 
        0xEB61B38C, 0xE266831A, 0xF96FD2A0, 0xF068E236, 0x140C7795, 0x1D0B4703, 0x060216B9, 0x0F05262F, 
        0x15BA3BBE, 0x1CBD0B28, 0x07B45A92, 0x0EB36A04, 0xEAD7FFA7, 0xE3D0CF31, 0xF8D99E8B, 0xF1DEAE1D, 
        0x1B64C2B0, 0x1263F226, 0x096AA39C, 0x006D930A, 0xE40906A9, 0xED0E363F, 0xF6076785, 0xFF005713, 
        0xE5BF4A82, 0xECB87A14, 0xF7B12BAE, 0xFEB61B38, 0x1AD28E9B, 0x13D5BE0D, 0x08DCEFB7, 0x01DBDF21, 
        0xE6D3D2D4, 0xEFD4E242, 0xF4DDB3F8, 0xFDDA836E, 0x19BE16CD, 0x10B9265B, 0x0BB077E1, 0x02B74777, 
        0x18085AE6, 0x110F6A70, 0x0A063BCA, 0x03010B5C, 0xE7659EFF, 0xEE62AE69, 0xF56BFFD3, 0xFC6CCF45, 
        0xE00AE278, 0xE90DD2EE, 0xF2048354, 0xFB03B3C2, 0x1F672661, 0x166016F7, 0x0D69474D, 0x046E77DB, 
        0x1ED16A4A, 0x17D65ADC, 0x0CDF0B66, 0x05D83BF0, 0xE1BCAE53, 0xE8BB9EC5, 0xF3B2CF7F, 0xFAB5FFE9, 
        0x1DBDF21C, 0x14BAC28A, 0x0FB39330, 0x06B4A3A6, 0xE2D03605, 0xEBD70693, 0xF0DE5729, 0xF9D967BF, 
        0xE3667A2E, 0xEA614AB8, 0xF1681B02, 0xF86F2B94, 0x1C0BBE37, 0x150C8EA1, 0x0E05DF1B, 0x0702EF8D
    ]
    checksum = 0xFEDCBA76
    checksum = ~checksum

    for i in range(ofs, ofs+length):
        checksum = CrcTable[((checksum & 0xFF)) ^ data[i]] ^ (rshift(checksum, 8))

    return ~checksum + 2 ** 32

def alterSecret(data, achievement, unlock=True):
    offs = getSectionOffsets(data)[0]
    new_data = b'\x00'
    if unlock:
        new_data = b'\x01'
    new_data = data[:offs + achievement] + new_data + data[offs + achievement + 1:] 
    return new_data

def alterChallenge(data, challenge_index, unlock=True):
    if unlock:
        val = 1
    else:
        val = 0
    return alterInt(data, getSectionOffsets(data)[6]+challenge_index, val, num_bytes=1)

def alterItem(data, item_index, unlock=True):
    if unlock:
        val = 1
    else:
        val = 0
    return alterInt(data, getSectionOffsets(data)[3]+item_index, val, num_bytes=1)

def alterInt(data, offset, new_val, debug=False, num_bytes=2, signed=False):
    if debug:
        current_val = int.from_bytes(
            data[offset:offset+num_bytes], 'little', signed=signed
        )
        print(f"current value: {current_val}")
        print(f"new value: {new_val}")
    return data[:offset] + int(new_val).to_bytes(num_bytes, 'little', signed=signed) + data[offset + num_bytes:]

def getInt(data, offset, debug=False, num_bytes=2, signed=False):
    if debug:
        current_val = int.from_bytes(
            data[offset:offset+num_bytes], 'little', signed=signed
        )
        print(f"current value: {current_val}")
    return int.from_bytes(data[offset:offset+num_bytes], 'little', signed=signed)

def _normalize_secret_ids(secret_list):
    normalized = []
    seen = set()
    for entry in secret_list:
        try:
            secret_id = int(entry)
        except (TypeError, ValueError):
            continue
        if secret_id <= 0:
            continue
        key = str(secret_id)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(secret_id)
    return normalized


def applySecretOverrides(data, unlocked_ids, overrides=None):
    if overrides is None:
        overrides = SECRET_UNLOCK_OVERRIDES
    if not overrides:
        return data
    result = data
    section_offsets = None
    unlocked_lookup = {str(value).strip() for value in unlocked_ids if str(value).strip()}
    for secret_id, config in overrides.items():
        normalized_id = str(secret_id).strip()
        if not normalized_id:
            continue
        offsets = config.get("offsets")
        if not offsets:
            continue
        value_key = "unlock_value" if normalized_id in unlocked_lookup else "lock_value"
        if value_key not in config:
            continue
        try:
            desired_value = int(config[value_key])
        except (TypeError, ValueError):
            continue
        try:
            num_bytes = int(config.get("num_bytes", 1))
        except (TypeError, ValueError):
            num_bytes = 1
        signed = bool(config.get("signed", False))
        absolute = bool(config.get("absolute", False))
        section_index = config.get("section_index", 1)
        try:
            section_index = int(section_index)
        except (TypeError, ValueError):
            section_index = 1
        try:
            offset_base = int(config.get("offset_base", 0))
        except (TypeError, ValueError):
            offset_base = 0
        if isinstance(offsets, (list, tuple, set)):
            offset_values = offsets
        else:
            offset_values = (offsets,)
        for raw_offset in offset_values:
            try:
                offset_value = int(raw_offset)
            except (TypeError, ValueError):
                continue
            target_offset = offset_value
            if not absolute:
                if section_offsets is None:
                    try:
                        section_offsets = getSectionOffsets(result)
                    except Exception:
                        section_offsets = []
                if section_index < 0 or section_index >= len(section_offsets):
                    continue
                target_offset = section_offsets[section_index] + offset_base + offset_value
            if target_offset < 0 or target_offset + num_bytes > len(result):
                continue
            result = alterInt(
                result,
                target_offset,
                desired_value,
                num_bytes=num_bytes,
                signed=signed,
            )
    return result


def updateSecrets(data, secret_list):
    secret_count = getSecretCount(data)
    for i in range(1, secret_count + 1):
        data = alterSecret(data, i, False)
    unlocked_ids = _normalize_secret_ids(secret_list)
    for secret_id in unlocked_ids:
        data = alterSecret(data, secret_id)
    return applySecretOverrides(data, unlocked_ids)

def updateChallenges(data, challenge_list):
    for i in range(1, 46):
        data = alterChallenge(data, i, False)
    for i in challenge_list:
        data = alterChallenge(data, int(i), True)
    return data

# Additional map unlocks require touching other stat counters in the
# persistent data. ``SECRET_UNLOCK_OVERRIDES`` mirrors the structure used by
# the GUI so that command line invocations of ``updateSecrets`` behave in the
# same way.  Offsets are relative to the player stats section (index 1) unless
# ``absolute`` is set to :data:`True`.
SECRET_UNLOCK_OVERRIDES: Dict[str, Dict[str, object]] = {
    "641": {
        "offsets": (0x0526, 0x0B0A, 0x0E65, 0x0F24, 0x0FD0),
        "unlock_value": 1,
        "lock_value": 0,
        "num_bytes": 4,
        "section_index": 1,
    }
}


_SKIPPED_ITEM_IDS = {43, 59, 61, 235, 587, 613, 620, 630, 648, 656, 662, 666, 718}
_ITEM_ENTRY_STRIDE = 4


def _normalize_item_ids(item_list):
    normalized = set()
    for entry in item_list:
        try:
            item_id = int(entry)
        except (TypeError, ValueError):
            continue
        if 1 <= item_id <= 732 and item_id not in _SKIPPED_ITEM_IDS:
            normalized.add(item_id)
    return normalized


def updateItems(data, item_list):
    selected_ids = _normalize_item_ids(item_list)
    offs = getSectionOffsets(data)[3]
    for item_id in range(1, 733):
        if item_id in _SKIPPED_ITEM_IDS:
            continue
        entry_base = offs + (item_id - 1) * _ITEM_ENTRY_STRIDE
        unlock = item_id in selected_ids
        for offset in (entry_base, entry_base + 1):
            current_val = getInt(data, offset, num_bytes=1)
            if unlock:
                new_val = current_val | ITEM_FLAG_SEEN | ITEM_FLAG_TOUCHED | ITEM_FLAG_COLLECTED
            else:
                new_val = current_val & ~ITEM_UNLOCK_CLEAR_MASK
            if new_val != current_val:
                new_byte = bytes((new_val & 0xFF,))
                data = data[:offset] + new_byte + data[offset + 1:]
    return data


def markItemsSeen(data, item_list):
    selected_ids = _normalize_item_ids(item_list)
    if not selected_ids:
        return data
    offs = getSectionOffsets(data)[3]
    for item_id in selected_ids:
        if item_id in _SKIPPED_ITEM_IDS:
            continue
        entry_base = offs + (item_id - 1) * _ITEM_ENTRY_STRIDE
        for offset in (entry_base, entry_base + 1):
            current_val = getInt(data, offset, num_bytes=1)
            new_val = current_val | ITEM_FLAG_SEEN
            if new_val != current_val:
                new_byte = bytes((new_val & 0xFF,))
                data = data[:offset] + new_byte + data[offset + 1:]
    return data

def updateChecksum(data):
    offset = 0x10
    length = len(data) - offset - 4
    return data[:offset + length] + calcAfterbirthChecksum(data, offset, length).to_bytes(5, 'little', signed=True)[:4]


def ensureBestiaryEncounterMinimum(data, minimum=1, reference_data=None):
    try:
        offsets = getBestiaryOffsets(data)
    except (IndexError, ValueError):
        return data
    if minimum < 0:
        minimum = 0

    player_headers, player_maps, player_orders = _read_bestiary_groups(data, offsets)

    ref_headers = ref_maps = ref_orders = None
    reference_sections = _load_reference_bestiary(reference_data)
    if reference_sections:
        ref_headers, ref_maps, ref_orders = reference_sections
    ref_order = []
    if ref_orders:
        ref_order = ref_orders[3]

    player_order = player_orders[3] if player_orders else []
    final_order = []
    seen = set()
    for prefix in ref_order + player_order:
        if prefix not in seen:
            final_order.append(prefix)
            seen.add(prefix)
    if not final_order:
        return data

    changed = False
    group_chunks = []
    for index, offset in enumerate(offsets):
        header = bytearray(player_headers[index])
        if len(header) < _BESTIARY_HEADER_SIZE:
            header.extend(b"\x00" * (_BESTIARY_HEADER_SIZE - len(header)))
        player_map = player_maps[index]
        ref_map = ref_maps[index] if ref_maps else {}

        if not any(header[:4]) and ref_headers and index < len(ref_headers):
            header[:4] = ref_headers[index][:4]

        chunks = []
        for prefix in final_order:
            current_chunk_bytes = player_map.get(prefix)
            ref_chunk_bytes = ref_map.get(prefix) if ref_map else None
            if current_chunk_bytes is not None:
                chunk = bytearray(current_chunk_bytes)
            elif ref_chunk_bytes is not None:
                chunk = bytearray(ref_chunk_bytes)
                changed = True
            else:
                continue

            if ref_chunk_bytes is not None and (
                current_chunk_bytes is None or chunk[2:4] == b"\x00\x00"
            ):
                hp_bytes = ref_chunk_bytes[2:4]
                if chunk[2:4] != hp_bytes:
                    chunk[2:4] = hp_bytes
                    changed = True

            if index == 3:
                current_value = int.from_bytes(chunk[4:8], "little", signed=False)
                if current_chunk_bytes is None:
                    new_value = max(minimum, 1)
                else:
                    new_value = current_value if current_value >= minimum else minimum
                if new_value != current_value:
                    chunk[4:8] = new_value.to_bytes(4, "little", signed=False)
                    changed = True
            else:
                if current_chunk_bytes is None:
                    if any(chunk[4:8]):
                        chunk[4:8] = (0).to_bytes(4, "little", signed=False)
                        changed = True

            chunks.append(bytes(chunk))

        entry_count = len(chunks)
        header[4:8] = (entry_count * 4).to_bytes(4, "little", signed=False)
        group_chunks.append(bytes(header) + b"".join(chunks))

    if not changed:
        return data

    section_start = offsets[0]
    section_end = offsets[0]
    for index, offset in enumerate(offsets):
        original_count = len(player_orders[index])
        group_length = _BESTIARY_HEADER_SIZE + original_count * _BESTIARY_ENTRY_SIZE
        section_end = offset + group_length

    new_section = b"".join(group_chunks)
    return data[:section_start] + new_section + data[section_end:]

# updateWinStreak: alterInt(data, getSectionOffsets(data)[1] + 0x4 + 0x54, 30)
# updateGreedMachine: alterInt(data, getSectionOffsets(data)[1] + 0x4 + 0x1C8, 30)
# updateDonationMachine: alterInt(data, getSectionOffsets(data)[1] + 0x4 + 0x1B0, 30)

if __name__ == "__main__":
    offset = 0x10
    with open(filename, "rb") as file:
        data = file.read()
        length = len(data) - offset - 4
        checksum = calcAfterbirthChecksum(data, offset, length).to_bytes(5, 'little', signed=True)[:4]
        print(checksum)
        old_checksum = data[offset + length:]    
    # below are some examples on how to use this script that aren't covered in the gui implementation.
    
    # update a character's post-it: 0 is not completed, 1 is completed on normal, 2 is completed on hard. order is in checklist_order.
    data = updateCheckListUnlocks(data, characters.index("Maggie"), [0,0,1,0,2,1,0,1,0,0,0,2])
    # enable secrets for online beta NOTE: THIS HAS NOT BEEN TESTED ON THE ONLINE BETA!!! USE AT OWN RISK!!!
    secret_count = getSecretCount(data)
    for i in range(secret_count - 4, secret_count + 1):
        data = alterSecret(data, i)


    with open(filename, 'wb') as file:
        print(calcAfterbirthChecksum(data, offset, length).to_bytes(5, 'little', signed=True)[:4])
        file.write(updateChecksum(data))