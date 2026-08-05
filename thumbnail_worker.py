import asyncio
import os
from typing import List, Tuple

import aiohttp
import asyncpg
from bs4 import BeautifulSoup

# ==========================
# Configuration
# ==========================

DATABASE_URL = os.environ["DATABASE_URL"]

BASE_URL = "https://greenxh.blog/videos"

WORKER_ID = int(os.getenv("WORKER_ID", "0"))
TOTAL_WORKERS = int(os.getenv("TOTAL_WORKERS", "1"))

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "5"))

REQUEST_TIMEOUT = 20
MAX_RETRIES = 3


# ==========================
# Thumbnail Extraction
# ==========================

async def get_thumbnail(session: aiohttp.ClientSession, video_id: str):
    url = f"{BASE_URL}/{video_id}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        )
    }

    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:

                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")

                html = await response.text()

                soup = BeautifulSoup(html, "html.parser")

                # Preferred
                tag = soup.find("meta", property="og:image")
                if tag and tag.get("content"):
                    return tag["content"]

                # Fallback
                for link in soup.find_all("link", rel="preload"):
                    if link.get("as") != "image":
                        continue

                    href = link.get("href", "")

                    if "/promo/" in href:
                        continue

                    if "ic-vt" in href:
                        return href

                return None

        except Exception:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                return None


# ==========================
# Fetch Batch
# ==========================

FETCH_SQL = """
SELECT id, video_id
FROM videos
WHERE thumbnail IS NULL
AND MOD(id, $1) = $2
ORDER BY id
LIMIT $3;
"""


async def fetch_batch(conn):
    return await conn.fetch(
        FETCH_SQL,
        TOTAL_WORKERS,
        WORKER_ID,
        BATCH_SIZE,
    )


# ==========================
# Update Batch
# ==========================

UPDATE_SQL = """
UPDATE videos
SET thumbnail=$1
WHERE id=$2;
"""


async def update_batch(conn, updates):
    if not updates:
        return

    await conn.executemany(
        UPDATE_SQL,
        updates,
    )


# ==========================
# Worker
# ==========================

async def process_batch(pool):

    async with pool.acquire() as conn:

        rows = await fetch_batch(conn)

    if not rows:
        return False

    semaphore = asyncio.Semaphore(CONCURRENCY)

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    connector = aiohttp.TCPConnector(limit=CONCURRENCY)

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
    ) as session:

        async def process(row):

            async with semaphore:

                thumbnail = await get_thumbnail(
                    session,
                    row["video_id"],
                )

                return (
                    thumbnail,
                    row["id"],
                )

        tasks = [process(r) for r in rows]

        results = await asyncio.gather(*tasks)

    updates = [
        r for r in results
        if r[0] is not None
    ]

    async with pool.acquire() as conn:

        async with conn.transaction():

            await update_batch(
                conn,
                updates,
            )

    print(
        f"Worker {WORKER_ID}: "
        f"Fetched={len(rows)} "
        f"Updated={len(updates)} "
        f"Failed={len(rows)-len(updates)}"
    )

    return True


# ==========================
# Main
# ==========================

async def main():

    print("=" * 60)
    print(f"Worker        : {WORKER_ID}")
    print(f"Total Workers : {TOTAL_WORKERS}")
    print(f"Batch Size    : {BATCH_SIZE}")
    print(f"Concurrency   : {CONCURRENCY}")
    print("=" * 60)

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
    )

    processed_batches = 0

    while True:

        has_more = await process_batch(pool)

        if not has_more:
            break

        processed_batches += 1

    await pool.close()

    print()
    print("Finished.")
    print(f"Batches processed: {processed_batches}")


if __name__ == "__main__":
    asyncio.run(main())
