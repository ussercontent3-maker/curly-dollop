import time
import requests


class Crawler:

    def __init__(
        self,
        user_agent,
        timeout=30,
        max_retries=3
    ):

        self.timeout = timeout
        self.max_retries = max_retries

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        })


    def fetch(self, url):

        for attempt in range(1, self.max_retries + 1):

            try:

                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True
                )

                if response.status_code == 200:

                    return response.text

                print(
                    f"HTTP {response.status_code} "
                    f"for {url}"
                )

            except requests.RequestException as e:

                print(
                    f"Request failed "
                    f"(attempt {attempt}/{self.max_retries}): "
                    f"{e}"
                )

            if attempt < self.max_retries:

                time.sleep(
                    min(attempt * 2, 10)
                )

        return None
