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

# Ekolayzır ayarlarını tutacak sözlükler
equalizer_settings = {}  # Aktif ekolayzır ayarları
equalizer_presets = {}  # Kayıtlı ekolayzır presetleri

# Yeni sözlükler
stats = {}  # İstatistikler
radio_stations = {
    "powerturk": "https://listen.powerapp.com.tr/powerturk/mpeg/icecast.audio",
    "power": "https://listen.powerapp.com.tr/powerfm/mpeg/icecast.audio",
    "slowturk": "https://radyo.duhnet.tv/ak_dtvh_slowturk",
    "fenomen": "https://live.radyofenomen.com/fenomen/128/icecast.audio",
    "kral": "https://dygedge.radyotvonline.net/kralpop/playlist.m3u8",
    "virgin": "https://playerservices.streamtheworld.com/api/livestream-redirect/VIRGIN_RADIOAAC.aac",
    "joyturk": "https://playerservices.streamtheworld.com/api/livestream-redirect/JOY_TURK.mp3",
    "metro": "https://playerservices.streamtheworld.com/api/livestream-redirect/METRO_FM.mp3"
}

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
                # Şarkı s��zlerini parçalara böl (Discord mesaj limiti)
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

        # Ekolayzır ayarlarını uygula
        guild_id = ctx.guild.id
        filter_options = []
        
        if guild_id in equalizer_settings:
            if equalizer_settings[guild_id] != "default" and equalizer_settings[guild_id] is not None:
                filter_options.append(equalizer_settings[guild_id])

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
                duration = info.get('duration', 0)
                
                if not url:
                    await ctx.send("❌ Şarkı URL'si alınamadı!")
                    return

                # İstatistikleri güncelle
                if guild_id not in stats:
                    stats[guild_id] = {
                        "total_songs": 0,
                        "total_time": 0,
                        "favorite_songs": {}
                    }
                
                stats[guild_id]["total_songs"] += 1
                stats[guild_id]["total_time"] += duration
                stats[guild_id]["favorite_songs"][title] = stats[guild_id]["favorite_songs"].get(title, 0) + 1

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

# Ekolayzır komutları
@bot.command(aliases=['eq', 'ekolayzır'])
async def equalizer(ctx, action=None, *args):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")
        return
    
    guild_id = ctx.guild.id
    
    if action is None:
        # Mevcut ayarları ve komutları göster
        embed = discord.Embed(title="🎛️ Ekolayzır Ayarları", color=discord.Color.blue())
        
        # Aktif ayarlar
        current_settings = equalizer_settings.get(guild_id, "default")
        if isinstance(current_settings, str):
            current = f"Aktif Preset: {current_settings}"
        else:
            current = "Özel ayarlar aktif"
        embed.add_field(name="Mevcut Durum", value=current, inline=False)
        
        # Komutlar
        commands = """
        `!eq preset <ad>` - Kayıtlı preset'i kullan
        `!eq default` - Varsayılan ayarlara dön
        `!eq set <frekans> <gain>` - Manuel ayar (ör: !eq set 100 5)
        `!eq save <ad>` - Mevcut ayarları preset olarak kaydet
        `!eq list` - Kayıtlı presetleri listele
        `!eq clear` - Tüm efektleri kaldır
        
        Frekans aralıkları:
        • 32, 64, 125, 250, 500, 1k, 2k, 4k, 8k, 16k
        Gain aralığı: -20 ile +20 arası
        """
        embed.add_field(name="Komutlar", value=commands, inline=False)
        
        # Varsayılan presetler
        presets = """
        `!eq preset bass` - Bass boost
        `!eq preset pop` - Pop müzik
        `!eq preset rock` - Rock müzik
        `!eq preset classical` - Klasik müzik
        `!eq preset jazz` - Jazz müzik
        """
        embed.add_field(name="Varsayılan Presetler", value=presets, inline=False)
        
        await ctx.send(embed=embed)
        return
    
    action = action.lower()
    
    if action == "default":
        equalizer_settings[guild_id] = "default"
        await restart_song(ctx, "🎛️ Ekolayzır varsayılan ayarlara döndü!")
    
    elif action == "clear":
        equalizer_settings[guild_id] = None
        await restart_song(ctx, "🎛️ Tüm ekolayzır efektleri kaldırıldı!")
    
    elif action == "preset":
        if not args:
            await ctx.send("❌ Preset adı belirtmelisiniz!")
            return
        
        preset_name = args[0].lower()
        
        # Varsayılan presetler
        default_presets = {
            "bass": "bass=g=10,equalizer=f=40:t=h:w=100:g=10",
            "pop": "equalizer=f=1000:t=h:w=200:g=3,equalizer=f=3000:t=h:w=200:g=2",
            "rock": "equalizer=f=60:t=h:w=100:g=5,equalizer=f=3000:t=h:w=100:g=3",
            "classical": "equalizer=f=500:t=h:w=100:g=2,equalizer=f=4000:t=h:w=100:g=3",
            "jazz": "equalizer=f=100:t=h:w=100:g=3,equalizer=f=8000:t=h:w=100:g=2"
        }
        
        # Önce kayıtlı presetlere bak
        if guild_id in equalizer_presets and preset_name in equalizer_presets[guild_id]:
            equalizer_settings[guild_id] = equalizer_presets[guild_id][preset_name]
            await restart_song(ctx, f"🎛️ '{preset_name}' preset'i uygulandı!")
        # Sonra varsayılan presetlere bak
        elif preset_name in default_presets:
            equalizer_settings[guild_id] = default_presets[preset_name]
            await restart_song(ctx, f"🎛️ '{preset_name}' preset'i uygulandı!")
        else:
            await ctx.send("❌ Böyle bir preset bulunamadı!")
    
    elif action == "set":
        if len(args) != 2:
            await ctx.send("❌ Frekans ve gain değerlerini belirtmelisiniz! Örnek: !eq set 100 5")
            return
        
        try:
            freq = args[0]
            gain = float(args[1])
            
            if gain < -20 or gain > 20:
                await ctx.send("❌ Gain değeri -20 ile +20 arasında olmalıdır!")
                return
            
            # Frekans kontrolü
            valid_freqs = {"32", "64", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"}
            if freq not in valid_freqs:
                await ctx.send("❌ Geçersiz frekans! Kullanılabilir frekanslar: 32, 64, 125, 250, 500, 1k, 2k, 4k, 8k, 16k")
                return
            
            # Mevcut ayarları al veya yeni oluştur
            if guild_id not in equalizer_settings or not isinstance(equalizer_settings[guild_id], dict):
                equalizer_settings[guild_id] = {}
            
            # Ayarı güncelle
            equalizer_settings[guild_id][freq] = gain
            
            # FFmpeg filtre stringini oluştur
            filters = []
            for f, g in equalizer_settings[guild_id].items():
                f = f.replace("k", "000")  # 1k -> 1000
                filters.append(f"equalizer=f={f}:t=h:w=100:g={g}")
            
            equalizer_settings[guild_id] = ",".join(filters)
            await restart_song(ctx, f"🎛️ {freq}Hz frekansı {gain}dB olarak ayarlandı!")
            
        except ValueError:
            await ctx.send("❌ Geçersiz gain değeri! Sayısal bir değer giriniz.")
    
    elif action == "save":
        if not args:
            await ctx.send("❌ Preset adı belirtmelisiniz!")
            return
        
        preset_name = args[0].lower()
        if guild_id not in equalizer_presets:
            equalizer_presets[guild_id] = {}
        
        current_settings = equalizer_settings.get(guild_id)
        if current_settings:
            equalizer_presets[guild_id][preset_name] = current_settings
            await ctx.send(f"✅ Mevcut ayarlar '{preset_name}' olarak kaydedildi!")
        else:
            await ctx.send("❌ Kaydedilecek aktif bir ayar yok!")
    
    elif action == "list":
        embed = discord.Embed(title="📋 Kayıtlı Ekolayzır Presetleri", color=discord.Color.blue())
        
        # Varsayılan presetler
        default_presets = "• bass\n• pop\n• rock\n• classical\n• jazz"
        embed.add_field(name="Varsayılan Presetler", value=default_presets, inline=False)
        
        # Kullanıcı presetleri
        if guild_id in equalizer_presets and equalizer_presets[guild_id]:
            user_presets = "\n".join([f"• {name}" for name in equalizer_presets[guild_id].keys()])
            embed.add_field(name="Kayıtlı Presetler", value=user_presets, inline=False)
        else:
            embed.add_field(name="Kayıtlı Presetler", value="Henüz kayıtlı preset yok", inline=False)
        
        await ctx.send(embed=embed)
    
    else:
        await ctx.send("❌ Geçersiz komut! Kullanılabilir komutları görmek için `!eq` yazın.")

async def restart_song(ctx, message):
    """Şarkıyı yeniden başlat ve mesaj gönder"""
    if ctx.guild.id in current_songs:
        current_title = current_songs[ctx.guild.id]
        ctx.voice_client.stop()
        await play_song(ctx, f"ytsearch:{current_title}")
        await ctx.send(message)

# İstatistik komutları
@bot.command(aliases=['stats', 'istatistik'])
async def show_stats(ctx):
    guild_id = ctx.guild.id
    if guild_id not in stats:
        stats[guild_id] = {
            "total_songs": 0,
            "total_time": 0,
            "favorite_songs": {}
        }
    
    embed = discord.Embed(title="📊 Bot İstatistikleri", color=discord.Color.blue())
    
    # Genel istatistikler
    total_songs = stats[guild_id]["total_songs"]
    total_time = stats[guild_id]["total_time"]
    hours = total_time // 3600
    minutes = (total_time % 3600) // 60
    
    general_stats = f"""
    Toplam çalınan şarkı: {total_songs}
    Toplam çalma süresi: {hours} saat {minutes} dakika
    """
    embed.add_field(name="Genel İstatistikler", value=general_stats, inline=False)
    
    # En çok çalınan şarkılar
    if stats[guild_id]["favorite_songs"]:
        top_songs = sorted(stats[guild_id]["favorite_songs"].items(), key=lambda x: x[1], reverse=True)[:5]
        favorite_songs = "\n".join([f"{i+1}. {song} ({count} kez)" for i, (song, count) in enumerate(top_songs)])
        embed.add_field(name="En Çok Çalınan Şarkılar", value=favorite_songs, inline=False)
    
    await ctx.send(embed=embed)

# Radyo komutları
@bot.command(aliases=['radio', 'radyo'])
async def play_radio(ctx, station=None):
    if station is None:
        # Radyo listesini göster
        embed = discord.Embed(title="📻 Radyo İstasyonları", color=discord.Color.blue())
        stations = "\n".join([f"`!radio {name}` - {name.title()}" for name in radio_stations.keys()])
        embed.add_field(name="Kullanılabilir İstasyonlar", value=stations)
        await ctx.send(embed=embed)
        return
    
    station = station.lower()
    if station not in radio_stations:
        await ctx.send("❌ Geçersiz radyo istasyonu! Kullanılabilir istasyonlar için `!radio` yazın.")
        return
    
    if ctx.author.voice is None:
        await ctx.send("Bir sesli kanalda değilsiniz!")
        return
    
    # Sesli kanala bağlan
    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()
    else:
        await ctx.voice_client.move_to(voice_channel)
    
    # Radyoyu çal
    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }
    
    url = radio_stations[station]
    source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
    
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    
    ctx.voice_client.play(source)
    await ctx.send(f"📻 {station.title()} radyosu çalınıyor!")

# Ses efektleri
@bot.command(aliases=['echo', 'eko'])
async def echo_effect(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")
        return
    
    guild_id = ctx.guild.id
    if guild_id not in filters:
        filters[guild_id] = {"echo": False}
    
    filters[guild_id]["echo"] = not filters[guild_id].get("echo", False)
    
    # Şarkıyı yeniden başlat
    if ctx.guild.id in current_songs:
        current_title = current_songs[ctx.guild.id]
        ctx.voice_client.stop()
        await play_song(ctx, f"ytsearch:{current_title}")
        
        if filters[guild_id]["echo"]:
            await ctx.send("🎵 Eko efekti açıldı!")
        else:
            await ctx.send("🎵 Eko efekti kapatıldı!")

@bot.command(aliases=['bass', 'bas'])
async def bass_boost(ctx, level="normal"):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("❌ Şu anda çalan bir şarkı yok!")
        return
    
    guild_id = ctx.guild.id
    if guild_id not in filters:
        filters[guild_id] = {"bass": None}
    
    if level.lower() == "off":
        filters[guild_id]["bass"] = None
        message = "🎵 Bass boost kapatıldı!"
    elif level.lower() == "low":
        filters[guild_id]["bass"] = "bass=g=5"
        message = "🎵 Bass boost düşük seviyeye ayarlandı!"
    elif level.lower() == "normal":
        filters[guild_id]["bass"] = "bass=g=10"
        message = "🎵 Bass boost normal seviyeye ayarlandı!"
    elif level.lower() == "high":
        filters[guild_id]["bass"] = "bass=g=20"
        message = "🎵 Bass boost yüksek seviyeye ayarlandı!"
    else:
        await ctx.send("❌ Geçersiz seviye! Kullanılabilir seviyeler: off, low, normal, high")
        return
    
    # Şarkıyı yeniden başlat
    if ctx.guild.id in current_songs:
        current_title = current_songs[ctx.guild.id]
        ctx.voice_client.stop()
        await play_song(ctx, f"ytsearch:{current_title}")
        await ctx.send(message)

# Botu çalıştır
bot.run(TOKEN)