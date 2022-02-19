import discord
import typing
import datetime
from discord.utils import find
from discord.ext import commands
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from string import digits


class Counting(commands.Cog):
    """
    Make a counting channel with goals.
    """

    __version__ = "1.4.0"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1564646215646, force_registration=True
        )

        self.config.register_guild(
            channel=0,
            previous=0,
            goal=0,
            last=0,
            warning=False,
            seconds=0
        )

    async def red_delete_data_for_user(self, *, requester, user_id):
        for guild in self.bot.guilds:
            if user_id == await self.config.guild(guild).last():
                await self.config.guild(guild).last.clear()

    def format_help_for_context(self, ctx: commands.Context) -> str:
        context = super().format_help_for_context(ctx)
        return f"{context}\n\nVersion: {self.__version__}"

    @checks.admin()
    @checks.bot_has_permissions(manage_channels=True, manage_messages=True)
    @commands.group(autohelp=True, aliases=["counting"])
    @commands.guild_only()
    async def countset(self, ctx: commands.Context):
        """Various Counting settings."""

    @countset.command(name="channel")
    async def countset_channel(
        self, ctx: commands.Context, channel: typing.Optional[discord.TextChannel]
    ):
        """Set the counting channel.

        If channel isn't provided, it will delete the current channel."""
        if not channel:
            await self.config.guild(ctx.guild).channel.set(0)
            return await ctx.send("Channel removed.")
        await self.config.guild(ctx.guild).channel.set(channel.id)
        await ctx.send(f"{channel.name} has been set for counting.")

    @countset.command(name="goal")
    async def countset_goal(self, ctx: commands.Context, goal: int = 0):
        """Set the counting goal.

        If goal isn't provided, it will be deleted."""
        if not goal:
            await self.config.guild(ctx.guild).goal.clear()
            return await ctx.send("Goal removed.")
        await self.config.guild(ctx.guild).goal.set(goal)
        await ctx.send(f"Goal set to {goal}.")

    @countset.command(name="start")
    async def countset_start(self, ctx: commands.Context, number: int):
        """Set the starting number."""
        channel = ctx.guild.get_channel(await self.config.guild(ctx.guild).channel())
        if not channel:
            return await ctx.send(
                f"Set the channel with `{ctx.clean_prefix}countset channel <channel>`, please."
            )
        await self.config.guild(ctx.guild).previous.set(number)
        await self.config.guild(ctx.guild).last.clear()
        goal = await self.config.guild(ctx.guild).goal()
        next_number = number + 1
        if await self.config.guild(ctx.guild).topic():
            await self._set_topic(number, goal, next_number, channel)
        await channel.send(number)
        await ctx.send(f"Counting start set to {number}.")

    @countset.command(name="reset")
    async def countset_reset(self, ctx: commands.Context, confirmation: bool = False):
        """Reset the counter and start from 0 again!"""
        if not confirmation:
            return await ctx.send(
                "This will reset the ongoing counting. This action **cannot** be undone.\n"
                f"If you're sure, type `{ctx.clean_prefix}countset reset yes`."
            )
        p = await self.config.guild(ctx.guild).previous()
        if p == 0:
            return await ctx.send("The counting hasn't even started.")
        c = ctx.guild.get_channel(await self.config.guild(ctx.guild).channel())
        if not c:
            return await ctx.send(
                f"Set the channel with `{ctx.clean_prefix}countchannel <channel>`, please."
            )
        await self.config.guild(ctx.guild).previous.clear()
        await self.config.guild(ctx.guild).last.clear()
        await c.send("Counting has been reset.")
        goal = await self.config.guild(ctx.guild).goal()
        if await self.config.guild(ctx.guild).topic():
            await self._set_topic(0, goal, 1, c)

    @countset.command(name="warnmsg")
    async def countset_warnmsg(
        self,
        ctx: commands.Context,
        on_off: typing.Optional[bool],
        seconds: typing.Optional[int],
    ):
        """Toggle a warning message.

        If `on_off` is not provided, the state will be flipped.
        Optionally add how many seconds the bot should wait before deleting the message (0 for not deleting)."""
        target_state = on_off or not (await self.config.guild(ctx.guild).warning())
        await self.config.guild(ctx.guild).warning.set(target_state)
        if target_state:
            if not seconds or seconds < 0:
                seconds = 0
                await ctx.send("Warning messages are now enabled.")
            else:
                await ctx.send(
                    f"Warning messages are now enabled, will be deleted after {seconds} seconds."
                )
            await self.config.guild(ctx.guild).seconds.set(seconds)
        else:
            await ctx.send("Warning messages are now disabled.")

    @countset.command(name="settings")
    async def countset_settings(self, ctx: commands.Context):
        """See current settings."""
        data = await self.config.guild(ctx.guild).all()
        channel = ctx.guild.get_channel(data["channel"])
        channel = channel.mention if channel else "None"

        goal = "None" if data["goal"] == 0 else str(data["goal"])

        warn = "Disabled" if data["warning"] else f"Enabled ({data['seconds']} s)"

        embed = discord.Embed(
            colour=await ctx.embed_colour(), timestamp=datetime.datetime.now()
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.title = "**__Counting settings:__**"
        embed.set_footer(text="*required to function properly")

        embed.add_field(name="Channel*:", value=channel)
        embed.add_field(name="Warning message:", value=warn)
        embed.add_field(name="Next number:", value=str(data["previous"] + 1))
        embed.add_field(name="Goal:", value=goal)

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.id == self.bot.user.id:
            return
        if message.channel.id != await self.config.guild(message.guild).channel():
            return
        last_id = await self.config.guild(message.guild).last()
        previous = await self.config.guild(message.guild).previous()
        next_number = previous + 1
        goal = await self.config.guild(message.guild).goal()
        warning = await self.config.guild(message.guild).warning()
        seconds = await self.config.guild(message.guild).seconds()
        if message.author.id != last_id:
            try:
                now = int(''.join(c for c in message.content if c in digits and message.content.isdigit()))
                if now - 1 == previous:
                    await self.config.guild(message.guild).previous.set(now)
                    await self.config.guild(message.guild).last.set(message.author.id)
                    n = now + 1
                    if await self.config.guild(message.guild).topic():
                        return await self._set_topic(now, goal, n, message.channel)
                    return
            except (TypeError, ValueError):
                pass
            if warning and message.author.id != last_id:
                await message.channel.send(f"The next message in this channel must be {next_number}", delete_after=seconds)
        else:
            await message.channel.send('You cannot count twice in a row.', delete_after=seconds)
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild:
            return
        if message.channel.id != await self.config.guild(message.guild).channel():
            return
        try:
            deleted = int(message.content)
            previous = await self.config.guild(message.guild).previous()
            goal = await self.config.guild(message.guild).goal()
            if deleted == previous:
                s = str(deleted)
                if goal == 0:
                    msgs = await message.channel.history(limit=100).flatten()
                else:
                    msgs = await message.channel.history(limit=goal).flatten()
                msg = find(lambda m: m.content == s, msgs)
                if not msg:
                    p = deleted - 1
                    await self.config.guild(message.guild).previous.set(p)
                    await message.channel.send(deleted)
        except (TypeError, ValueError):
            return
