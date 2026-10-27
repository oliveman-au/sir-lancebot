import unittest
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.exts.utilities.emoji import Emojis


class EmojiInfoTests(unittest.IsolatedAsyncioTestCase):
    """Exercise emoji info with Discord's timezone-aware creation timestamps."""

    async def test_info_preserves_creation_timezone(self) -> None:
        """Send the info embed without mixing naive and aware datetimes."""
        now = datetime(2026, 1, 3, 12, tzinfo=UTC)
        for tz in (UTC, timezone(timedelta(hours=5))):
            with self.subTest(timezone=tz):
                emoji = SimpleNamespace(
                    name="python", id=123,
                    created_at=(now - timedelta(days=2, hours=3)).astimezone(tz),
                    url="https://cdn.discordapp.com/emojis/123.png",
                )
                ctx = SimpleNamespace(send=AsyncMock())
                with patch("bot.utils.time.datetime") as clock:
                    clock.now.return_value = now
                    await Emojis.info_command.callback(Emojis(None), ctx, emoji)

                ctx.send.assert_awaited_once()
                embed = ctx.send.call_args.kwargs["embed"]
                self.assertIn("**Created:** 2 days and 3 hours ago", embed.description)
                self.assertIn("**Date:** 01/01/2026", embed.description)
                self.assertIn("**ID:** 123", embed.description)
                self.assertEqual(embed.thumbnail.url, emoji.url)

    async def test_info_for_recent_emoji(self) -> None:
        """Keep the hour precision for emojis created less than an hour ago."""
        now = datetime(2026, 1, 3, 12, tzinfo=UTC)
        emoji = SimpleNamespace(
            name="python", id=123, created_at=now - timedelta(minutes=30),
            url="https://cdn.discordapp.com/emojis/123.png",
        )
        ctx = SimpleNamespace(send=AsyncMock())
        with patch("bot.utils.time.datetime") as clock:
            clock.now.return_value = now
            await Emojis.info_command.callback(Emojis(None), ctx, emoji)

        embed = ctx.send.call_args.kwargs["embed"]
        self.assertIn("**Created:** less than a hour ago", embed.description)
