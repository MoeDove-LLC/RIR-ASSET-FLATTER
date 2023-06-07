import requests
import json
import yaml
import ipaddress
import sys
import os
from pathlib import Path
import subprocess
import copy
as_set_src = os.environ["AS_SET_SRC"]
as_set_dst = os.environ["AS_SET_DST"]
password = os.environ["RIPE_MNT_PASSWD"]
max_depth = int(os.environ["MAX_DEPTH"])


dst_cache_file = Path("cache/dst_cache.json")
irrdb = "RIPE,APNIC,AFRINIC,ARIN,LACNIC,RADB"

src_url = f"https://rest.db.ripe.net/ripe/as-set/{as_set_src}"
dst_url = f"https://rest.db.ripe.net/ripe/as-set/{as_set_dst}?password={password}"
t1_asns = [ 701, 1239, 1299, 2914, 3257, 3320, 3356, 3491, 5511, 6453, 6461, 6762, 6830, 7018, 12956, 174, 1273, 2828, 4134, 4809, 4637, 6939, 7473, 7922, 9002 ]

headers = {
  'Content-Type': 'application/json',
  'Accept': 'application/json'
}

def extract_member(base_json):
    return list(map(lambda x:x["value"],filter(lambda x:x["name"] == "members", base_json["objects"]["object"][0]["attributes"]["attribute"])))

def index_of_first(lst, pred):
    for i, v in enumerate(lst):
        if pred(v):
            return i
    return 1

def pack_member(base_json,member_list):
    base_json = copy.deepcopy(base_json)
    old_list = base_json["objects"]["object"][0]["attributes"]["attribute"]
    first_member_idx = index_of_first(old_list,lambda x:x["name"] == "members")
    old_list = list(filter(lambda x:x["name"] != "members",old_list))
    new_list = old_list[0:first_member_idx] + [{"name": "members", "value": member, "referenced-type":"aut-num" if member[:2] == "AS" and member[2:].isdecimal() else "as-set" } for member in member_list] + old_list[first_member_idx:]
    base_json["objects"]["object"][0]["attributes"]["attribute"] = new_list
    return base_json
def getval(strin):
    return strin.split(":",1)[1].strip()

src_json = json.loads(requests.request("GET", src_url, headers=headers).text)
src_asset = extract_member(src_json)
if dst_cache_file.is_file():
    print("Previous dst_cache_file found")
    dst_json = json.loads(open(dst_cache_file).read())
else:
    print("Previous dst_cache_file not found, download from " + dst_url)
    dst_json = json.loads(requests.request("GET", dst_url, headers=headers).text)
dst_asset = extract_member(dst_json)

flatted_members = {}
for as_set in src_asset:
    if max_depth == -1:
        query = ["bgpq4", "-tj", "-S",irrdb , as_set]
    else:
        query = ["bgpq4", "-tj","-L",str(max_depth), "-S",irrdb , as_set]
    bgpq4_asns = subprocess.run(query, stdout=subprocess.PIPE).stdout.decode()
    asset_asns = json.loads(bgpq4_asns)["NN"]
    asset_t1s = sorted(set(asset_asns) & set(t1_asns))
    if len(asset_t1s)>0:
        print(f"Warning: {as_set} contains t1_asns:{asset_t1s}")
        continue
    for asn in asset_asns:
        flatted_members[asn] = 0
        
flatted_members = sorted(list(flatted_members.keys()))

old_member = dst_asset
new_member = list(map(lambda x:"AS" + str(x),flatted_members))

if old_member != new_member:
    dst_json_new = pack_member(dst_json,new_member)
    payload = json.dumps(dst_json_new)
    response = requests.request("PUT", dst_url, headers=headers, data=payload)
    response.raise_for_status()
    dst_json_new = json.loads(response.text)
    print("updated:",as_set_dst)
    print("old member:",old_member)
    print("new member:",new_member)
else:
    print("same, no update:",as_set_dst)
    
open(dst_cache_file,"w").write(json.dumps(dst_json_new))
