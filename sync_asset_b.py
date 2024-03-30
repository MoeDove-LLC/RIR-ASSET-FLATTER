import requests
import json
import yaml
import ipaddress
import sys
import os
from pathlib import Path
import subprocess
import copy
import xmltodict

as_set_dst = os.environ["AS_SET_DST"]
apikey = os.environ["ARIN_APIKEY"]
memeber_cache_file = Path(os.environ["MEM_CACHE_FILE"])

dst_cache_file = Path("cache/dst_cache_arin.json")

dst_url = f"https://reg.arin.net/rest/irr/as-set/{as_set_dst}?apikey={apikey}"

headers = {
    'Content-Type': 'application/xml',
    'Accept': 'application/xml'
}

def extract_member(base_json):
    # Extract AS-SET members from the original JSON
    if 'member' in base_json['asSet']['members']:
        members = base_json['asSet']['members']['member']
        if isinstance(members, list):
            return sorted([member['@name'] for member in members])
        elif isinstance(members, dict):
            return sorted([members['@name']])
    return []

def turn2xml(strin):
    strout = {}
    strout['@name'] = strin
    return strout


def pack_member(base_json, member_list):
    # Pack AS-SET members
    base_json['asSet']['members']['member'] = list(map(turn2xml, sorted(set(member_list, reserved = True))))
    return base_json

# SRC AS-SET members retrieval
if memeber_cache_file.is_file():
    print("Previous member_cache_file found")
    src_as = sorted(list(json.loads(open(memeber_cache_file).read())))
else:
    print("Previous member_cache_file not found!")

# DST AS-SET retrieval
if dst_cache_file.is_file():
    print("Previous dst_cache_file found")
    dst_json = json.loads(open(dst_cache_file).read())
else:
    print("Previous dst_cache_file not found, download from " + dst_url)
    dst_json = xmltodict.parse(requests.request("GET", dst_url, headers=headers).text)

dst_asset = extract_member(dst_json)

new_member_add = list(set(src_as) - set(dst_asset))
new_member_remove = list(set(dst_asset) - set(src_as))

if dst_asset != src_as:
    payload = xmltodict.unparse(pack_member(dst_json, src_as)).replace("\n", "")
    response = requests.request("PUT", dst_url, headers=headers, data=payload)
    response.raise_for_status()
    dst_json_new = xmltodict.parse(response.text)
    print("Updated:", as_set_dst)
    print("Old members:", dst_asset)
    print("New members added:", new_member_add)
    print("Old members removed:", new_member_remove)
else:
    dst_json_new = dst_json
    print("Same, no update:", as_set_dst)

open(dst_cache_file, "w").write(json.dumps(dst_json_new))
