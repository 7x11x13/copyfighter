import itertools
import json
import os
from typing import Iterator
from discord_webhook import DiscordEmbed, DiscordWebhook
from extensions import query, classify_claim, get_yt_session
import structlog

_log = structlog.get_logger()

_webhooks = {
    k: os.getenv(f"WEBHOOK_{k.upper()}")
    for k in ("new_claim", "claim_scored", "claim_disputed")
    if os.getenv(f"WEBHOOK_{k.upper()}")
}


def _get_claim_title(claim: dict):
    metadata = claim["asset"]["metadata"]
    if "soundRecording" in metadata:
        data = metadata["soundRecording"]
        return f"{', '.join(data.get('artists', ['Unknown']))} - {data['title']}"
    elif "composition" in metadata:
        data = metadata["composition"]
        return f"{', '.join(data.get('writers', ['Unknown']))} - {data['title']}"
    elif "movie" in metadata:
        data = metadata["movie"]
        return f"Movie: {data['title']}"
    else:
        raise ValueError(f"Unknown asset metadata: {metadata}")


def _discord_fields_from_video(video_id: str, video_title: str, claim_info: list):
    return [
        {
            "name": "Original",
            "value": f"[{video_title}](https://youtube.com/watch?v={video_id})",
        },
        {
            "name": "Claims",
            "value": "\n".join(
                f"{_get_claim_title(claim)} [{owner['displayName']}]"
                for claim, owner in claim_info
            ),
        },
    ]


def watch_claim_ids():
    session, session_data = get_yt_session()
    if session is None:
        return
    claims = session._get_claimed_videos(session_data)
    _log.info(f"Found {len(claims)} claims")
    for chunk in itertools.batched(claims, 50):
        response = query(
            f"INSERT OR IGNORE INTO Claims (Id, Title) VALUES {', '.join(['(?, ?)'] * len(chunk))}",
            params=list(
                itertools.chain.from_iterable(
                    [claim["videoId"], claim["title"]] for claim in chunk
                )
            ),
        )
        _log.debug(response, query="insert null claim", claims=chunk)


def fetch_claim_info():
    session, session_data = get_yt_session()
    if session is None:
        return
    response = query("SELECT Id, Title FROM Claims WHERE Claim IS NULL LIMIT 1")
    _log.debug(response, query="select null claim")
    if not (response and response[0].results):
        return

    result = response[0].results[0]
    video_title = result["Title"]
    video_id = result["Id"]
    info = session._get_claim_info(session_data, video_id)
    score = None
    for claim, owner in info:
        if owner["displayName"] == "Bquate Music":
            score = 10
    if len(info) > 1:
        score = 0
    if score is not None:
        response = query(
            "UPDATE Claims SET Claim=json(?), Score=? WHERE Id=?",
            params=[json.dumps(info), score, video_id],
        )
    else:
        response = query(
            "UPDATE Claims SET Claim=json(?) WHERE Id=?",
            params=[json.dumps(info), video_id],
        )
    url = _webhooks.get("new_claim")
    if url:
        embed = DiscordEmbed(
            title="New Claim",
            fields=_discord_fields_from_video(video_id, video_title, info),
            color="5ace65",
        )
        DiscordWebhook(url, embeds=[embed]).execute()
    _log.debug(response, query="update null claim", json=info)


def score_claim():
    response = query(
        "SELECT Id, Title, Claim FROM Claims WHERE Score IS NULL AND Claim IS NOT NULL AND Fake IS NULL LIMIT 1"
    )
    _log.debug(response, query="select unscored claim")
    if not (response and response[0].results):
        return

    result = response[0].results[0]
    claim = json.loads(result["Claim"])
    video_id = result["Id"]
    video_title = result["Title"]
    claim_data = claim[0][0]
    claim_title = _get_claim_title(claim_data)
    score = classify_claim(video_title, claim_title)
    if score is None:
        return
    response = query(
        "UPDATE Claims SET Score=? WHERE Id=?",
        params=[score, video_id],
    )
    _log.debug(response, query="insert score")
    url = _webhooks.get("claim_scored")
    if url:
        embed = DiscordEmbed(
            title="Claim Scored",
            description=f"Score: {score}",
            fields=_discord_fields_from_video(video_id, video_title, claim),
            color="8a5bcf",
        )
        DiscordWebhook(url, embeds=[embed]).execute()


def dispute_claim():
    response = query(
        "SELECT Id, Title, Claim FROM Claims WHERE Fake AND NOT(Claimed) LIMIT 1"
    )
    _log.debug(response, query="select fake claims")
    if not (response and response[0].results):
        return

    result = response[0].results[0]
    video_id = result["Id"]
    video_title = result["Title"]
    claim = json.loads(result["Claim"])
    claim_id = claim[0][0]["claimId"]
    justification = f"This is a fake claim. The real song is '{video_title}'"
    session, session_data = get_yt_session()
    if session is None:
        return
    session._dispute_claim(
        session_data, claim_id, video_id, justification, os.getenv("LEGAL_NAME")
    )
    response = query("UPDATE Claims SET Claimed=? WHERE Id=?", [1, video_id])
    _log.debug(response, query="update claimed")
    url = _webhooks.get("claim_disputed")
    if url:
        embed = DiscordEmbed(
            title="Claim Disputed",
            fields=_discord_fields_from_video(video_id, video_title, claim),
            color="da3c3c",
        )
        DiscordWebhook(url, embeds=[embed]).execute()
