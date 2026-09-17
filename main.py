import asyncio
import os
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

# Suppress noisy yt-dlp output
yt_dlp.utils.bug_reports_message = lambda: ""

ytdl_format_options = {
    "format": "bestaudio/best",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

ffmpeg_options = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
    ),
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):

  def __init__(self, source, *, data, volume=0.5):
    super().__init__(source, volume)
    self.data = data
    self.title = data.get("title")
    self.url = data.get("url")

  @classmethod
  async def from_url(cls, url, *, loop=None, stream=False):
    loop = loop or asyncio.get_running_loop()
    data = await loop.run_in_executor(
        None, lambda: ytdl.extract_info(url, download=not stream)
    )

    if "entries" in data:
      data = data["entries"][0]

    filename = data["url"] if stream else ytdl.prepare_filename(data)
    return cls(
        discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data
    )


class MusicBot(commands.Bot):

  def __init__(self):
    intents = discord.Intents.default()
    intents.message_content = True
    super().__init__(command_prefix="!", intents=intents)
    self.queues = {}  # guild_id: [YTDLSource, ...]

  async def setup_hook(self):
    @self.tree.command(name="play", description="Play a song or add it to queue.")
    @app_commands.describe(query="Song name or YouTube/audio URL")
    async def play(interaction: discord.Interaction, query: str):
      if not interaction.user.voice:
        await interaction.response.send_message(
            "You need to be in a voice channel first!", ephemeral=True
        )
        return

      voice_channel = interaction.user.voice.channel
      voice_client = interaction.guild.voice_client

      if not voice_client:
        voice_client = await voice_channel.connect()
      elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

      await interaction.response.defer()

      try:
        player = await YTDLSource.from_url(query, loop=self.loop, stream=True)
      except Exception as e:
        await interaction.followup.send(f"An error occurred: `{e}`")
        return

      guild_id = interaction.guild.id
      if guild_id not in self.queues:
        self.queues[guild_id] = []

      self.queues[guild_id].append(player)

      if not voice_client.is_playing():
        self.play_next(interaction.guild, voice_client)
        await interaction.followup.send(f"Now playing: **{player.title}**")
      else:
        await interaction.followup.send(
            f"Added to queue: **{player.title}**"
        )

    @self.tree.command(
        name="skip", description="Skip the currently playing song."
    )
    async def skip(interaction: discord.Interaction):
      voice_client = interaction.guild.voice_client
      if not voice_client or not voice_client.is_playing():
        await interaction.response.send_message(
            "Nothing is playing right now.", ephemeral=True
        )
        return

      voice_client.stop()
      await interaction.response.send_message("Skipped song!")

    @self.tree.command(name="queue", description="View the current music queue.")
    async def queue(interaction: discord.Interaction):
      guild_id = interaction.guild.id
      q = self.queues.get(guild_id, [])
      if not q:
        await interaction.response.send_message(
            "The queue is currently empty.", ephemeral=True
        )
        return

      queue_list = "\n".join(
          [f"{i+1}. {song.title}" for i, song in enumerate(q[:10])]
      )
      embed = discord.Embed(
          title="Server Queue",
          description=queue_list,
          color=discord.Color.blurple(),
      )
      await interaction.response.send_message(embed=embed)

    @self.tree.command(
        name="stop", description="Stop playback and clear the queue."
    )
    async def stop(interaction: discord.Interaction):
      voice_client = interaction.guild.voice_client
      if not voice_client:
        await interaction.response.send_message(
            "I'm not in a voice channel.", ephemeral=True
        )
        return

      guild_id = interaction.guild.id
      if guild_id in self.queues:
        self.queues[guild_id].clear()

      voice_client.stop()
      await voice_client.disconnect()
      await interaction.response.send_message("Stopped music and disconnected.")

    await self.tree.sync()
    print(f"Synced slash commands for {self.user}")

  def play_next(self, guild, voice_client):
    guild_id = guild.id
    if guild_id in self.queues and len(self.queues[guild_id]) > 0:
      player = self.queues[guild_id].pop(0)

      def after_playing(error):
        if error:
          print(f"Player error: {error}")
        self.play_next(guild, voice_client)

      voice_client.play(player, after=after_playing)

  async def on_ready(self):
    print(f"Logged in as {self.user} (ID: {self.user.id})")


bot = MusicBot()

# Make sure you set your bot token as an environment variable or paste it here securely
bot.run(os.getenv("TOKEN"))
    
