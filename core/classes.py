import discord
from discord.ext import commands
import aiosqlite


class Cog_Extension(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db: aiosqlite.Connection | None = None
        self.cache = {}

    async def cog_load(self):
        """Runs automatically when the Cog is loaded."""
        # 1. Open a persistent DB connection for this Cog
        self.db = await aiosqlite.connect("user.db")

        # 2. Set up tables
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                points INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                playing INTEGER DEFAULT 0,
                answer TEXT
            )
            """
        )
        await self.db.commit()

        # 3. Warm the cache
        async with self.db.execute("SELECT user_id, points, level FROM users") as cursor:
            rows = await cursor.fetchall()
            for user_id, points, level in rows:
                self.cache[user_id] = {
                    "points": points, "level": level}

    async def cog_unload(self):
        """Runs automatically when the Cog is unloaded or the bot shuts down."""
        if self.db:
            await self.db.close()
