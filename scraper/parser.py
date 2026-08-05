import re
import json
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

    path = urlparse(href).path.rstrip("/")

    if not path:
        return None

    slug = path.split("/")[-1]

    return slug


def parse_index_page(html, base_domain):

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    videos = {}

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


# --------------------------------------------------
# JSON STATE EXTRACTION (window.initials fallback)
# --------------------------------------------------
# Many tube-site templates only populate og:image / data-duration /
# creator <a> tags via client-side JS. The real data still ships
# server-side inside `<script id='initials-script'>window.initials={...}</script>`.
# We parse that blob once per page and use it purely as a fallback
# for fields the DOM-based selectors failed to find.

_INITIALS_RE = re.compile(
    r"id=['\"]initials-script['\"]>\s*window\.initials\s*=\s*(\{.*?\})\s*;\s*</script>",
    re.DOTALL
)


def _extract_initials(html):
    """Return the parsed window.initials dict, or None if not found/invalid."""
    match = _INITIALS_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _get_video_model(initials):
    """Digs into window.initials to find the videoModel/videoEntity blocks."""
    if not initials:
        return {}, {}
    video_model = initials.get("videoModel") or {}
    video_entity = initials.get("videoEntity") or {}
    return video_model, video_entity


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

    # Parse the embedded JSON state once, reused by thumbnail/duration/creator below.
    initials = _extract_initials(html)
    video_model, video_entity = _get_video_model(initials)


    # --------------------------------------------------
    # TITLE
    # --------------------------------------------------

    title = None

    og_title = soup.find(
        "meta",
        attrs={
            "property": "og:title"
        }
    )

    if og_title:
        title = og_title.get("content")

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

    if not record["thumbnail_url"]:
        record["thumbnail_url"] = (
            video_model.get("thumbURL")
            or video_entity.get("thumbBig")
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

    if not record["preview_url"]:
        trailer_url = video_model.get("trailerURL")
        if trailer_url:
            record["preview_url"] = trailer_url

    if not record["preview_fallback_url"]:
        trailer_fallback = video_model.get("trailerFallbackUrl")
        if trailer_fallback:
            record["preview_fallback_url"] = trailer_fallback


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

    if record["duration"] in (None, ""):
        duration = video_model.get("duration")
        if duration is not None:
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

    if not record["creator_name"] or not record["creator_path"]:
        author = video_model.get("author") or {}
        landing = video_model.get("landing") or {}

        creator_name = author.get("name") or landing.get("name")
        creator_link_url = landing.get("link") or author.get("pageURL")

        if not record["creator_name"] and creator_name:
            record["creator_name"] = creator_name.strip() if isinstance(creator_name, str) else creator_name
        if not record["creator_path"] and creator_link_url:
            record["creator_path"] = urlparse(creator_link_url).path


    return record


if __name__ == "__main__":
    sample_html = '''
    <html><head>
    <title>Some Video Title</title>
    </head><body>
    <script id='initials-script'>window.initials={"videoModel":{"id":24435270,"duration":458,"thumbURL":"https://ic-vt-nss.cdnsolutions.media/a/HASH/s(w:1280,h:720),webp/024/435/270/v2/2560x1440.212.webp","trailerURL":"https://thumb-v0.cdnsolutions.media/a/x/024/435/270/526x298.94.3.4.t.mp4","author":{"name":"Pofegistka","pageURL":"https://greenxh.blog/users/pofegistka"},"landing":{"type":"person","name":"Pofegistka","link":"https://greenxh.blog/creators/pofegistka"}},"videoEntity":{"thumbBig":"https://ic-vt-nss.cdnsolutions.media/a/HASH2/s(w:526,h:298),webp/024/435/270/v2/526x298.212.webp"}};</script>
    </body></html>
    '''
    rec = parse_video_page(sample_html, "https://greenxh.blog", {"video_id": "24435270", "source_path": "/videos/foo"})
    print(json.dumps(rec, indent=2))
