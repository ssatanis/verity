"""Reload the timecodes table (DuckDB and Postgres) from ingest/02_timecodes.csv after QA edits. Run when no detector holds the DuckDB lock."""
import os, duckdb, psycopg
from dotenv import load_dotenv; load_dotenv(".env")
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
con.execute("""CREATE OR REPLACE TABLE timecodes AS
SELECT hcpcs, description, TRY_CAST(minutes_per_unit AS DOUBLE) AS minutes_per_unit, unit_basis,
       COALESCE(TRY_CAST(group_divisor AS INTEGER), 1) AS group_divisor, family, fraud_vector,
       TRY_CAST(mn_rate_per_unit AS DOUBLE) AS mn_rate_per_unit, TRY_CAST(mn_daily_cap_hours AS DOUBLE) AS mn_daily_cap_hours, personal_service = 'Y' AS personal_service, source, notes
FROM read_csv_auto('ingest/02_timecodes.csv', all_varchar=true, header=true)""")
print("duckdb timecodes:", con.execute("SELECT count(*), count(*) FILTER (WHERE personal_service) FROM timecodes").fetchone())
rows = con.execute("SELECT hcpcs, personal_service FROM timecodes").fetchall(); con.close()
with psycopg.connect(os.environ["DATABASE_URL"]) as pg:
    with pg.cursor() as c:
        for h, p in rows: c.execute("UPDATE public.timecodes SET personal_service = %s WHERE hcpcs = %s", (p, h))
    pg.commit(); print("postgres timecodes updated", len(rows))
