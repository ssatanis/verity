"""One-off: remove duplicate flag ids left by earlier runs (the inserts now dedupe themselves)."""
import os, duckdb
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
before = con.execute("SELECT count(*) FROM flags").fetchone()[0]
con.execute("CREATE OR REPLACE TABLE flags AS SELECT * FROM flags QUALIFY row_number() OVER (PARTITION BY id ORDER BY score DESC NULLS LAST) = 1")
print("flags", before, "->", con.execute("SELECT count(*) FROM flags").fetchone()[0], "dups now", con.execute("SELECT count(*) - count(DISTINCT id) FROM flags").fetchone()[0])
