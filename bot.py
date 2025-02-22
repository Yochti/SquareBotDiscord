import discord
import os
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from discord.ext import commands
from discord.utils import utcnow
from PIL import Image, ImageDraw,ImageFont
import io
from discord.ext import tasks
from datetime import time, timezone
from keepalive import keep_alive

load_dotenv()
print("Lancement du bot...")
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

WELCOME_CHANNEL_ID = 1342979606810198097
GOODBYE_CHANNEL_ID = 1342979628511264838
ROLESLVL_CHANNEL_ID = 1342968068451733504
LEADERBOARD_CHANNEL_ID = 1342968031734923315  
XP_FILE = 'xp_data.json'
COOLDOWN_DURATION = 40  # Durée du cooldown en secondes

# Dictionnaire pour suivre le temps du dernier message de chaque utilisateur
last_message_times = {}

# Chargement des données XP
def load_xp_data():
    if os.path.exists(XP_FILE):
        try:
            with open(XP_FILE, 'r') as f:
                xp_data = json.load(f)
                if not isinstance(xp_data, dict):
                    raise ValueError("Données incorrectes dans le fichier.")
                return xp_data
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Erreur de lecture du fichier XP : {e}. Initialisation des données.")
            return {}
    return {}

# Sauvegarde des données d'XP
def save_xp_data(xp_data):
    with open(XP_FILE, 'w') as f:
        json.dump(xp_data, f, indent=4)

# Gagner de l'XP pour un utilisateur
def add_xp(user_id, xp_data):
    user_id_str = str(user_id)
    current_time = datetime.utcnow()

    # Vérifier le cooldown
    if user_id_str in last_message_times:
        time_since_last_message = current_time - last_message_times[user_id_str]
        if time_since_last_message < timedelta(seconds=COOLDOWN_DURATION):
            return xp_data, False, False  # Cooldown actif, ne pas ajouter d'XP

    # Mettre à jour le temps du dernier message
    last_message_times[user_id_str] = current_time

    if user_id_str not in xp_data:
        xp_data[user_id_str] = {"xp": 0, "level": 1}

    xp_gained = random.randint(10, 15)
    xp_data[user_id_str]["xp"] += xp_gained

    leveled_up = False
    if xp_data[user_id_str]["xp"] >= xp_data[user_id_str]["level"] * 100:
        xp_data[user_id_str]["level"] += 1
        xp_data[user_id_str]["xp"] = 0  # Réinitialiser l'XP au niveau suivant
        leveled_up = True

    save_xp_data(xp_data)
    return xp_data, True, leveled_up

# Fonction pour générer l'image de la barre d'expérience
# Fonction pour générer l'image de la barre d'expérience
def generate_xp_bar(level, xp, xp_to_next_level):
    bar_width = 300
    bar_height = 50
    background_color = (25, 25, 20)
    bar_color = (114, 137, 218)
    text_color = (255, 255, 255)

    # Créer une image vide
    image = Image.new('RGB', (bar_width, bar_height), background_color)
    draw = ImageDraw.Draw(image)

    # Calculer la largeur de la barre d'XP
    xp_width = int((xp / (level * 100)) * bar_width)  # Correction ici

    # Dessiner la barre d'XP
    draw.rectangle([0, 0, xp_width, bar_height], fill=bar_color)
    # Ajouter le texte
    try:
        font = ImageFont.truetype("arial.ttf",18)
    except IOError:
        font = ImageFont.load_default()

    # Ajuster la position verticale du texte
    text_position = (10, 16.9)  # Position intermédiaire
    draw.text(text_position, f"Level {level}", font=font, fill=text_color)

    # Enregistrer l'image dans un buffer
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)

    return buffer
@tasks.loop(time=time(hour=23, minute=00, tzinfo=timezone.utc))
async def send_daily_leaderboard():
    guild = bot.guilds[0]  # Prend le premier serveur où est le bot (ajuster si nécessaire)
    channel = guild.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        print("⚠️ Erreur : Channel de leaderboard introuvable.")
        return

    xp_data = load_xp_data()

    sorted_users = sorted(xp_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)

    embed = discord.Embed(
        title="🌟 Classement Quotidien 🌟",
        description="Les 10 plus gros parleurs du serveur à ce jour 🏆",
        color=discord.Color.gold()
    )

    leaderboard_text = ""
    medal_emojis = ["🥇", "🥈", "🥉"]

    for i, (user_id, data) in enumerate(sorted_users[:10], start=1):
        member = guild.get_member(int(user_id))
        if member:
            emoji = medal_emojis[i - 1] if i <= 3 else "🔹"
            leaderboard_text += f"{emoji} **#{i}** - `{member.display_name}` | Niveau **{data['level']}** | **{data['xp']} XP**\n"

    embed.add_field(name="📌 Top 10", value=leaderboard_text or "Personne n'a encore parlé aujourd'hui !", inline=False)
    embed.set_footer(text="Classement remis à zéro tous les jours à minuit !")

    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print("Bot allumé !")
    try:
        synced = await bot.tree.sync()
        print(f"Commandes synchronisées : {len(synced)} ")
    except Exception as e:
        print(e)

    if not send_daily_leaderboard.is_running():
        send_daily_leaderboard.start()



# Dictionnaire des rôles à attribuer selon le niveau
LEVEL_ROLES = {
    5: 1342874804667285516,  # Remplace par l'ID du rôle pour le niveau 5
    10: 1342877661093040160, # ID du rôle pour le niveau 10
    15: 1342877855071080571, # ID du rôle pour le niveau 15
    20: 1342877957462691871  # ID du rôle pour le niveau 20
}

# Fonction pour attribuer un rôle en fonction du niveau
async def assign_level_role(member: discord.Member, level: int):
    guild = member.guild
    if level in LEVEL_ROLES:
        role = guild.get_role(LEVEL_ROLES[level])
        if role and role not in member.roles:
            try:
                await member.add_roles(role)

                # Création de l'embed
                embed = discord.Embed(
                    title="🌟 Nouveau Rang Atteint !",
                    description=f"🎉 Félicitations {member.mention} !\n\nTu as atteint **le niveau {level}** et reçu le rôle **{role.name}** ! 🚀",
                    color=discord.Color.gold()
                )
                embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                embed.set_footer(text="Continue comme ça pour monter encore plus haut !")

                # Envoi de l'embed dans le channel de montée de niveau
                channel = guild.get_channel(ROLESLVL_CHANNEL_ID)
                if channel:
                    await channel.send(embed=embed)
                else:
                    print(f"❌ Erreur : Channel ID {ROLESLVL_CHANNEL_ID} introuvable.")

                print(f"✅ Rôle {role.name} attribué à {member.display_name} (Niveau {level})")
            except discord.Forbidden:
                print(f"❌ Impossible d'ajouter le rôle {role.name} à {member.display_name} (permissions insuffisantes)")
            except discord.HTTPException as e:
                print(f"❌ Erreur HTTP en attribuant le rôle : {e}")

@bot.tree.command(name="help", description="Affiche la liste des commandes disponibles")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📜 Liste des Commandes",
        description="Voici toutes les commandes disponibles sur le serveur !",
        color=discord.Color.blue()
    )

    embed.add_field(name="🎖 **XP & Niveau**", value=(
        "`/niveau [@membre]` - Affiche le niveau et l'XP d'un utilisateur.\n"
        "`/rang [@membre]` - Affiche le rang d'un utilisateur dans le serveur.\n"
        "`/classement` - Affiche le top 10 des utilisateurs avec le plus d'XP."
    ), inline=False)

    embed.add_field(name="⚔️ **Modération**", value=(
        "`/banguy @membre` - Bannir un utilisateur du serveur.\n"
        "`/toguy @membre durée` - Mute un utilisateur pour une durée spécifiée (en minutes)."
    ), inline=False)

    embed.set_footer(text="Besoin d'aide ? Contacte un administrateur.")

    await interaction.response.send_message(embed=embed, ephemeral=True)
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    xp_data = load_xp_data()
    user_id_str = str(message.author.id)

    xp_data, xp_added, leveled_up = add_xp(user_id_str, xp_data)

    if leveled_up:
        user_xp = xp_data.get(user_id_str, {"xp": 0, "level": 1})
        level = user_xp["level"]
        xp = user_xp["xp"]
        xp_to_next_level = level * 100

        # Créer un embed pour la montée de niveau
        embed = discord.Embed(
            title=f"🎉 Bravo {message.author.display_name} !",
            description=f"Tu viens de passer **niveau {level}** ! 🚀",
            color=discord.Color.green()
        )
        embed.add_field(name="📊 XP Actuelle", value=f"{xp}/{xp_to_next_level}", inline=True)
        embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)

        await message.channel.send(f"{message.author.mention}", embed=embed)

        # Assigner un rôle si applicable
        await assign_level_role(message.author, level)

    if "bonjour" in message.content.lower():
        channel = message.channel
        user = message.author
        await message.add_reaction("👋")
        await channel.send(f"Bonjour {str(user)} ! Comment vas-tu ?")
# Commande pour afficher le niveau et l'XP actuels avec une barre d'expérience dans un embed
@bot.tree.command(name="niveau", description="Affiche le niveau et l'XP d'un utilisateur")
async def niveau(interaction: discord.Interaction, membre: discord.Member = None):
    xp_data = load_xp_data()

    # Si aucun membre n'est spécifié, on prend l'auteur de la commande
    membre = membre or interaction.user
    user_id_str = str(membre.id)

    # Récupération des données XP
    user_xp = xp_data.get(user_id_str, {"xp": 0, "level": 1})
    level = user_xp["level"]
    xp = user_xp["xp"]
    xp_to_next_level = level * 100 - xp

    # Générer l'image de la barre d'expérience
    xp_bar_image = generate_xp_bar(level, xp, xp_to_next_level)

    # Créer un embed
    embed = discord.Embed(
        title=f"Niveau et XP de {membre.display_name}",
        description=f"{membre.display_name} est au niveau **{level}** avec **{xp}**/{level * 100} XP!",
        color=discord.Color.blue()
    )
    embed.add_field(name="XP restante pour le prochain niveau", value=f"{xp_to_next_level} XP", inline=False)
    embed.set_image(url="attachment://xp_bar.png")
    embed.set_thumbnail(url=membre.avatar.url if membre.avatar else membre.default_avatar.url)

    # Envoyer l'embed avec l'image
    file = discord.File(xp_bar_image, filename='xp_bar.png')
    await interaction.response.send_message(embed=embed, file=file)
# Commande pour afficher le rang de l'utilisateur dans le serveur
@bot.tree.command(name="rang", description="Affiche le rang d'un utilisateur dans le serveur")
async def rang(interaction: discord.Interaction, membre: discord.Member = None):
    xp_data = load_xp_data()

    # Si aucun membre n'est spécifié, on prend l'auteur de la commande
    membre = membre or interaction.user
    user_id_str = str(membre.id)

    # Trier les utilisateurs par niveau puis par XP
    sorted_users = sorted(xp_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)

    # Trouver le rang du membre
    rank = next((i + 1 for i, (user_id, data) in enumerate(sorted_users) if user_id == user_id_str), None)

    if rank is not None:
        user_xp = xp_data[user_id_str]
        level = user_xp["level"]
        xp = user_xp["xp"]

        # Créer un embed pour afficher le rang
        embed = discord.Embed(
            title=f"🏅 Rang de {membre.display_name}",
            description=f"📊 **Classement :** #{rank} sur le serveur",
            color=discord.Color.gold()
        )
        embed.add_field(name="📈 Niveau", value=f"**{level}**", inline=True)
        embed.add_field(name="🔹 XP", value=f"**{xp}**", inline=True)
        embed.set_thumbnail(url=membre.avatar.url if membre.avatar else membre.default_avatar.url)

        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"{membre.display_name} n'a pas encore d'XP enregistrée.", ephemeral=True)


@bot.tree.command(name="classement", description="Affiche le classement des 10 plus gros chatteurs")
async def classement(interaction: discord.Interaction):
    xp_data = load_xp_data()
    user_id_str = str(interaction.user.id)

    # Trier les utilisateurs par niveau puis par XP
    sorted_users = sorted(xp_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)

    # Créer un embed stylisé
    embed = discord.Embed(
        title="🏆 Classement des Chatteurs 🏆",
        description="Les 10 plus gros chatteurs du serveur 📜",
        color=discord.Color.gold()
    )

    # Génération du texte du classement avec un formatage amélioré
    leaderboard_text = ""
    medal_emojis = ["🥇", "🥈", "🥉"]  # Émojis pour les 3 premiers

    top_users = []
    for i, (user_id, data) in enumerate(sorted_users[:10], start=1):
        member = interaction.guild.get_member(int(user_id))
        if member:
            top_users.append(user_id)
            emoji = medal_emojis[i - 1] if i <= 3 else "🔹"  # Médailles pour les 3 premiers, icône normale sinon
            leaderboard_text += f"{emoji} **#{i}** - `{member.display_name}` | Niveau **{data['level']}** | **{data['xp']} XP**\n"

    embed.add_field(name="📌 Classement actuel", value=leaderboard_text or "Aucun utilisateur dans le classement.", inline=False)

    # Vérifier si l'utilisateur est hors du top 10 et afficher son classement
    if user_id_str not in top_users:
        rank = next((i + 1 for i, (user_id, data) in enumerate(sorted_users) if user_id == user_id_str), None)
        if rank:
            user_data = xp_data[user_id_str]
            member = interaction.guild.get_member(int(user_id_str))
            if member:
                embed.add_field(
                    name="📍 Ton classement",
                    value=f"**#{rank}** - `**{member.display_name}` | Niveau **{user_data['level']}** | **{user_data['xp']} XP**",
                    inline=False
                )

    await interaction.response.send_message(embed=embed)


# Commande pour bannir quelqu'un (administrateurs uniquement)
@bot.tree.command(name="banguy", description="Pour bannir quelqu'un")
@commands.has_permissions(ban_members=True)
async def banguy(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message("Ban envoyé !")
    await member.ban()
    await member.send("Tu as été banni du serveur.")

# Commande pour TO quelqu'un (administrateurs uniquement)
@bot.tree.command(name="toguy", description="Pour TO quelqu'un")
@commands.has_permissions(moderate_members=True)
async def tonguy(interaction: discord.Interaction, member: discord.Member, duration: int):
    await interaction.response.send_message(f"TO envoyé pour {duration} minutes!")
    await member.timeout(timedelta(minutes=duration), reason="Timeout")


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    channel = guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title=f"Bienvenue {member.name} !",
            description="Bienvenue sur le serveur ! Pense à consulter les salons importants pour t'intégrer.",
            color=discord.Color.green()  # Fond vert pour l'embed
        )
        avatar_url = member.avatar.url if member.avatar else "https://c.clc2l.com/t/d/i/discord-4OXyS2.png"  # Image générique par défaut
        embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"{len(guild.members)}ème personne du serveur !")
        welcome_message = await channel.send(embed=embed)
        await welcome_message.add_reaction("👋")

@bot.event
async def on_member_remove(member: discord.Member):
    guild = member.guild
    channel = guild.get_channel(GOODBYE_CHANNEL_ID)
    if channel:
        time_in_server = utcnow() - member.joined_at if member.joined_at else "Inconnu"
        duration_text = f"{time_in_server.days} jours et {time_in_server.seconds // 3600} heures" if isinstance(time_in_server, timedelta) else "Durée inconnue"
        
        embed = discord.Embed(
            title=f"Au revoir {member.name}...",
            description=f"Nous espérons te revoir bientôt !\nTu étais sur le serveur depuis {duration_text}.",
            color=discord.Color.red()
        )
        avatar_url = member.avatar.url if member.avatar else "https://c.clc2l.com/t/d/i/discord-4OXyS2.png"  # Image générique par défaut
        embed.set_thumbnail(url=avatar_url)
        goodbye_message = await channel.send(embed=embed)
        await goodbye_message.add_reaction("😭")  # Utilisation de l'emoji :sob:






# ---- AVANT DERNIERE LIGNE !!!! ----
keep_alive()
# ---- DERNIERE LIGNE !!!!! ----
bot.run(os.getenv('DISCORD_TOKEN'))
