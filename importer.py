import os
import gzip
import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from slugify import slugify

DATABASE_URL = os.environ["DATABASE_URL"]

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ---------------------------------------------------
# Create tables if missing
# ---------------------------------------------------

cur.execute("""
CREATE TABLE IF NOT EXISTS videos (
    id BIGSERIAL PRIMARY KEY,

    video_id TEXT UNIQUE NOT NULL,

    title TEXT NOT NULL,

    slug TEXT,

    source_path TEXT NOT NULL,

    thumbnail TEXT,

    preview TEXT,

    duration INTEGER,

    creator TEXT,

    categories TEXT[],

    created_at TIMESTAMP DEFAULT NOW()
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS imported_batches (
    filename TEXT PRIMARY KEY,

    imported_at TIMESTAMP DEFAULT NOW()
);
""")

conn.commit()

# ---------------------------------------------------
# Add categories column if table already exists
# ---------------------------------------------------

cur.execute("""
ALTER TABLE videos
ADD COLUMN IF NOT EXISTS categories TEXT[];
""")

conn.commit()

# ---------------------------------------------------
# Import batches
# ---------------------------------------------------

folder = Path("data/videos")

files = sorted(folder.glob("*.jsonl.gz"))

for batch in files:

    filename = batch.name

    cur.execute(
        "SELECT 1 FROM imported_batches WHERE filename=%s",
        (filename,)
    )

    if cur.fetchone():
        print(f"Skipping {filename}")
        continue

    print(f"Importing {filename}")

    rows = []

    with gzip.open(batch, "rt", encoding="utf8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            item = json.loads(line)

            # -----------------------------------------
            # Categories from parser
            # -----------------------------------------

            categories = item.get("categories", [])

            # Make sure categories is always a list
            if not isinstance(categories, list):
                categories = []

            rows.append(
                (
                    item["video_id"],

                    item["title"],

                    slugify(item["title"]),

                    item["source_path"],

                    item.get("thumbnail"),

                    item.get("preview"),

                    item.get("duration"),

                    item.get("creator"),

                    categories
                )
            )

    if not rows:
        print(f"No rows found in {filename}")
        continue

    # ---------------------------------------------------
    # Insert videos
    # ---------------------------------------------------

    execute_values(
        cur,

        """
        INSERT INTO videos
        (
            video_id,
            title,
            slug,
            source_path,
            thumbnail,
            preview,
            duration,
            creator,
            categories
        )

        VALUES %s

        ON CONFLICT (video_id)
        DO NOTHING
        """,

        rows,

        page_size=1000
    )

    # ---------------------------------------------------
    # Mark batch as imported
    # ---------------------------------------------------

    cur.execute(
        """
        INSERT INTO imported_batches(filename)
        VALUES(%s)
        """,
        (filename,)
    )

    conn.commit()

    print(f"Imported {filename}")

# ---------------------------------------------------
# Close
# ---------------------------------------------------

cur.close()
conn.close()

print("Finished.")
