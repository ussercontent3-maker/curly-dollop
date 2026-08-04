from bs4 import BeautifulSoup
from urllib.parse import urlparse


def absolute_url(base_domain, url):

    if not url:
        return None

    url = url.strip()

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return base_domain.rstrip("/") + url

    if url.startswith("http://") or url.startswith("https://"):
        return url

    return base_domain.rstrip("/") + "/" + url.lstrip("/")


def is_video_path(path):

    if not path:
        return False

    return (
        path.startswith("/videos/")
        and len(path) > len("/videos/")
    )


def extract_video_id(element, href):

    video_id = element.get("data-video-id")

    if video_id:
        return str(video_id).strip()

    # Fallback: use final URL slug identifier
    path = urlparse(href).path.rstrip("/")

    if not path:
        return None

    slug = path.split("/")[-1]

    # Most source URLs use an identifier at the end.
    # Keep slug as fallback only.
    return slug


def parse_index_page(html, base_domain):

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    videos = {}

    # Primary selector.
    elements = soup.select(
        '[data-role="thumb-link"]'
    )

    for element in elements:

        href = element.get("href")

        if not href:
            continue

        absolute = absolute_url(
            base_domain,
            href
        )

        parsed = urlparse(absolute)

        if not is_video_path(
            parsed.path
        ):
            continue

        video_id = extract_video_id(
            element,
            absolute
        )

        if not video_id:
            continue

        video_id = str(video_id)

        videos[video_id] = {
            "video_id": video_id,
            "source_path": parsed.path,
            "source_domain": base_domain.replace(
                "https://",
                ""
            ).replace(
                "http://",
                ""
            )
        }

    return list(videos.values())


def parse_video_page(
    html,
    base_domain,
    discovered=None
):

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    discovered = discovered or {}

    record = {
        "video_id": discovered.get("video_id"),

        "title": None,

        "source_domain": base_domain.replace(
            "https://",
            ""
        ).replace(
            "http://",
            ""
        ),

        "source_path": discovered.get(
            "source_path"
        ),

        "thumbnail_url": None,

        "preview_url": None,

        "preview_fallback_url": None,

        "duration": None,

        "creator_name": None,

        "creator_path": None
    }


    # --------------------------------------------------
    # TITLE
    # --------------------------------------------------

    title = None

    # OpenGraph title
    og_title = soup.find(
        "meta",
        attrs={
            "property": "og:title"
        }
    )

    if og_title:
        title = og_title.get("content")

    # Page title fallback
    if not title and soup.title:
        title = soup.title.get_text(
            " ",
            strip=True
        )

    if title:
        record["title"] = title.strip()


    # --------------------------------------------------
    # THUMBNAIL
    # --------------------------------------------------

    og_image = soup.find(
        "meta",
        attrs={
            "property": "og:image"
        }
    )

    if og_image:
        record["thumbnail_url"] = (
            og_image.get("content")
        )


    # --------------------------------------------------
    # CANONICAL URL
    # --------------------------------------------------

    canonical = soup.find(
        "link",
        attrs={
            "rel": "canonical"
        }
    )

    if canonical:

        canonical_url = canonical.get(
            "href"
        )

        if canonical_url:

            parsed = urlparse(
                canonical_url
            )

            if is_video_path(
                parsed.path
            ):

                record["source_path"] = (
                    parsed.path
                )


    # --------------------------------------------------
    # PREVIEW VIDEO
    # --------------------------------------------------

    preview = soup.select_one(
        "[data-previewvideo]"
    )

    if preview:

        preview_url = preview.get(
            "data-previewvideo"
        )

        record["preview_url"] = (
            absolute_url(
                base_domain,
                preview_url
            )
        )


    # --------------------------------------------------
    # DURATION
    # --------------------------------------------------

    duration_element = soup.select_one(
        "[data-duration]"
    )

    if duration_element:

        duration = duration_element.get(
            "data-duration"
        )

        record["duration"] = duration


    # --------------------------------------------------
    # CREATOR
    # --------------------------------------------------

    creator_link = None

    for link in soup.select(
        'a[href*="/creators/"]'
    ):

        href = link.get("href")

        if not href:
            continue

        parsed = urlparse(
            absolute_url(
                base_domain,
                href
            )
        )

        if parsed.path.startswith(
            "/creators/"
        ):

            creator_link = link

            break


    if creator_link:

        record["creator_name"] = (
            creator_link.get_text(
                " ",
                strip=True
            )
        )

        record["creator_path"] = (
            urlparse(
                absolute_url(
                    base_domain,
                    creator_link.get(
                        "href"
                    )
                )
            ).path
        )


    return record
