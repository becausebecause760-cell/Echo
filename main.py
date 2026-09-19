import discord, time
from discord.ext import commands, tasks

active_shifts, last_activity = {}, {}
WEBHOOK_URL = "https://discord.com/api/webhooks/1550917481256853615/fz35gUfvOu2T9Ln4tlW0C0hTPGnIFnJeTNhBZpOI4yUK6nHP0b_GJk2QyO9rf4t51Cn6"

def is_staff(i: discord.Interaction) -> bool:
    if i.user.id == i.guild.owner_id or i.user.guild_permissions.administrator or i.user.guild_permissions.manage_guild: return True
    if i.user.guild_permissions.kick_members or i.user.guild_permissions.ban_members or i.user.guild_permissions.manage_messages: return True
    return any(k in r.name.lower() for r in i.user.roles for k in ["admin", "moderator", "mod", "manager", "helper"])

async def get_logs(guild):
    ch = discord.utils.get(guild.text_channels, name="sterix-private-logs")
    if not ch:
        ov = {guild.default_role: discord.PermissionOverwrite(read_messages=False), guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        for r in guild.roles:
            if r.permissions.administrator: ov[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        ch = await guild.create_text_channel("sterix-private-logs", overwrites=ov)
    return ch

class WaitModal(discord.ui.Modal, title="✨ Sterix Break & Vacation"):
    reason = discord.ui.TextInput(label="Why do you need a break?", style=discord.TextStyle.paragraph, required=True, max_length=300)
    vacation = discord.ui.TextInput(label="Vacation dates / info", style=discord.TextStyle.short, required=True, max_length=100)

    async def on_submit(self, i: discord.Interaction):
        ch = discord.utils.get(i.guild.text_channels, name="sterix-wait-logs")
        if not ch:
            ov = {i.guild.default_role: discord.PermissionOverwrite(read_messages=False), i.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
            for r in i.guild.roles:
                if r.permissions.administrator: ov[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            ch = await i.guild.create_text_channel("sterix-wait-logs", overwrites=ov)
        emb = discord.Embed(title="🏖️ New Break Request", description=f"👤 **Staff:** {i.user.mention}\n📝 **Reason:** {self.reason.value}\n🌴 **Vacation:** {self.vacation.value}", color=0xffa500)
        emb.set_thumbnail(url=i.user.display_avatar.url)
        emb.set_footer(text=f"ID: {i.user.id} • Sterix Core™")
        await ch.send(embed=emb, view=WaitApprovalView(i.user.id))
        await i.response.send_message("🏖️ | Request dispatched to administration!", ephemeral=True)

class WaitResponseModal(discord.ui.Modal):
    def __init__(self, action: str, emb: discord.Embed, uid: int):
        super().__init__(title=f"👑 Admin {action} Panel")
        self.action, self.emb, self.uid = action, emb, uid
        self.note = discord.ui.TextInput(label="Edit response note:", style=discord.TextStyle.paragraph, default="Good luck!" if action == "Accept" else "Denied.", required=True, max_length=300)
        self.add_item(self.note)

    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        member, col, emoji = i.guild.get_member(self.uid), (0x00ff00 if self.action == "Accept" else 0xff0000), ("✅" if self.action == "Accept" else "❌")
        upd = discord.Embed(title=f"{emoji} Break Request — {self.action}ed", description=self.emb.description + f"\n\n💬 **Admin ({i.user.display_name}):** {self.note.value}", color=col)
        if self.emb.thumbnail: upd.set_thumbnail(url=self.emb.thumbnail.url)
        upd.set_footer(text=f"Processed by {i.user}")
        await i.message.edit(embed=upd, view=None)
        await i.followup.send(f"Successfully {self.action.lower()}ed request!", ephemeral=True)
        if member:
            try: await member.send(embed=discord.Embed(title=f"{emoji} Break Update", description=f"Your request was **{self.action.lower()}ed**.\n💬 {self.note.value}", color=col))
            except: pass

class WaitApprovalView(discord.ui.View):
    def __init__(self, uid: int):
        super().__init__(timeout=None)
        self.uid = uid
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅", custom_id="w_acc")
    async def accept(self, i: discord.Interaction, b: discord.ui.Button):
        if not is_staff(i): return await i.response.send_message("❌ Staff only.", ephemeral=True)
        await i.response.send_modal(WaitResponseModal("Accept", i.message.embeds[0], self.uid))
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, emoji="❌", custom_id="w_den")
    async def deny(self, i: discord.Interaction, b: discord.ui.Button):
        if not is_staff(i): return await i.response.send_message("❌ Staff only.", ephemeral=True)
        await i.response.send_modal(WaitResponseModal("Deny", i.message.embeds[0], self.uid))

class StaffInactivityModal(discord.ui.Modal):
    def __init__(self, emb: discord.Embed, uid: int):
        super().__init__(title="⚙️ Manage Inactive Staff")
        self.emb, self.uid = emb, uid
        self.note = discord.ui.TextInput(label="Edit warning message:", style=discord.TextStyle.paragraph, default="Hello! You are clocked in but inactive. Are you still here?", required=True, max_length=300)
        self.add_item(self.note)
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        member = i.guild.get_member(self.uid)
        if member:
            try: await member.send(embed=discord.Embed(title="⚠️ Staff Warning", description=self.note.value, color=0xffa500))
            except: pass
        upd = discord.Embed(title="⚠️ Inactive Staff — Warning Sent", description=self.emb.description + f"\n\n💬 **Admin Action:** {self.note.value}", color=0xffa500)
        if self.emb.thumbnail: upd.set_thumbnail(url=self.emb.thumbnail.url)
        await i.message.edit(embed=upd, view=None)
        await i.followup.send("Warning sent!", ephemeral=True)

class StaffInactivityView(discord.ui.View):
    def __init__(self, uid: int):
        super().__init__(timeout=None)
        self.uid = uid
    @discord.ui.button(label="Send Warning", style=discord.ButtonStyle.blurple, emoji="⚠️", custom_id="s_warn")
    async def warn(self, i: discord.Interaction, b: discord.ui.Button):
        if not is_staff(i): return await i.response.send_message("❌ Staff only.", ephemeral=True)
        await i.response.send_modal(StaffInactivityModal(i.message.embeds[0], self.uid))
    @discord.ui.button(label="Force Clock-Off", style=discord.ButtonStyle.red, emoji="🔨", custom_id="s_kick")
    async def kick(self, i: discord.Interaction, b: discord.ui.Button):
        if not is_staff(i): return await i.response.send_message("❌ Staff only.", ephemeral=True)
        await i.response.defer(ephemeral=True)
        active_shifts.pop(self.uid, None)
        last_activity.pop(self.uid, None)
        member = i.guild.get_member(self.uid)
        if member:
            try: await member.send(embed=discord.Embed(title="🔴 Shift Force-Ended", description="Your shift was ended by admin due to inactivity.", color=0xff0000))
            except: pass
        upd = discord.Embed(title="🔨 Inactive Staff — Force Ended", description=i.message.embeds[0].description + "\n\n🛑 Forcefully clocked off.", color=0xff0000)
        if i.message.embeds[0].thumbnail: upd.set_thumbnail(url=i.message.embeds[0].thumbnail.url)
        await i.message.edit(embed=upd, view=None)
        await i.followup.send("Shift force-ended!", ephemeral=True)

class SterixSelect(discord.ui.Select):
    def __init__(self):
        opts = [
            discord.SelectOption(label="Home • Sterix Core™", description="Welcome overview & mission control", emoji="🏠"),
            discord.SelectOption(label="Staff Shield • Clock-In", description="Track active staff shifts securely", emoji="🛡️"),
            discord.SelectOption(label="Manage Your Staff", description="Use /staffboard to see active shifts", emoji="⚙️"),
            discord.SelectOption(label="Break & Vacation • /wait", description="Request time off & approvals", emoji="🏖️"),
            discord.SelectOption(label="Support & Ownership", description="Creator & community support", emoji="👑"),
        ]
        super().__init__(placeholder="📂 Select a category...", options=opts)

    async def callback(self, i: discord.Interaction):
        c = self.values[0]
        if "Home" in c:
            emb = discord.Embed(title="🎉 Meet Sterix Core™!", description="Hello! Are you trying to keep your Discord server under control?\nSometimes your staff members don't want to be online when you need them to be.\n\nI'm here to help you manage and guide your community. Just use `/help` or `/support` to get started and follow the guide!", color=0x5865F2)
        elif "Staff Shield" in c:
            emb = discord.Embed(title="🛡️ Staff Clock-In System", description="You need help managing your staff?\nIt's better to keep them online and see how many staff are active.\n\nUse `/clockin` and `/clockoff` to track your shifts securely with role verification.\nAdministrators can use `/stafflogs` to check who is currently clocked in and active.\n\nGood luck and have fun using it!", color=0x3498DB)
        elif "Manage Your Staff" in c:
            emb = discord.Embed(title="⚙️ Manage Your Staff", description="Only moderators are able to access and use `/staffboard` to see who is actually clocking in every time and who deserves a promotion.", color=0x1ABC9C)
        elif "Break" in c:
            emb = discord.Embed(title="🏖️ Staff Break & Vacation System", description="Need a break or going on vacation?\nUse the `/wait` command!\n\n• Type `/wait` to open the request menu.\n• Provide your reason and vacation details.\n• It gets sent directly to a dedicated private log channel (`#sterix-wait-logs`).\n• Admins can accept or deny your request and customize the response notes.", color=0xE67E22)
        else:
            emb = discord.Embed(title="👑 Bot Owner & Support", description="To view official owner and support details privately, please use the `/support` command!\n\nType `/support` to see the full information.", color=0xF1C40F)
        emb.set_thumbnail(url=i.client.user.display_avatar.url)
        emb.set_footer(text="Sterix Core™ • Interactive Guide")
        await i.response.edit_message(embed=emb, view=SterixHelpView())

class SterixHelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(SterixSelect())
        self.add_item(discord.ui.Button(label="Dashboard", url="https://bot-hosting.net", style=discord.ButtonStyle.link, row=1, emoji="📊"))
        self.add_item(discord.ui.Button(label="Invite Bot", url="https://discord.com/oauth2/authorize?client_id=1550263984018563194&permissions=8&integration_type=0&scope=bot", style=discord.ButtonStyle.link, row=1, emoji="🤖"))
        self.add_item(discord.ui.Button(label="Support Server", url="https://discord.gg/64RDmyKj6d", style=discord.ButtonStyle.link, row=1, emoji="🔗"))

class FeatureInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Support Server", url="https://discord.gg/64RDmyKj6d", style=discord.ButtonStyle.link, emoji="🔗"))

class SterixBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self): await self.tree.sync()
    async def on_ready(self):
        print(f"Logged in as {self.user}!")
        if not self.status_loop.is_running(): self.status_loop.start()
        if not self.inactivity_checker.is_running(): self.inactivity_checker.start()

    @tasks.loop(minutes=15)
    async def status_loop(self):
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"Protecting {len(self.guilds)} servers"))

    @tasks.loop(minutes=5)
    async def inactivity_checker(self):
        now = time.time()
        for uid in list(active_shifts.keys()):
            if (now - last_activity.get(uid, active_shifts[uid])) > 600:
                for guild in self.guilds:
                    member = guild.get_member(uid)
                    if member:
                        ch = await get_logs(guild)
                        emb = discord.Embed(title="⚠️ Staff Inactivity Alert", description=f"👤 **Staff:** {member.mention}\nClocked in for over 10 minutes without speaking.", color=0xffa500)
                        emb.set_thumbnail(url=member.display_avatar.url)
                        try: await ch.send(embed=emb, view=StaffInactivityView(uid))
                        except: pass
                last_activity[uid] = now

    async def on_guild_join(self, guild):
        count = len(self.guilds)
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"Protecting {count} servers"))
        try:
            async with discord.Webhook.from_url(WEBHOOK_URL, client=self) as webhook:
                emb = discord.Embed(title="📥 New Server Joined!", description=f"Sterix Core™ has been added to a new server!\n\n🏢 **Server Name:** {guild.name}\n🆔 **Server ID:** {guild.id}\n👑 **Owner:** {guild.owner}\n👥 **Member Count:** {guild.member_count}\n📊 **Total Servers:** {count}", color=0x00FF00)
                if guild.icon: emb.set_thumbnail(url=guild.icon.url)
                emb.set_footer(text="Sterix Core™ • Guild Tracker")
                await webhook.send(embed=emb)
        except Exception as e: print(f"Webhook error: {e}")

    async def on_guild_remove(self, guild):
        count = len(self.guilds)
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"Protecting {count} servers"))
        try:
            async with discord.Webhook.from_url(WEBHOOK_URL, client=self) as webhook:
                emb = discord.Embed(title="📤 Server Removed", description=f"Sterix Core™ was removed from a server.\n\n🏢 **Server Name:** {guild.name}\n🆔 **Server ID:** {guild.id}\n📊 **Total Servers:** {count}", color=0xFF0000)
                if guild.icon: emb.set_thumbnail(url=guild.icon.url)
                emb.set_footer(text="Sterix Core™ • Guild Tracker")
                await webhook.send(embed=emb)
        except Exception as e: print(f"Webhook error: {e}")

bot = SterixBot()

@bot.event
async def on_message(msg):
    if not msg.author.bot and msg.author.id in active_shifts: last_activity[msg.author.id] = time.time()
    await bot.process_commands(msg)

@bot.tree.command(name="help", description="Open command menu.")
async def help_cmd(i: discord.Interaction):
    emb = discord.Embed(title="🎉 Meet Sterix Core™!", description="Hello! Are you trying to keep your Discord server under control?\nSometimes your staff members don't want to be online when you need them to be.\n\nI'm here to help you manage and guide your community. Just use `/help` or `/support` to get started and follow the guide!", color=0x5865F2)
    if bot.user.display_avatar: emb.set_thumbnail(url=bot.user.display_avatar.url)
    emb.set_footer(text="Sterix Core™ • Main Menu")
    await i.response.send_message(embed=emb, view=SterixHelpView(), ephemeral=False)

@bot.tree.command(name="support", description="View owner info.")
async def support_cmd(i: discord.Interaction):
    emb = discord.Embed(title="👑 Bot Owner & Support", description="• **Developer:** Sterix Developer\n• **Support:** [Join Here](https://discord.gg/64RDmyKj6d)", color=0xF1C40F)
    if bot.user.display_avatar: emb.set_thumbnail(url=bot.user.display_avatar.url)
    emb.set_footer(text="Sterix Core™ • Support Panel")
    await i.response.send_message(embed=emb, view=FeatureInfoView(), ephemeral=True)

@bot.tree.command(name="clockin", description="Clock in for shift.")
async def clockin(i: discord.Interaction):
    if not is_staff(i): return await i.response.send_message(embed=discord.Embed(title="❌ | Access Denied", color=0xff0000), ephemeral=True)
    active_shifts[i.user.id], last_activity[i.user.id] = int(time.time()), time.time()
    ch = await get_logs(i.guild)
    emb = discord.Embed(title="🟢 | Staff Clock In", description=f"🟢 {i.user.mention} clocked in at <t:{active_shifts[i.user.id]}:t>", color=0x00ff00)
    emb.set_thumbnail(url=i.user.display_avatar.url)
    emb.set_footer(text="Sterix Core™ • Clock-In System")
    await ch.send(embed=emb)
    await i.response.send_message(embed=emb, ephemeral=True)

@bot.tree.command(name="clockoff", description="Clock off from shift.")
async def clockoff(i: discord.Interaction):
    if not is_staff(i): return await i.response.send_message(embed=discord.Embed(title="❌ | Access Denied", color=0xff0000), ephemeral=True)
    start = active_shifts.pop(i.user.id, None)
    last_activity.pop(i.user.id, None)
    ch = await get_logs(i.guild)
    emb = discord.Embed(title="🔴 | Staff Clock Off", description=f"🔴 {i.user.mention} clocked off. Started <t:{start}:R>", color=0xff0000)
    emb.set_thumbnail(url=i.user.display_avatar.url)
    emb.set_footer(text="Sterix Core™ • Clock-Off System")
    await ch.send(embed=emb)
    await i.response.send_message(embed=emb, ephemeral=True)

@bot.tree.command(name="staffboard", description="View clocked-in staff leaderboard.")
async def staffboard(i: discord.Interaction):
    if not is_staff(i): return await i.response.send_message(embed=discord.Embed(title="❌ | Access Denied", description="Only moderators/staff are able to use this command.", color=0xff0000), ephemeral=True)
    emb = discord.Embed(title="📊 Staff Clock-In Leaderboard", color=0x1ABC9C)
    emb.set_thumbnail(url=i.client.user.display_avatar.url)
    emb.description = "No staff members currently clocked in." if not active_shifts else "".join([f"• **{i.guild.get_member(uid).display_name if i.guild.get_member(uid) else uid}** — Clocked in <t:{ts}:R>\n" for uid, ts in active_shifts.items()])
    emb.set_footer(text="Sterix Core™ • Leaderboard")
    await i.response.send_message(embed=emb, ephemeral=False)

@bot.tree.command(name="wait", description="Request break or vacation.")
async def wait_cmd(i: discord.Interaction):
    if not is_staff(i): return await i.response.send_message(embed=discord.Embed(title="❌ | Access Denied", color=0xff0000), ephemeral=True)
    await i.response.send_modal(WaitModal())

@bot.tree.command(name="stafflogs", description="View active shifts.")
async def stafflogs(i: discord.Interaction):
    if not is_staff(i): return await i.response.send_message(embed=discord.Embed(title="❌ | Access Denied", color=0xff0000), ephemeral=True)
    ch = await get_logs(i.guild)
    emb = discord.Embed(title="📋 Active Staff Shifts", description=f"No one active.\n📁 {ch.mention}" if not active_shifts else "\n".join([f"• <@!{uid}> — Active (<t:{ts}:R>)" for uid, ts in active_shifts.items()]), color=0x00ff00)
    emb.set_footer(text="Sterix Core™ • Logs")
    await i.response.send_message(embed=emb, ephemeral=True)

@bot.tree.command(name="24-7", description="Check 24/7 online status.")
async def status_247(i: discord.Interaction):
    emb = discord.Embed(title="📁 Sterix Core™ Status", description="🟢 **System Online:** Sterix Core™ is fully operational and running smoothly around the clock!", color=0x2ECC71)
    emb.add_field(name="🌟 Active Features:", value="`+` 🛡️ Secure Staff Clock-In & Auto-Inactivity Tracking\n`+` 🏖️ Vacation & Break Management System (`/wait`)\n`+` ⚡ 24/7 Server Moderation Support", inline=False)
    emb.add_field(name="Quick Tip:", value="Use `/help` to see the complete interactive dashboard and explore all commands.", inline=False)
    if i.client.user.display_avatar: emb.set_thumbnail(url=i.client.user.display_avatar.url)
    emb.set_footer(text="Sterix Core™ • Always Online")
    await i.response.send_message(embed=emb, view=FeatureInfoView(), ephemeral=False)

bot.run("
