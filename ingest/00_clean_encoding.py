#!/usr/bin/env python3
"""CMS publishes some CSVs as UTF-8 with stray Windows-1252 bytes (en dashes, accented names). DuckDB refuses both
utf-8 and latin-1 for those. This writes clean UTF-8 copies under data/clean/<subdir>/ (per-line fallback: utf-8, then cp1252)
and symlinks files that are already valid UTF-8. Re-runnable."""
import glob, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
SUBDIRS = ["cms_enrollment", "cms_program_integrity", "oig_leie", "care_compare", "cms_pos", "sam_exclusions", "state_exclusions"]
for sub in SUBDIRS:
    os.makedirs(f"data/clean/{sub}", exist_ok=True)
    for src in sorted(glob.glob(f"data/{sub}/*.csv") + glob.glob(f"data/{sub}/*.CSV")):
        dst = f"data/clean/{sub}/{os.path.basename(src)}"; t = time.time()
        if os.path.exists(dst) and not os.path.islink(dst) and os.path.getmtime(dst) >= os.path.getmtime(src): continue
        raw = open(src, "rb").read()
        try:
            raw.decode("utf-8"); ok = True
        except UnicodeDecodeError: ok = False
        if ok:
            if os.path.lexists(dst): os.remove(dst)
            os.symlink(os.path.relpath(src, os.path.dirname(dst)), dst); print(f"utf8-ok  {src}"); continue
        bad = 0
        with open(dst, "wb") as out:
            for line in raw.split(b"\n"):
                try: out.write(line.decode("utf-8").encode("utf-8") + b"\n")
                except UnicodeDecodeError:
                    bad += 1; out.write(line.decode("cp1252", errors="replace").encode("utf-8") + b"\n")
        # drop the trailing extra newline we added after the final split element
        with open(dst, "rb+") as f:
            f.seek(-1, 2); f.truncate() if raw.endswith(b"\n") or True else None
        print(f"cleaned  {src}: {bad} lines re-decoded from cp1252 ({time.time()-t:.1f}s)")
