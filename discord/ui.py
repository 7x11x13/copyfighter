import json
import disnake as ds
from disnake.utils import escape_markdown as escape
from disnake import ApplicationCommandInteraction as ACI

INDENT_CHAR = "— "


def _indent_lines(lines: list[str], start: int = 0, end: int = None):
    if end is None:
        end = len(lines)
    for i in range(start, end):
        lines[i] = INDENT_CHAR + lines[i]


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


def _video_claim_to_lines(video_id: str, video_title: str, claims: list):
    lines = [f"[{escape(video_title)}](https://youtube.com/watch?v={video_id})"]
    for claim, owner in claims:
        lines.append(f"{_get_claim_title(claim)} [{owner['displayName']}]")
    return lines


def video_claims_to_lines(results: list):
    lines = []
    for i, item in enumerate(results, start=1):
        i_lines = _video_claim_to_lines(
            item["Id"], item["Title"], json.loads(item["Claim"])
        )
        i_lines[0] = f"**{i}** - {i_lines[0]} ({item['Score']})"
        _indent_lines(i_lines, start=1)
        lines += i_lines
        lines.append("")
    if lines:
        lines.pop()  # remove empty last line
    return lines


class PaginatorView(ds.ui.View):
    MAX_EMBED_DESC_LENGTH = 4096

    def __init__(
        self,
        title: str,
        color: ds.Color,
        lines: list[str],
        author: int,
        timeout: float = 600,
        empty_lines_desc: str = "",
    ):
        super().__init__(timeout=timeout)
        embeds = self._create_embeds(lines, title, color, empty_lines_desc)
        self._embeds = embeds
        self._last_page = len(embeds) - 1
        self._author = author
        self._cur_page = 0
        self._buttons: dict[str, ds.ui.Button] = {}
        if len(embeds) == 1:
            # delete buttons
            self.children = []
        else:
            for child in self.children:
                if isinstance(child, ds.ui.Button):
                    self._buttons[child.custom_id] = child
            self._disable_buttons()

    async def send(self, inter: ACI, deferred: bool = False):
        if deferred:
            return await inter.followup.send(embed=self._embeds[0], view=self)
        else:
            return await inter.send(embed=self._embeds[0], view=self)

    def _create_embeds(
        self,
        lines: list[str],
        title: str,
        color: ds.Color,
        empty_lines_desc: str | None,
    ):
        embeds: list[ds.Embed] = []
        cur_desc = ""
        for line in lines:
            if len(line) + len(cur_desc) <= self.MAX_EMBED_DESC_LENGTH:
                cur_desc += line + "\n"
            else:
                embeds.append(ds.Embed(description=cur_desc, color=color, title=title))
                cur_desc = ""
        if cur_desc:
            cur_desc = cur_desc[:-1]  # remove trailing newline
            embeds.append(ds.Embed(description=cur_desc, color=color, title=title))
        elif embeds:
            embeds[-1].description = embeds[-1].description[
                :-1
            ]  # remove trailing newline
        else:
            embeds.append(
                ds.Embed(description=empty_lines_desc, color=color, title=title)
            )
        return embeds

    def _disable_buttons(self):
        self._buttons["button.prev"].disabled = self._cur_page <= 0
        self._buttons["button.next"].disabled = self._cur_page >= self._last_page

    @ds.ui.button(label="Back", style=ds.ButtonStyle.primary, custom_id="button.prev")
    async def previous(self, button: ds.ui.Button, inter: ACI):
        if inter.author.id != self._author:
            return await inter.send(
                "You cannot interact with these buttons", ephemeral=True
            )

        if self._cur_page > 0:
            self._cur_page -= 1
            self._disable_buttons()
            await inter.response.edit_message(
                embed=self._embeds[self._cur_page], view=self
            )

    @ds.ui.button(label="Next", style=ds.ButtonStyle.primary, custom_id="button.next")
    async def next(self, button: ds.ui.Button, inter: ACI):
        if inter.author.id != self._author:
            return await inter.send(
                "You cannot interact with these buttons", ephemeral=True
            )

        if self._cur_page < self._last_page:
            self._cur_page += 1
            self._disable_buttons()
            await inter.response.edit_message(
                embed=self._embeds[self._cur_page], view=self
            )
