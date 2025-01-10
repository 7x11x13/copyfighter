import os
import urllib.parse
from http.cookiejar import Cookie, FileCookieJar

import requests
import structlog
from cloudflare import Cloudflare
from dotenv import load_dotenv
from youtube_up import YTUploaderSession, YTUploaderException

load_dotenv()
log = structlog.get_logger()

client = Cloudflare()
ai = client.workers.ai
database = client.d1.database


def query(sql: str, params: list = None):
    return database.query(
        database_id=os.getenv("D1_DATABASE_ID"),
        account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        sql=sql,
        params=params,
    )


def classify_claim(video_title: str, claim_title: str):
    response = ai.run(
        model_name="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        messages=[
            {
                "role": "system",
                "content": "You will be given a song artist and title, followed by the song artist and title of a copyright claim on the first song. You will give a score from 0-10 determining how likely it is that the copyright claim is valid. Only answer with a number 0-10, where 10 means the copyright claim is valid.",
            },
            {"role": "user", "content": f"{video_title}\n{claim_title}"},
        ],
        max_tokens=1,
    )
    log.debug(response, video_title=video_title, claim_title=claim_title)
    if not response:
        return None
    try:
        score = int(response["response"])
        if 0 <= score <= 10:
            return 10 - score
        return None
    except Exception:
        return None


_cookie_relay_url = os.getenv("COOKIE_RELAY_URL")
_cookie_relay_api_key = os.getenv("COOKIE_RELAY_API_KEY")
_channel_id = os.getenv("CHANNEL_ID")


def _get_cookies(user_id: str) -> list[Cookie]:
    url = urllib.parse.urljoin(_cookie_relay_url, f"/cookies/youtube/{user_id}")
    with requests.get(
        url, headers={"Cookie-Relay-API-Key": _cookie_relay_api_key}
    ) as r:
        r.raise_for_status()
        cookies = []
        for data in r.json():
            rest = {}
            if data.get("httpOnly"):
                rest["HTTPOnly"] = ""
            cookie = Cookie(
                0,
                data["name"],
                data["value"],
                None,
                False,
                data["domain"],
                True,
                data["domain"].startswith("."),
                data["path"],
                True,
                data["secure"],
                data["expirationDate"] or None,
                False,
                None,
                None,
                rest,
            )
            cookies.append(cookie)
    return cookies


class APIFileCookieJar(FileCookieJar):
    def load(self, filename=None, ignore_discard=False, ignore_expires=False):
        for cookie in _get_cookies(_channel_id):
            self.set_cookie(cookie)

    def save(self, filename=None, ignore_discard=False, ignore_expires=False):
        return


_session: YTUploaderSession = None
_session_data: dict = None


def get_yt_session() -> tuple[YTUploaderSession, dict]:
    global _session
    global _session_data
    try:
        if _session is not None and _session.has_valid_cookies():
            return _session, _session_data
    except Exception:
        pass

    _session = YTUploaderSession(APIFileCookieJar())
    try:
        _session_data = _session._get_session_data()
    except YTUploaderException:
        return None, None
    return _session, _session_data
