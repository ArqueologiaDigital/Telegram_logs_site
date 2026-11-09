"""How many Pagefind bundle files change when N new messages arrive (gh-pages growth per day)?
   ../.venv/bin/python -I tests/search_churn.py SCRATCH_DIR 20
   (2026-11-09: 20 new messages -> 119 new/changed files, 3.58 MB; index 94 of 163 chunks)"""
import os, sys, filecmp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build as B, search_index as S
out, n = sys.argv[1], int(sys.argv[2])
class O: deleted = "placeholder"; phones = "review"; media_base = "x/"
d = B.Data(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "Telegram_logs")); B.mark_phones(d, O)
recs = list(S.records(d, O))
S.write_index(recs[:-n], os.path.join(out, "before")); S.write_index(recs, os.path.join(out, "after"))
def files(r): return {os.path.relpath(os.path.join(a, f), r) for a, _, fs in os.walk(r) for f in fs}
a, b = files(os.path.join(out, "before")), files(os.path.join(out, "after"))
same = {f for f in a & b if filecmp.cmp(os.path.join(out, "before", f), os.path.join(out, "after", f), shallow=False)}
new = b - same
size = sum(os.path.getsize(os.path.join(out, "after", f)) for f in new)
print(f"{n} new messages: {len(b)} files after, {len(new)} new/changed ({size/1e6:.2f} MB), {len(a - b)} removed")
for top in ("fragment", "index", "filter"):
    print(f"  {top}: {sum(1 for f in new if f.startswith(top + '/'))} new/changed")
