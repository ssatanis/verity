#!/usr/bin/env python3
"""Run the Verity tripwire over a real Blue Button EOB bundle on disk (no OAuth needed).
Any Medicare beneficiary can export their own claims from Medicare.gov (Blue Button download, JSON). Point this at that file.
  python3 scripts/bluebutton_offline_verify.py path/to/ExplanationOfBenefit_bundle.json
  python3 scripts/bluebutton_offline_verify.py --npis 1234567890,0987654321      # check NPIs directly against the warehouse"""
import sys, os, json, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
from dotenv import load_dotenv; load_dotenv(".env")
from api import bluebutton as bb, verify as vf
ap = argparse.ArgumentParser(); ap.add_argument("bundle", nargs="?")
ap.add_argument("--npis", help="comma-separated NPIs to check directly instead of a bundle"); a = ap.parse_args()
if a.npis:
    for e in vf.events_for(a.npis.split(",")): print(e)
    sys.exit()
if not a.bundle: sys.exit("give a bundle path or --npis")
claims = bb.normalize_eobs(json.load(open(a.bundle)))
print(f"{len(claims)} claims; types: {sorted({c['type'] for c in claims})}; NPIs: {sorted({n for c in claims for n in c['npis']})[:10]}")
res = vf.verify_claims(claims)
print(json.dumps({k: v for k, v in res.items() if k != "providers"}, indent=1, default=str)[:3000])
