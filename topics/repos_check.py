#!/usr/bin/env python3
"""Is topics/repos.json up to date with the organisation's public repositories on GitHub?

Lists public repos that the catalogue lacks, and catalogue entries that no longer exist. One
unauthenticated GitHub API request; run by hand when a repository is created or renamed.

    python3 -I topics/repos_check.py
"""
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "repos.json"), encoding="utf-8") as f:
    doc = json.load(f)
url = f"https://api.github.com/orgs/{doc['org']}/repos?per_page=100&type=public"
live = {r["name"] for r in json.load(urllib.request.urlopen(url, timeout=30))}
have = {r["name"] for g in doc["groups"] for r in g["repos"]}
print(f"{len(live)} public repos on GitHub, {len(have)} in the catalogue")
print("missing from the catalogue:", sorted(live - have) or "none")
print("in the catalogue but not on GitHub:", sorted(have - live) or "none")
