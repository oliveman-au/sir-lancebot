import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot.exts.fun.xkcd import XKCD


class XKCDTests(unittest.IsolatedAsyncioTestCase):
    """Check startup handling without starting the refresh loop or using HTTP."""

    async def asyncSetUp(self) -> None:
        """Create the cog with its background task disabled."""
        self.bot = MagicMock()
        with patch("discord.ext.tasks.Loop.start"):
            self.cog = XKCD(self.bot)
        self.ctx = SimpleNamespace(send=AsyncMock())
        self.info = {
            "num": 42, "safe_title": "Test comic", "img": "https://imgs.xkcd.com/comics/test.png",
            "alt": "Test alt text", "year": "2026", "month": "1", "day": "1",
        }

    def mock_response(self, status: int) -> AsyncMock:
        """Configure a response from the HTTP session's async context manager."""
        response = AsyncMock()
        response.status = status
        response.json.return_value = self.info
        self.bot.http_session.get.return_value.__aenter__.return_value = response
        return response

    async def test_empty_cache(self) -> None:
        """Both random and latest requests receive a retry message at startup."""
        for comic in (None, "latest"):
            with self.subTest(comic=comic):
                self.ctx.send.reset_mock()
                await XKCD.fetch_xkcd_comics.callback(self.cog, self.ctx, comic)
                self.ctx.send.assert_awaited_once()
                embed = self.ctx.send.call_args.kwargs["embed"]
                self.assertIn("Please try again shortly", embed.description)
        self.bot.http_session.get.assert_not_called()

    async def test_numbered_comic_with_empty_cache(self) -> None:
        """Explicit numbers remain available before the latest comic is cached."""
        self.mock_response(200)
        await XKCD.fetch_xkcd_comics.callback(self.cog, self.ctx, "42")
        self.bot.http_session.get.assert_called_once_with("https://xkcd.com/42/info.0.json")
        self.assertIn("view", self.ctx.send.call_args.kwargs)

    async def test_failed_refresh_leaves_cache_unavailable(self) -> None:
        """An unsuccessful initial refresh still produces a useful command reply."""
        self.mock_response(503)
        await self.cog.get_latest_comic_info()
        await XKCD.fetch_xkcd_comics.callback(self.cog, self.ctx, "latest")
        self.assertIn("Please try again shortly", self.ctx.send.call_args.kwargs["embed"].description)

    async def test_successful_refresh_recovers(self) -> None:
        """Random and latest commands work once a later refresh fills the cache."""
        self.mock_response(200)
        await self.cog.get_latest_comic_info()
        for comic in (None, "latest"):
            with self.subTest(comic=comic), patch("bot.exts.fun.xkcd.randint", return_value=42):
                self.ctx.send.reset_mock()
                await XKCD.fetch_xkcd_comics.callback(self.cog, self.ctx, comic)
                self.ctx.send.assert_awaited_once()
                self.assertIn("view", self.ctx.send.call_args.kwargs)

    async def test_invalid_argument_with_empty_cache(self) -> None:
        """Argument errors keep their existing message during startup."""
        await XKCD.fetch_xkcd_comics.callback(self.cog, self.ctx, "invalid")
        self.assertIn("integer or 'latest'", self.ctx.send.call_args.kwargs["embed"].description)
        self.bot.http_session.get.assert_not_called()

    async def test_numbered_comic_http_error(self) -> None:
        """HTTP failures for numbered requests keep their existing error reply."""
        self.mock_response(404)
        await XKCD.fetch_xkcd_comics.callback(self.cog, self.ctx, "404")
        self.assertIn("404: Could not retrieve", self.ctx.send.call_args.kwargs["embed"].description)
