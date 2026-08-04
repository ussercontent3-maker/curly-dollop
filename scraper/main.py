import gzip
import json
import time
from pathlib import Path

from scraper.config import load_config
from scraper.crawler import Crawler
from scraper.parser import (
    parse_index_page,
    parse_video_page
)

from scraper.checkpoint import (
    load_checkpoint,
    save_checkpoint,
    mark_started,
    mark_completed,
    mark_failed
)


ROOT_DIR = Path(__file__).resolve().parent.parent

DISCOVERED_DIR = (
    ROOT_DIR /
    "data" /
    "discovered"
)

VIDEOS_DIR = (
    ROOT_DIR /
    "data" /
    "videos"
)


def write_jsonl_gz(
    records,
    output_file
):

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with gzip.open(
        output_file,
        "wt",
        encoding="utf-8"
    ) as f:

        for record in records:

            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                )
                + "\n"
            )


def run():

    config = load_config()

    checkpoint = load_checkpoint(
        config
    )

    mark_started(
        checkpoint
    )

    save_checkpoint(
        checkpoint
    )


    crawler = Crawler(

        user_agent=config[
            "user_agent"
        ],

        timeout=config[
            "request_timeout"
        ],

        max_retries=config[
            "max_retries"
        ]
    )


    domain = config[
        "active_domain"
    ].rstrip("/")


    start_page = (
        checkpoint[
            "last_index_page"
        ]
        + 1
    )

    end_page = config[
        "end_page"
    ]


    seen_ids = set(
        checkpoint.get(
            "seen_video_ids",
            []
        )
    )


    batch_size = config[
        "batch_size"
    ]


    video_batch = []

    batch_number = (
        checkpoint[
            "last_batch"
        ]
        + 1
    )


    try:

        for page_number in range(
            start_page,
            end_page + 1
        ):

            index_url = (
                f"{domain}/{page_number}"
            )

            print(
                f"\nINDEX PAGE {page_number}: "
                f"{index_url}"
            )


            html = crawler.fetch(
                index_url
            )


            if not html:

                print(
                    "Failed to fetch index page."
                )

                checkpoint[
                    "failed_pages"
                ].append(
                    page_number
                )

                save_checkpoint(
                    checkpoint
                )

                continue


            discovered = (
                parse_index_page(
                    html,
                    domain
                )
            )


            print(
                f"Found "
                f"{len(discovered)} "
                f"video links."
            )


            for item in discovered:

                video_id = item[
                    "video_id"
                ]


                if video_id in seen_ids:

                    continue


                seen_ids.add(
                    video_id
                )


                checkpoint[
                    "seen_video_ids"
                ].append(
                    video_id
                )


                checkpoint[
                    "discovered_videos"
                ] += 1


                source_url = (
                    domain
                    + item[
                        "source_path"
                    ]
                )


                print(
                    f"Scraping: "
                    f"{source_url}"
                )


                video_html = crawler.fetch(
                    source_url
                )


                checkpoint[
                    "processed_videos"
                ] += 1


                if not video_html:

                    checkpoint[
                        "failed_videos"
                    ] += 1

                    continue


                record = (
                    parse_video_page(
                        video_html,
                        domain,
                        item
                    )
                )


                # Basic validation
                if not record.get(
                    "title"
                ):

                    print(
                        "WARNING: "
                        "No title found."
                    )


                # Explicitly prevent HLS fields
                record.pop(
                    "hls_url",
                    None
                )

                record.pop(
                    "m3u8_url",
                    None
                )

                record.pop(
                    "video_url",
                    None
                )

                record.pop(
                    "stream_url",
                    None
                )


                video_batch.append(
                    record
                )


                checkpoint[
                    "successful_videos"
                ] += 1


                # Save checkpoint batch
                if len(
                    video_batch
                ) >= batch_size:

                    output_file = (
                        VIDEOS_DIR /
                        f"batch_{batch_number:06d}.jsonl.gz"
                    )


                    write_jsonl_gz(
                        video_batch,
                        output_file
                    )


                    checkpoint[
                        "last_batch"
                    ] = batch_number


                    print(
                        f"Saved batch "
                        f"{batch_number}: "
                        f"{len(video_batch)} records"
                    )


                    video_batch = []

                    batch_number += 1


                    save_checkpoint(
                        checkpoint
                    )


                time.sleep(
                    config[
                        "video_delay_seconds"
                    ]
                )


            checkpoint[
                "last_index_page"
            ] = page_number


            save_checkpoint(
                checkpoint
            )


            print(
                f"Checkpoint saved "
                f"at page {page_number}"
            )


            time.sleep(
                config[
                    "index_delay_seconds"
                ]
            )


        # Save remaining records
        if video_batch:

            output_file = (
                VIDEOS_DIR /
                f"batch_{batch_number:06d}.jsonl.gz"
            )


            write_jsonl_gz(
                video_batch,
                output_file
            )


            checkpoint[
                "last_batch"
            ] = batch_number


        mark_completed(
            checkpoint
        )

        save_checkpoint(
            checkpoint
        )


        print(
            "\nSCRAPING COMPLETE"
        )


    except KeyboardInterrupt:

        print(
            "\nInterrupted. "
            "Saving checkpoint."
        )

        mark_failed(
            checkpoint
        )

        save_checkpoint(
            checkpoint
        )


    except Exception as e:

        print(
            f"\nFatal error: {e}"
        )

        mark_failed(
            checkpoint
        )

        save_checkpoint(
            checkpoint
        )

        raise


if __name__ == "__main__":
    run()
