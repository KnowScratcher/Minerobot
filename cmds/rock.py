from discord import File, ButtonStyle, Interaction, Embed, SelectOption
from discord.abc import Messageable
from discord.ui import Button, View, Modal, TextInput, Select
from discord.ext import commands
from core.classes import Cog_Extension
import helper.select as select
import json
from math import log

image_index: dict[int, int] = {}  # The index of the image currently shown
image_list: dict[int, list] = {}  # The shuffled list of images
image_answer: dict[int, str] = {}  # The answer to everyone's image
user_guesses: dict[int, list] = {}  # The users' guess
user_hints: dict[int, set] = {}  # The users' used hint

item_data = {}  # The preloaded data of all items
hints = {
    "lithology": ("岩性", "🪨"),
    "felsmaf": ("酸基性", "🧪"),
    "grain": ("顆粒大小", "✨"),
    "foliation": ("葉理", "📎")
}  # the label and value pair of hint menu

# Load the data into variable
with open("data.json", "r", encoding="UTF-8") as j:
    item_data = json.load(j)


class AnswerSubmit(Modal, title="答案提交"):
    """The form for user to submit answer

    Args:
        cog (Rock): The object Rock currently using
    """

    # Single-line text input
    answer_input = TextInput(
        label="你的答案",
        placeholder="請在此輸入你的答案...",
        required=True,
        max_length=50,
    )

    def __init__(self, cog: "Rock"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: Interaction):
        # Get user id
        uid = interaction.user.id
        # Retrieve values entered by the user
        user_answer = self.answer_input.value.lower()
        real_answer = image_answer[uid]
        # Record user guess
        user_guesses[uid].append(user_answer)
        # If user guess wrong
        if real_answer != user_answer and user_answer not in item_data[real_answer]["alias"]:
            await interaction.response.send_message(f"❌ {user_answer}", ephemeral=True)
        else:  # If user guess right
            # mark all previous guess as wrong, and the last one right
            report_text = [f"❌ {x}" for x in user_guesses[uid]
                           [:-1]] + [f"✅ {user_guesses[uid][-1]}"]
            # Calculate try count and points
            try_count = len(user_guesses[uid])
            image_count = image_index[uid] + 1
            hint_count = len(user_hints[uid])
            # Get 1 point after 5 tries
            score = max(0, int(item_data[real_answer]["points"]
                        ** (1.25 - try_count / 4)) - image_count // 3 - hint_count // 2)
            # Add points to the user's database
            level_change = await self.cog._add_points(uid, score)
            # Reset buttons
            view = View(timeout=0)
            await interaction.response.edit_message(view=view)
            # Generate guess report
            embed = Embed(title="恭喜答對", description="\n".join(
                report_text), color=0x00ff00)
            embed.add_field(name="猜測次數", value=try_count)
            embed.add_field(name="使用圖片數", value=image_count)
            embed.add_field(name="使用提示數", value=hint_count)
            embed.add_field(name="分數", value=score)
            # Send report and reference url
            await interaction.followup.send(embed=embed)
            await interaction.followup.send(item_data[real_answer]["url"])
            # Send level change message
            if level_change != 0:
                await interaction.followup.send(embed=await self.cog._build_level_change_embed(level_change, self.cog.cache[uid]["level"]))
            # Remove user data from play field
            del image_index[uid]
            del image_list[uid]
            del image_answer[uid]
            del user_guesses[uid]


class Rock(Cog_Extension):
    async def _build_level_change_embed(self, diff: int, new_level: int) -> Embed:
        if diff > 0:
            embed = Embed(title=f"⬆️ 恭喜您升級到 LV.{new_level}了", color=0x00ffff)
        elif diff < 0:
            embed = Embed(title=f"⬇️ 抱歉您降級到 LV.{new_level}了", color=0xff7700)
        else:
            return Embed()
        return embed

    async def _calculate_level(self, points: int):
        return max(int(log(points/20) / log(5) + 2), 1)

    async def _add_points(self, uid: int, points: int):
        new_level = await self._calculate_level(self.cache[uid]["points"] + points)
        difference = new_level - self.cache[uid]["level"]
        if difference != 0:
            self.cache[uid]["level"] = new_level
        # Update cache
        self.cache[uid]["points"] += points
        assert self.db  # Prevent database missing
        await self.db.execute(  # Write to database
            """
            INSERT INTO users (user_id, points, level)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            points = excluded.points,
            level = excluded.level
            """,
            (uid, self.cache[uid]["points"], self.cache[uid]["level"]),
        )
        await self.db.commit()
        return difference

    async def _handle_first_join(self, uid: int):
        if uid in self.cache:  # If user is already cached (played before)
            return
        # New user
        user_data = {"points": 0, "level": 1}
        self.cache[uid] = user_data  # Create the user's data in cache
        assert self.db
        await self.db.execute(  # Write to database
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

    async def _build_hint_selection_menu(self, uid: int):
        answer = image_answer[uid]
        options = [SelectOption(label=label[0], value=value, emoji=label[1])
                   for value, label in hints.items() if value not in user_hints[uid]]
        if len(options) == 0:
            return False
        menu = Select(placeholder="請選一項提示",
                      min_values=1,
                      max_values=1,
                      options=options)

        async def menu_callback(interaction: Interaction):
            user_answer = menu.values[0]
            real_answer = image_answer[uid]
            user_hints[uid].add(user_answer)
            await interaction.response.edit_message(content=f"這個東西的{hints[user_answer][0]}是: {item_data[real_answer]['hints'][user_answer] if user_answer in item_data[real_answer]['hints'] else '不適用'}", view=View())

        menu.callback = menu_callback
        return menu

    async def _picture_flow(self, channel: Messageable, uid: int, item_type: str | None = None):
        # Send waiting message to user
        wait_msg = await channel.send("請稍等，正在尋找圖片...")
        if uid not in image_index:  # If the user was not playing
            # Pick a image depending on the user's level and preference
            select_result = select.select_image(
                self.cache[uid]["level"], item_type)
            # Setup play field
            image_index[uid] = 0
            image_list[uid], image_answer[uid] = select_result["imgs"], select_result["answer"]
            user_guesses[uid] = []
            user_hints[uid] = set()
        else:  # If user is playing (recursive-ing)
            # Get the next image
            image_index[uid] = min(image_index[uid] + 1,
                                   len(image_list[uid]) - 1)  # Prevent index overflow

        # Setup buttons
        button_more = Button(label="再來一張", style=ButtonStyle.blurple)
        button_guess = Button(label="提交猜想", style=ButtonStyle.green)
        button_hint = Button(label="提示", style=ButtonStyle.gray)
        button_skip = Button(label="跳過", style=ButtonStyle.red)

        async def more_callback(interaction: Interaction):
            if interaction.user.id != uid:
                return
            view = View(timeout=0)
            # Delete buttons
            await interaction.response.edit_message(view=view)
            # Recursive (gets next image)
            await self._picture_flow(channel, uid, item_type)

        async def guess_callback(interaction: Interaction):
            if interaction.user.id != uid:
                return
            # Send answer submit form
            await interaction.response.send_modal(AnswerSubmit(cog=self))

        async def hint_callback(interaction: Interaction):
            if interaction.user.id != uid:
                return
            view = View(timeout=0)
            menu = await self._build_hint_selection_menu(uid)
            if not menu:
                await interaction.response.send_message("很抱歉，你已經用完提示了", ephemeral=True)
                return
            view.add_item(menu)
            await interaction.response.send_message(view=view, ephemeral=True)

        async def skip_callback(interaction: Interaction):
            if interaction.user.id != uid:
                return
            # Mark all guesses wrong and add the correct answer
            report_text = [f"❌ {x}" for x in user_guesses[uid]
                           ] + [f"➡️ {image_answer[uid]}"]
            # Calculate score
            count = len(user_guesses[uid])
            score = -(self.cache[uid]["level"] - 1)*5
            level_change = await self._add_points(uid, score)
            # Reset buttons
            view = View(timeout=0)
            await interaction.response.edit_message(view=view)
            # Generate report
            embed = Embed(title="失敗", description="\n".join(
                report_text), color=0xff0000)
            embed.add_field(name="猜測次數", value=count)
            embed.add_field(name="分數", value=score)
            await interaction.followup.send(embed=embed)
            await interaction.followup.send(item_data[image_answer[uid]]["url"])
            if level_change != 0:
                await interaction.followup.send(embed=await self._build_level_change_embed(level_change, self.cache[uid]["level"]))
            # Remove user data from play field
            del image_index[uid]
            del image_list[uid]
            del image_answer[uid]
            del user_guesses[uid]

        # Setup buttons
        button_more.callback = more_callback
        button_guess.callback = guess_callback
        button_hint.callback = hint_callback
        button_skip.callback = skip_callback

        view = View(timeout=0)
        view.add_item(button_more)
        view.add_item(button_guess)
        view.add_item(button_hint)
        view.add_item(button_skip)
        index = image_index[uid]
        file = File(image_list[uid][index])
        if index < len(image_list[uid]) - 1:  # If is not the last image
            await channel.send(content=f"<@{uid}> 圖片準備好了，請猜出這是什麼", file=file, view=view)
        else:  # If is last image
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
        await self._picture_flow(ctx.channel, ctx.message.author.id, item_type)


async def setup(bot):
    await bot.add_cog(Rock(bot))
