import discord
from discord.ext import commands
import yt_dlp
from discord.ui import Button, View, Select
import asyncio
from collections import deque
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import random
import json
import lyricsgenius

# Environment variable'lardan bilgileri al
TOKEN = os.getenv('TOKEN')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
GENIUS_TOKEN = os.getenv('GENIUS_TOKEN')  # Şarkı sözleri için Genius API token'ı

# Environment variable kontrolü
if not TOKEN:
    raise ValueError("TOKEN environment variable'ı bulunamadı!")
if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise ValueError("Spotify API bilgileri bulunamadı!")

# Spotify ve Genius istemcilerini başlat
try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    ))
    genius = lyricsgenius.Genius(GENIUS_TOKEN)
except Exception as e:
    print(f"API bağlantısı kurulamadı: {str(e)}")
    raise

# Botun prefixini ve intentlerini belirliyoruz
intents = discord.Intents.all()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=['!', '.'], intents=intents)

# Müzik kuyruğunu ve şu an çalan şarkıyı tutacak sözlükler
music_queues = {}
current_songs = {}
is_paused = {}
loop_modes = {}  # none, song, queue
saved_playlists = {}
dj_roles = {}

# Ses filtrelerini ve otomatik özellikleri tutacak sözlükler
filters = {}  # nightcore, 8d, vaporwave
autoplay_enabled = {}  # autoplay durumu
autodj_enabled = {}  # autodj durumu

# Yardım komutu
@bot.command(aliases=['yardım', 'y', 'komutlar'])
async def commands(ctx):
    embed = discord.Embed(title="🎵 NoceBOT Komutları", color=discord.Color.blue())
    
    # Temel Komutlar
    basic_commands = """
    `!play`, `!çal` - Şarkı çal
    `!stop`, `!dur` - Şarkıyı durdur
    `!pause`, `!duraklat` - Şarkıyı duraklat
    `!resume`, `!devam` - Şarkıyı devam ettir
    `!skip`, `!geç` - Şarkıyı geç
    `!join`, `!katıl` - Sesli kanala katıl
    """
    embed.add_field(name="📌 Temel Komutlar", value=basic_commands, inline=False)
    
    # Sıra Komutları
    queue_commands = """
    `!queue`, `!sıra` - Sırayı göster
    `!clear`, `!temizle` - Sırayı temizle
    `!shuffle`, `!karıştır` - Sırayı karıştır
    `!loop`, `!döngü` - Döngü modunu değiştir
    `!remove`, `!kaldır` - Sıradan şarkı kaldır
    `!move`, `!taşı` - Sıradaki şarkıları taşı
    """
    embed.add_field(name="📋 Sıra Komutları", value=queue_commands, inline=False)
    
    # Bilgi Komutları
    info_commands = """
    `!now`, `!şuan` - Çalan şarkı bilgisi
    `!lyrics`, `!sözler` - Şarkı sözleri
    `!search`, `!ara` - YouTube'da ara
    """
    embed.add_field(name="ℹ️ Bilgi Komutları", value=info_commands, inline=False)
    
    # Playlist Komutları
    playlist_commands = """
    `!save`, `!kaydet` - Playlist kaydet
    `!load`, `!yükle` - Playlist yükle
    `!list`, `!listele` - Playlistleri listele
    """
    embed.add_field(name="💾 Playlist Komutları", value=playlist_commands, inline=False)
    
    # DJ Komutları
    dj_commands = """
    `!dj` - DJ rolü ayarla
    `!voteskip`, `!oylageç` - Oylama ile geç
    `!forceskip`, `!zorla` - Zorla geç (DJ)
    """
    embed.add_field(name="🎧 DJ Komutları", value=dj_commands, inline=False)
    
    await ctx.send(embed=embed)

# Şarkıyı durdur
@bot.command(aliases=['stop', 'dur', 'leave', 'ayrıl'])
async def stop_music(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        if ctx.guild.id in music_queues:
            music_queues[ctx.guild.id].clear()
        await ctx.send("👋 Görüşürüz!")

# Şarkıyı duraklat/devam ettir
@bot.command(aliases=['pause', 'duraklat'])
async def pause_music(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        is_paused[ctx.guild.id] = True
        await ctx.send("⏸️ Şarkı duraklatıldı")

@bot.command(aliases=['resume', 'devam'])
async def resume_music(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        is_paused[ctx.guild.id] = False
        await ctx.send("▶️ Şarkı devam ediyor")

# Sırayı karıştır
@bot.command(aliases=['shuffle', 'karıştır'])
async def shuffle_queue(ctx):
    if ctx.guild.id in music_queues and music_queues[ctx.guild.id]:
        queue = list(music_queues[ctx.guild.id])
        random.shuffle(queue)
        music_queues[ctx.guild.id] = deque(queue)
        await ctx.send("🔀 Sıra karıştırıldı!")
    else:
        await ctx.send("❌ Sırada şarkı yok!")

# Döngü modu
@bot.command(aliases=['loop', 'döngü'])
async def toggle_loop(ctx, mode=None):
    if mode is None:
        # Döngü modları: none -> song -> queue -> none
        current_mode = loop_modes.get(ctx.guild.id, "none")
        if current_mode == "none":
            loop_modes[ctx.guild.id] = "song"
            await ctx.send("🔂 Şarkı döngüsü açıldı")
        elif current_mode == "song":
            loop_modes[ctx.guild.id] = "queue"
            await ctx.send("🔁 Sıra döngüsü açıldı")
        else:
            loop_modes[ctx.guild.id] = "none"
            await ctx.send("➡️ Döngü kapatıldı")
    else:
        mode = mode.lower()
        if mode in ["none", "kapalı", "off"]:
            loop_modes[ctx.guild.id] = "none"
            await ctx.send("➡️ Döngü kapatıldı")
        elif mode in ["song", "şarkı", "current", "this"]:
            loop_modes[ctx.guild.id] = "song"
            await ctx.send("🔂 Şarkı döngüsü açıldı")
        elif mode in ["queue", "sıra", "all"]:
            loop_modes[ctx.guild.id] = "queue"
            await ctx.send("🔁 Sıra döngüsü açıldı")

# Şu an çalan şarkı bilgisi
@bot.command(aliases=['now', 'şuan', 'playing', 'np'])
async def now_playing(ctx):
    if ctx.guild.id in current_songs and ctx.voice_client and ctx.voice_client.is_playing():
        title = current_songs[ctx.guild.id]
        embed = discord.Embed(title="🎵 Şu an çalıyor", description=title, color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")

# Şarkı sözleri
@bot.command(aliases=['lyrics', 'sözler'])
async def get_lyrics(ctx):
    if ctx.guild.id in current_songs:
        title = current_songs[ctx.guild.id]
        try:
            # Şarkı adını temizle
            title = title.split('(')[0]  # Parantez içindeki kısımları kaldır
            title = title.split('[')[0]  # Köşeli parantez içindeki kısımları kaldır
            title = title.split('feat.')[0]  # feat. kısmını kaldır
            title = title.split('ft.')[0]  # ft. kısmını kaldır
            title = title.split('Official')[0]  # Official kısmını kaldır
            title = title.split('Music')[0]  # Music kısmını kaldır
            title = title.split('Video')[0]  # Video kısmını kaldır
            title = title.strip()  # Baştaki ve sondaki boşlukları kaldır
            
            # Genius'ta ara
            song = genius.search_song(title)
            if song:
                lyrics = song.lyrics
                # Şarkı sözlerini parçalara böl (Discord mesaj limiti)
                chunks = [lyrics[i:i+1900] for i in range(0, len(lyrics), 1900)]
                
                # İlk embed'e şarkı bilgilerini ekle
                first_embed = discord.Embed(
                    title=f"🎵 {song.title}",
                    description=chunks[0],
                    color=discord.Color.blue()
                )
                first_embed.set_author(name=song.artist)
                if song.song_art_image_url:
                    first_embed.set_thumbnail(url=song.song_art_image_url)
                await ctx.send(embed=first_embed)
                
                # Diğer parçaları gönder
                for chunk in chunks[1:]:
                    embed = discord.Embed(description=chunk, color=discord.Color.blue())
                    await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Şarkı sözleri bulunamadı!")
        except Exception as e:
            print(f"Lyrics error: {str(e)}")  # Hata detayını konsola yazdır
            await ctx.send(f"❌ Şarkı sözleri alınırken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")
    else:
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")

# Playlist kaydet/yükle
@bot.command(aliases=['save', 'kaydet'])
async def save_playlist(ctx, name):
    if ctx.guild.id in music_queues and music_queues[ctx.guild.id]:
        if ctx.guild.id not in saved_playlists:
            saved_playlists[ctx.guild.id] = {}
        saved_playlists[ctx.guild.id][name] = list(music_queues[ctx.guild.id])
        # Playlistleri dosyaya kaydet
        with open('playlists.json', 'w', encoding='utf-8') as f:
            json.dump(saved_playlists, f, ensure_ascii=False, indent=4)
        await ctx.send(f"✅ Playlist '{name}' kaydedildi!")
    else:
        await ctx.send("❌ Sırada şarkı yok!")

@bot.command(aliases=['load', 'yükle'])
async def load_playlist(ctx, name):
    if ctx.guild.id in saved_playlists and name in saved_playlists[ctx.guild.id]:
        if ctx.guild.id not in music_queues:
            music_queues[ctx.guild.id] = deque()
        playlist = saved_playlists[ctx.guild.id][name]
        music_queues[ctx.guild.id].extend(playlist)
        await ctx.send(f"✅ Playlist '{name}' yüklendi! {len(playlist)} şarkı sıraya eklendi.")
        if not ctx.voice_client.is_playing():
            await play_next(ctx)
    else:
        await ctx.send(f"❌ '{name}' adlı playlist bulunamadı!")

@bot.command(aliases=['list', 'listele'])
async def list_playlists(ctx):
    if ctx.guild.id in saved_playlists and saved_playlists[ctx.guild.id]:
        playlists = list(saved_playlists[ctx.guild.id].keys())
        embed = discord.Embed(title="📋 Kayıtlı Playlistler", color=discord.Color.blue())
        for i, name in enumerate(playlists, 1):
            embed.add_field(name=f"{i}. {name}", value=f"{len(saved_playlists[ctx.guild.id][name])} şarkı", inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Kayıtlı playlist yok!")

# DJ sistemi
@bot.command()
async def dj(ctx, role: discord.Role = None):
    if ctx.author.guild_permissions.administrator:
        if role:
            dj_roles[ctx.guild.id] = role.id
            await ctx.send(f"✅ DJ rolü {role.mention} olarak ayarlandı!")
        else:
            if ctx.guild.id in dj_roles:
                del dj_roles[ctx.guild.id]
                await ctx.send("✅ DJ rolü kaldırıldı!")
            else:
                await ctx.send("❌ DJ rolü zaten ayarlanmamış!")
    else:
        await ctx.send("❌ Bu komutu kullanmak için yönetici yetkisine sahip olmalısın!")

@bot.command(aliases=['voteskip', 'oylageç'])
async def vote_skip(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")
        return

    # Oylama mesajı
    msg = await ctx.send("Şarkıyı geçmek için oylama başladı! ✅ ile oyla!")
    await msg.add_reaction("✅")
    
    def check(reaction, user):
        return str(reaction.emoji) == "✅" and not user.bot and user.voice and user.voice.channel == ctx.voice_client.channel

    try:
        # 30 saniye bekle ve oyları topla
        await asyncio.sleep(30)
        msg = await ctx.channel.fetch_message(msg.id)
        votes = [reaction for reaction in msg.reactions if str(reaction.emoji) == "✅"][0]
        
        # Sesli kanaldaki kişi sayısının yarısından fazlası oy verdiyse
        voice_members = len([m for m in ctx.voice_client.channel.members if not m.bot])
        if votes.count >= voice_members / 2:
            ctx.voice_client.stop()
            await ctx.send("🎵 Oylama başarılı! Şarkı geçiliyor...")
        else:
            await ctx.send("❌ Yeterli oy toplanamadı!")
    except Exception as e:
        await ctx.send(f"❌ Bir hata oluştu: {str(e)}")

@bot.command(aliases=['forceskip', 'zorla'])
async def force_skip(ctx):
    if ctx.guild.id in dj_roles:
        role = ctx.guild.get_role(dj_roles[ctx.guild.id])
        if role not in ctx.author.roles:
            await ctx.send("❌ Bu komutu kullanmak için DJ rolüne sahip olmalısın!")
            return
    
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Şarkı geçildi!")
    else:
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")

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
        try:
            if interaction.guild.voice_client and interaction.guild.voice_client.source:
                volume = int(self.values[0]) / 100
                interaction.guild.voice_client.source.volume = volume
                emoji = "🔇" if volume == 0 else "🔈" if volume < 0.4 else "🔉" if volume < 0.8 else "🔊"
                await interaction.response.send_message(f"{emoji} Ses seviyesi {int(volume * 100)}% olarak ayarlandı!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Şu anda çalan bir şarkı yok!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ses seviyesi ayarlanırken bir hata oluştu: {str(e)}", ephemeral=True)

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

        # Ses filtrelerini uygula
        guild_id = ctx.guild.id
        filter_options = []
        
        if guild_id in filters:
            if filters[guild_id].get("nightcore", False):
                filter_options.append("atempo=1.25")
            if filters[guild_id].get("8d", False):
                filter_options.append("apulsator=hz=0.08:width=0.8")
            if filters[guild_id].get("vaporwave", False):
                filter_options.append("atempo=0.8")

        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -acodec libopus' + (f' -af "{",".join(filter_options)}"' if filter_options else '')
        }

        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                # YouTube'da ara
                if query.startswith('ytsearch:'):
                    info = ydl.extract_info(query, download=False)
                    if info.get('entries'):
                        info = info['entries'][0]
                else:
                    info = ydl.extract_info(query, download=False)

                if not info:
                    await ctx.send("❌ Şarkı bulunamadı!")
                    return

                # Şarkı bilgilerini al
                title = info.get('title', 'Bilinmeyen şarkı')
                url = info.get('url')
                video_id = info.get('id')
                
                if not url:
                    await ctx.send("❌ Şarkı URL'si alınamadı!")
                    return

                # Ses kaynağını oluştur
                source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
                source.volume = 1.0

                # Önceki şarkıyı durdur
                if ctx.voice_client.is_playing():
                    ctx.voice_client.stop()

                # Yeni şarkıyı çal
                def after_playing(error):
                    async def next_song():
                        if error:
                            print(f'Oynatma hatası: {error}')
                        
                        if ctx.guild.id in autoplay_enabled and autoplay_enabled[ctx.guild.id]:
                            # Benzer şarkıları al
                            try:
                                related_url = f"https://www.youtube.com/watch?v={video_id}"
                                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                                    info = ydl.extract_info(related_url, download=False)
                                    if info.get('related_videos'):
                                        next_video = random.choice(info['related_videos'])
                                        next_url = f"https://www.youtube.com/watch?v={next_video['id']}"
                                        asyncio.create_task(play_song(ctx, next_url))
                                        return
                            except Exception as e:
                                print(f"Autoplay error: {str(e)}")
                        
                        await play_next(ctx)
                    
                    asyncio.run_coroutine_threadsafe(next_song(), bot.loop)

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
async def play(ctx, *, query):
    if ctx.author.voice is None:
        await ctx.send("Bir sesli kanalda değilsiniz!")
        return
    
    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()
    else:
        await ctx.voice_client.move_to(voice_channel)

    try:
        # URL kontrolü
        if 'http' in query:
            # Spotify URL'si kontrolü
            if 'spotify.com' in query:
                tracks = await get_spotify_tracks(query)
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
            if 'playlist' in query:
                YDL_OPTIONS = {
                    'format': 'bestaudio/best',
                    'extract_flat': True,
                    'quiet': True
                }
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    try:
                        info = ydl.extract_info(query, download=False)
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
                return

            # Tekli URL
            if ctx.voice_client.is_playing():
                if ctx.guild.id not in music_queues:
                    music_queues[ctx.guild.id] = deque()
                music_queues[ctx.guild.id].append(query)
                await ctx.send(f'Şarkı sıraya eklendi! Sırada {len(music_queues[ctx.guild.id])} şarkı var.')
            else:
                await play_song(ctx, query)
        else:
            # Şarkı ismi ile arama
            search_query = f"ytsearch:{query}"
            if ctx.voice_client.is_playing():
                if ctx.guild.id not in music_queues:
                    music_queues[ctx.guild.id] = deque()
                music_queues[ctx.guild.id].append(search_query)
                await ctx.send(f'Şarkı sıraya eklendi! Sırada {len(music_queues[ctx.guild.id])} şarkı var.')
            else:
                await play_song(ctx, search_query)
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

# Ses filtreleri
@bot.command(aliases=['nightcore', 'nc'])
async def nightcore_filter(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")
        return
    
    guild_id = ctx.guild.id
    if guild_id not in filters:
        filters[guild_id] = {"nightcore": False, "8d": False, "vaporwave": False}
    
    filters[guild_id]["nightcore"] = not filters[guild_id]["nightcore"]
    
    # Şarkıyı yeniden başlat
    if ctx.guild.id in current_songs:
        current_title = current_songs[ctx.guild.id]
        ctx.voice_client.stop()
        await play_song(ctx, f"ytsearch:{current_title}")
        
        if filters[guild_id]["nightcore"]:
            await ctx.send("🎵 Nightcore modu açıldı!")
        else:
            await ctx.send("🎵 Nightcore modu kapatıldı!")

@bot.command(aliases=['8d'])
async def eight_d_filter(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")
        return
    
    guild_id = ctx.guild.id
    if guild_id not in filters:
        filters[guild_id] = {"nightcore": False, "8d": False, "vaporwave": False}
    
    filters[guild_id]["8d"] = not filters[guild_id]["8d"]
    
    # Şarkıyı yeniden başlat
    if ctx.guild.id in current_songs:
        current_title = current_songs[ctx.guild.id]
        ctx.voice_client.stop()
        await play_song(ctx, f"ytsearch:{current_title}")
        
        if filters[guild_id]["8d"]:
            await ctx.send("🎵 8D ses modu açıldı!")
        else:
            await ctx.send("🎵 8D ses modu kapatıldı!")

@bot.command(aliases=['vaporwave', 'vw'])
async def vaporwave_filter(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")
        return
    
    guild_id = ctx.guild.id
    if guild_id not in filters:
        filters[guild_id] = {"nightcore": False, "8d": False, "vaporwave": False}
    
    filters[guild_id]["vaporwave"] = not filters[guild_id]["vaporwave"]
    
    # Şarkıyı yeniden başlat
    if ctx.guild.id in current_songs:
        current_title = current_songs[ctx.guild.id]
        ctx.voice_client.stop()
        await play_song(ctx, f"ytsearch:{current_title}")
        
        if filters[guild_id]["vaporwave"]:
            await ctx.send("🎵 Vaporwave modu açıldı!")
        else:
            await ctx.send("🎵 Vaporwave modu kapatıldı!")

# Otomatik özellikler
@bot.command(aliases=['autoplay', 'otomatik'])
async def toggle_autoplay(ctx):
    guild_id = ctx.guild.id
    autoplay_enabled[guild_id] = not autoplay_enabled.get(guild_id, False)
    
    if autoplay_enabled[guild_id]:
        await ctx.send("🎵 Otomatik çalma modu açıldı! Şarkı bitince benzer şarkılar çalınacak.")
    else:
        await ctx.send("🎵 Otomatik çalma modu kapatıldı!")

@bot.command(aliases=['autodj', 'djauto'])
async def toggle_autodj(ctx):
    guild_id = ctx.guild.id
    autodj_enabled[guild_id] = not autodj_enabled.get(guild_id, False)
    
    if autodj_enabled[guild_id]:
        await ctx.send("🎵 AutoDJ modu açıldı! Her 5 dakikada bir rastgele şarkı çalınacak.")
        await auto_dj(ctx)
    else:
        await ctx.send("🎵 AutoDJ modu kapatıldı!")

async def auto_dj(ctx):
    while autodj_enabled.get(ctx.guild.id, False):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            # Rastgele bir şarkı seç ve çal
            random_songs = [
                "ytsearch:pop hits 2023",
                "ytsearch:rock classics",
                "ytsearch:electronic dance music",
                "ytsearch:hip hop hits",
                "ytsearch:türkçe pop"
            ]
            await play_song(ctx, random.choice(random_songs))
        await asyncio.sleep(300)  # 5 dakika bekle

# Botu çalıştır
bot.run(TOKEN)