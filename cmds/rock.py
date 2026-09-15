from discord import File, ButtonStyle, Interaction, Embed
from discord.abc import Messageable
from discord.ui import Button, View, Modal, TextInput
from discord.ext import commands
from core.classes import Cog_Extension
import helper.select as select
import json

image_index = {}
image_list = {}
image_answer = {}
user_guesses = {}

item_data = {}

with open("data.json") as j:
    item_data = json.load(j)


class AnswerSubmit(Modal, title="答案提交"):
    def __init__(self, cog: "Rock"):
        super().__init__()
        self.cog = cog
    # Single-line text input
    answer_input = TextInput(
        label="你的答案",
        placeholder="請在此輸入你的答案...",
        required=True,
        max_length=50,
    )

    async def on_submit(self, interaction: Interaction):
        # Retrieve values entered by the user
        answer = self.answer_input.value
        uid = interaction.user.id
        user_guesses[uid].append(answer)
        if image_answer[uid] != answer:
            await interaction.response.send_message(f"❌ {answer}", ephemeral=True)
        else:
            report_text = [f"❌ {x}" for x in user_guesses[uid]
                           [:-1]] + [f"✅ {user_guesses[uid][-1]}"]
            count = len(user_guesses[uid])
            score = int(10**(1.25 - count / 4))
            await self.cog._add_points(uid, score)
            view = View(timeout=0)
            await interaction.response.edit_message(view=view)
            embed = Embed(title="解題報告", description="\n".join(report_text), color=0x00ff00)
            embed.add_field(name="猜測次數", value=count)
            embed.add_field(name="分數", value=score)
            print(1)
            await interaction.followup.send(embed=embed)
            await interaction.followup.send(item_data[answer])
            del image_index[uid]
            del image_list[uid]
            del image_answer[uid]
            del user_guesses[uid]

class Rock(Cog_Extension):
    async def _add_points(self, uid: int, points: int):
        self.cache[uid]["points"] += points
        assert self.db
        await self.db.execute(
            """
            INSERT INTO users (user_id, points)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            points = excluded.points
            """,
            (uid, self.cache[uid]["points"]),
        )
        await self.db.commit()

    async def _handle_first_join(self, uid: int):
        if uid in self.cache:
            return
        user_data = {"points": 0, "level": 1}
        self.cache[uid] = user_data
        assert self.db
        await self.db.execute(
            """
            INSERT INTO users (user_id, points, level)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            points = excluded.points,
            level = excluded.level
            """,
            (uid, user_data["points"], user_data["level"]),
        )
        await self.db.commit()

    async def _picture_flow(self, channel: Messageable, uid: int, item_type: str | None = None):
        wait_msg = await channel.send("請稍等，正在尋找圖片...")
        if uid not in image_index:
            select_result = select.select_image(
                self.cache[uid]["level"], item_type)
            image_index[uid] = 0
            image_list[uid], image_answer[uid] = select_result["imgs"], select_result["answer"]
            user_guesses[uid] = []
        else:
            image_index[uid] = min(image_index[uid] + 1, len(image_list[uid]) - 1)

        button_more = Button(label="再來一張", style=ButtonStyle.blurple)
        button_guess = Button(label="提交猜想", style=ButtonStyle.green)
        button_hint = Button(label="提示", style=ButtonStyle.gray)
        button_skip = Button(label="跳過", style=ButtonStyle.red)

        async def more_callback(interaction: Interaction):
            if interaction.user.id == uid:
                view = View(timeout=0)
                await interaction.response.edit_message(view=view)
                await self._picture_flow(channel, uid, item_type)

        async def guess_callback(interaction: Interaction):
            if interaction.user.id == uid:
                await interaction.response.send_modal(AnswerSubmit(cog=self))

        button_more.callback = more_callback
        button_guess.callback = guess_callback

        view = View(timeout=0)
        view.add_item(button_more)
        view.add_item(button_guess)
        view.add_item(button_hint)
        view.add_item(button_skip)
        index = image_index[uid]
        file = File(image_list[uid][index])
        if index < len(image_list[uid]) - 1:
            await channel.send(content=f"<@{uid}> 圖片準備好了，請猜出這是什麼", file=file, view=view)
        else:
            view = View(timeout=0)
            button_more.disabled = True
            view.add_item(button_more)
            view.add_item(button_guess)
            view.add_item(button_hint)
            view.add_item(button_skip)
            await channel.send(content=f"<@{uid}> 接下來沒有圖片了，請猜出這是什麼", file=file, view=view)
        await wait_msg.delete()

    @commands.command()
    async def p(self, ctx, item_type=None):
        await self._handle_first_join(ctx.message.author.id)
        await self._picture_flow(ctx.channel, ctx.message.author.id)


async def setup(bot):
    await bot.add_cog(Rock(bot))
