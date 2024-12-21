import discord
from discord.ext import commands
import yt_dlp
from discord.ui import Button, View
import asyncio
from collections import deque
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os

# Environment variable'lardan bilgileri al
TOKEN = os.getenv('TOKEN')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# Spotify istemcisini başlat
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# Botun prefixini ve intentlerini belirliyoruz
intents = discord.Intents.all()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Müzik kuyruğunu ve şu an çalan şarkıyı tutacak sözlükler
music_queues = {}
current_songs = {}
is_paused = {}

async def get_spotify_tracks(url):
    tracks = []
    try:
        if 'track' in url:
            # Tekli şarkı
            track_id = url.split('/')[-1].split('?')[0]
            track = sp.track(track_id)
            search_query = f"ytsearch:{track['name']} {' '.join([artist['name'] for artist in track['artists']])}"
            tracks.append(search_query)
        
        elif 'playlist' in url:
            # Playlist
            playlist_id = url.split('/')[-1].split('?')[0]
            results = sp.playlist_tracks(playlist_id)
            
            for item in results['items']:
                if item['track']:
                    track = item['track']
                    search_query = f"ytsearch:{track['name']} {' '.join([artist['name'] for artist in track['artists']])}"
                    tracks.append(search_query)
            
            while results['next']:
                results = sp.next(results)
                for item in results['items']:
                    if item['track']:
                        track = item['track']
                        search_query = f"ytsearch:{track['name']} {' '.join([artist['name'] for artist in track['artists']])}"
                        tracks.append(search_query)
        
        elif 'album' in url:
            # Albüm
            album_id = url.split('/')[-1].split('?')[0]
            results = sp.album_tracks(album_id)
            
            for track in results['items']:
                search_query = f"ytsearch:{track['name']} {' '.join([artist['name'] for artist in track['artists']])}"
                tracks.append(search_query)
            
            while results['next']:
                results = sp.next(results)
                for track in results['items']:
                    search_query = f"ytsearch:{track['name']} {' '.join([artist['name'] for artist in track['artists']])}"
                    tracks.append(search_query)
    except Exception as e:
        print(f"Spotify track extraction error: {str(e)}")
        return None
    
    return tracks

class MusicControls(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.volume = 100

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.primary, custom_id="previous")
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Bu özellik yakında eklenecek!", ephemeral=True)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.success, custom_id="pause")
    async def pause_button(self, interaction: discord.Interaction, button: Button):
        if interaction.guild_id in is_paused and is_paused[interaction.guild_id]:
            interaction.guild.voice_client.resume()
            is_paused[interaction.guild_id] = False
            button.emoji = "⏸️"
            button.style = discord.ButtonStyle.success
        else:
            interaction.guild.voice_client.pause()
            is_paused[interaction.guild_id] = True
            button.emoji = "▶️"
            button.style = discord.ButtonStyle.danger
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary, custom_id="skip")
    async def skip_button(self, interaction: discord.Interaction, button: Button):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Şarkı geçildi!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Şu anda çalan bir şarkı yok!", ephemeral=True)

    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="loop")
    async def loop_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Bu özellik yakında eklenecek!", ephemeral=True)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, custom_id="volume")
    async def volume_button(self, interaction: discord.Interaction, button: Button):
        # Ses seviyesi menüsünü oluştur
        select = VolumeSelect(self.ctx)
        await interaction.response.send_message("Ses seviyesini seçin:", view=select, ephemeral=True)

class VolumeSelect(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.add_item(VolumeDropdown())

class VolumeDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Sessiz", emoji="🔇", value="0"),
            discord.SelectOption(label="20%", emoji="🔈", value="20"),
            discord.SelectOption(label="40%", emoji="🔈", value="40"),
            discord.SelectOption(label="60%", emoji="🔉", value="60"),
            discord.SelectOption(label="80%", emoji="🔊", value="80"),
            discord.SelectOption(label="100%", emoji="🔊", value="100"),
            discord.SelectOption(label="120%", emoji="🔊", value="120"),
            discord.SelectOption(label="150%", emoji="🔊", value="150"),
            discord.SelectOption(label="200%", emoji="🔊", value="200")
        ]
        super().__init__(placeholder="Ses Seviyesi", options=options, custom_id="volume_select")

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            volume = int(self.values[0]) / 100
            interaction.guild.voice_client.source.volume = volume
            emoji = "🔇" if volume == 0 else "🔈" if volume < 0.4 else "🔉" if volume < 0.8 else "🔊"
            await interaction.response.send_message(f"{emoji} Ses seviyesi {int(volume * 100)}% olarak ayarlandı!", ephemeral=True)

@bot.event
async def on_ready():
    print(f'Bot {bot.user} olarak giriş yaptı')
    print('Bot hazır!')

@bot.command()
async def join(ctx):
    if ctx.author.voice is None:
        await ctx.send("Bir sesli kanalda değilsiniz!")
        return
    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()
    else:
        await ctx.voice_client.move_to(voice_channel)

async def play_next(ctx):
    if ctx.guild.id in music_queues and music_queues[ctx.guild.id]:
        next_song = music_queues[ctx.guild.id].popleft()
        await play_song(ctx, next_song)

async def play_song(ctx, query):
    try:
        YDL_OPTIONS = {
            'format': 'bestaudio',
            'noplaylist': True,
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0'
        }

        FFMPEG_OPTIONS = {
            'options': '-vn'
        }

        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                # YouTube'da ara
                if query.startswith('ytsearch:'):
                    # Spotify şarkısı
                    info = ydl.extract_info(query, download=False)
                    if info.get('entries'):
                        info = info['entries'][0]
                else:
                    # YouTube URL'si
                    info = ydl.extract_info(query, download=False)

                if not info:
                    await ctx.send("❌ Şarkı bulunamadı!")
                    return

                # Şarkı bilgilerini al
                title = info.get('title', 'Bilinmeyen şarkı')
                url = info.get('url')
                
                if not url:
                    await ctx.send("❌ Şarkı URL'si alınamadı!")
                    return

                # Ses kaynağını oluştur
                source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)

                # Önceki şarkıyı durdur
                if ctx.voice_client.is_playing():
                    ctx.voice_client.stop()

                # Yeni şarkıyı çal
                def after_playing(error):
                    if error:
                        print(f'Oynatma hatası: {error}')
                    asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)

                ctx.voice_client.play(source, after=after_playing)
                current_songs[ctx.guild.id] = title

                # Kontrol butonlarını göster
                view = MusicControls(ctx)
                await ctx.send(f'🎵 Şu an çalıyor: {title}', view=view)

            except Exception as e:
                print(f"Error in play_song: {str(e)}")
                await ctx.send(f'❌ Şarkı çalınırken bir hata oluştu: {str(e)}')

    except Exception as e:
        print(f"Error in play_song (outer): {str(e)}")
        await ctx.send('❌ Şarkı çalınırken bir hata oluştu.')

@bot.command()
async def play(ctx, *, url):
    if ctx.author.voice is None:
        await ctx.send("Bir sesli kanalda değilsiniz!")
        return
    
    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()
    else:
        await ctx.voice_client.move_to(voice_channel)

    try:
        # Spotify URL'si kontrolü
        if 'spotify.com' in url:
            tracks = await get_spotify_tracks(url)
            if tracks:
                if len(tracks) > 1:
                    await ctx.send(f"Spotify'dan {len(tracks)} şarkı ekleniyor...")
                    
                    if ctx.guild.id not in music_queues:
                        music_queues[ctx.guild.id] = deque()
                    
                    for track in tracks:
                        music_queues[ctx.guild.id].append(track)
                    
                    if not ctx.voice_client.is_playing():
                        await play_next(ctx)
                else:
                    await play_song(ctx, tracks[0])
            else:
                await ctx.send("Spotify'dan şarkı bilgisi alınamadı!")
            return

        # YouTube playlist kontrolü
        if 'playlist' in url:
            YDL_OPTIONS = {
                'format': 'bestaudio/best',
                'extract_flat': True,
                'quiet': True
            }
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    if 'entries' in info:
                        if ctx.guild.id not in music_queues:
                            music_queues[ctx.guild.id] = deque()
                        
                        for entry in info['entries']:
                            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                            music_queues[ctx.guild.id].append(video_url)
                        
                        await ctx.send(f"Playlist'e {len(info['entries'])} şarkı eklendi!")
                        if not ctx.voice_client.is_playing():
                            await play_next(ctx)
                except Exception as e:
                    await ctx.send(f'Playlist eklenirken bir hata oluştu: {str(e)}')
        else:
            # Tekli şarkı
            if ctx.voice_client.is_playing():
                if ctx.guild.id not in music_queues:
                    music_queues[ctx.guild.id] = deque()
                music_queues[ctx.guild.id].append(url)
                await ctx.send(f'Şarkı sıraya eklendi! Sırada {len(music_queues[ctx.guild.id])} şarkı var.')
            else:
                await play_song(ctx, url)
    except Exception as e:
        await ctx.send(f'Bir hata oluştu: {str(e)}')

@bot.command()
async def queue(ctx):
    if ctx.guild.id in music_queues and music_queues[ctx.guild.id]:
        queue_list = '\n'.join([f"{i+1}. {url}" for i, url in enumerate(music_queues[ctx.guild.id])])
        await ctx.send(f"Sıradaki şarkılar:\n{queue_list}")
    else:
        await ctx.send("Sırada şarkı yok!")

@bot.command()
async def clear(ctx):
    if ctx.guild.id in music_queues:
        music_queues[ctx.guild.id].clear()
        await ctx.send("Sıra temizlendi!")

# Botu çalıştır
bot.run(TOKEN)