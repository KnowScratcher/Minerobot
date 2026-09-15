import sys
import traceback

import discord
from discord import *  # type: ignore
from discord.ext import commands
from discord.ui import *  # type: ignore
import json
import os
import time
import asyncio
import re

with open('config.json', 'r', encoding="UTF-8") as f:
    config = json.load(f)
with open("ops.txt", "r", encoding="UTF-8") as op:
    admin = re.split(",", op.read())

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='c.', intents=intents)
bot.remove_command("help")

no_permission_embed = discord.Embed(
    title="等等..你是管理員嗎 這個是管理員才能用的喔\n請放心，我不會讓管理員知道的!", color=0xff0000)


@bot.event
async def on_ready():
    print("bot is ready")


@bot.command()
async def load(ctx, extension):
    if str(ctx.message.author.id) in admin:
        await bot.load_extension(f'cmds.{extension}')
        await ctx.send(f'loaded {extension} done.')
    else:
        await ctx.message.delete()
        noperm = await ctx.send(embed=no_permission_embed)
        await asyncio.sleep(3)
        await noperm.delete()


@bot.command()
async def unload(ctx, extension):
    if str(ctx.message.author.id) in admin:
        await bot.unload_extension(f'cmds.{extension}')
        await ctx.send(f'unloaded {extension} done.')
    else:
        await ctx.message.delete()
        noperm = await ctx.send(embed=no_permission_embed)
        await asyncio.sleep(3)
        await noperm.delete()


@bot.command()
async def reload(ctx, extension):
    if str(ctx.message.author.id) in admin:
        await bot.reload_extension(f'cmds.{extension}')
        await ctx.send(f'reloaded {extension} done.')
    else:
        await ctx.message.delete()
        noperm = await ctx.send(embed=no_permission_embed)
        await asyncio.sleep(3)
        await noperm.delete()


@bot.command()  # 防止打錯指令用
async def relaod(ctx, extension): 
    if str(ctx.message.author.id) in admin:
        await bot.reload_extension(f'cmds.{extension}')
        await ctx.send(f'reloaded {extension} done.')
    else:
        await ctx.message.delete()
        noperm = await ctx.send(embed=no_permission_embed)
        await asyncio.sleep(3)
        await noperm.delete()


async def load_extensions():
    for Filename in os.listdir('./cmds'):
        if Filename.endswith('.py'):
            print(f"loading {Filename}")
            await bot.load_extension(f'cmds.{Filename[:-3]}')
            print("done")
    print("setting up...")


async def main():
    async with bot:
        await load_extensions()
        await bot.start(config['TOKEN'])

@bot.event
async def on_command_error(ctx, error):
    # Unwrap CommandInvokeError to get the actual underlying exception
    error = getattr(error, "original", error)

    # Print the error traceback to standard error output
    print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
    traceback.print_exception(
        type(error), error, error.__traceback__, file=sys.stderr
    )

if __name__ == "__main__":
    os.system("title " + "MUD bot")
    asyncio.run(main())
