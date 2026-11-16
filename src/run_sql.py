"""Run every query in sql/ on the simulated tables (DuckDB) and save each result to data/output/sql_<name>.csv.

Usage:  python src/run_sql.py            (all files)
        python src/run_sql.py 06         (files whose name starts with 06)
"""
import sys

from common import OUT, SQL, sim_con, utf8


def run(name, con=None):
    con = con or sim_con()
    return con.sql((SQL / name).read_text(encoding="utf-8")).df()


if __name__ == "__main__":
    utf8()
    OUT.mkdir(parents=True, exist_ok=True)
    con = sim_con()
    for f in sorted(SQL.glob("*.sql")):
        if len(sys.argv) > 1 and not f.name.startswith(sys.argv[1]):
            continue
        df = run(f.name, con)
        df.to_csv(OUT / f"sql_{f.stem}.csv", index=False)
        print(f"{f.name:34s} {len(df):>8,} rows")
