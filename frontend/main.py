import logging
import os
import re

import disnake
from disnake import ApplicationCommandInteraction as ACI
from disnake.ext import commands
from dotenv import load_dotenv
from extensions import query

from ui import PaginatorView, video_claims_to_lines

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

intents = disnake.Intents.default()
intents.message_content = True
client = commands.InteractionBot(intents=intents)

embed_id_regex = re.compile(
    r"^\[.*\]\(https://youtube.com/watch\?v=(?P<id>[a-zA-Z\d\-_]+)\)$"
)


@client.event
async def on_ready():
    log.info(f"Logged in as {client.user}")


@client.event
async def on_raw_reaction_add(event: disnake.RawReactionActionEvent):
    if event.channel_id != int(os.getenv("CLAIM_CHANNEL")):
        return
    channel = await client.fetch_channel(event.channel_id)
    msg = await channel.fetch_message(event.message_id)
    if event.member.id != int(os.getenv("ADMIN_ID")):
        return

    emoji = event.emoji.name
    if emoji in "👍✅✔️☑️":
        fake = False
    elif emoji in "👎❌✖️🚫":
        fake = True
    else:
        return

    def find_video_id(embed: disnake.Embed):
        for field in embed.fields:
            if field.name == "Original":
                return embed_id_regex.match(field.value).group("id")

    video_id = find_video_id(msg.embeds[0])
    response = query(
        "UPDATE Claims SET Fake=? WHERE Id=?",
        params=[int(fake), video_id],
    )
    clear_videos_cache()
    log.info(f"Update {video_id}: Fake={int(fake)}, response: {response}")


def check_admin(inter: ACI):
    return inter.user.id == int(os.getenv("ADMIN_ID"))


videos_cache = []


def clear_videos_cache():
    global videos_cache
    videos_cache = []


@client.slash_command(
    name="claim_queue", description="View unclassified copyright claims"
)
@commands.check(check_admin)
async def claim_queue(inter: ACI, clear_cache: bool = False):
    global videos_cache
    if clear_cache:
        clear_videos_cache()
    await inter.response.defer()
    if not videos_cache:
        response = query(
            "SELECT Id, Title, Claim, Score FROM Claims WHERE Claim IS NOT NULL AND Fake IS NULL ORDER BY Score DESC"
        )
        if not (response and response[0].results):
            return
        results = response[0].results
        videos_cache = results
    lines = video_claims_to_lines(videos_cache)
    await PaginatorView(
        "Unclassified Claims", disnake.Color.green(), lines, inter.author.id
    ).send(inter, deferred=True)


@client.slash_command(name="mark_claims", description="Mark claims as fake or real")
@commands.check(check_admin)
async def mark_claims(inter: ACI, fake: bool, start: int, end: int = None):
    if end is None:
        end = start
    start -= 1  # 1-indexed

    video_ids = [video["Id"] for video in videos_cache[start:end]]

    response = query(
        f"UPDATE Claims SET Fake=? WHERE Id IN ({', '.join(['?'] * len(video_ids))})",
        params=[int(fake), *video_ids],
    )
    log.info(f"Marked videos Fake={int(fake)}: {video_ids}, response: {response}")
    clear_videos_cache()
    await inter.send("Success!")


@client.event
async def on_slash_command_error(inter: ACI, error: commands.CommandError):
    if isinstance(error, commands.CheckFailure):
        await inter.send("Missing permissions", ephemeral=True)
        return
    await inter.send("Internal bot error")
    logging.exception(error)


def main():
    token = os.getenv("BOT_TOKEN")
    client.run(token)


if __name__ == "__main__":
    main()
