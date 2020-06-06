import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo
import random
import asyncio
import time
import private
import psutil
import platform
import os

bot = commands.Bot(command_prefix="u.", activity=discord.Game(name="Uno | u.help"))
mongo = AsyncIOMotorClient(private.mongo, retryWrites=False)
bot.db = mongo.unobot

@bot.event
async def on_ready():
	print("Bot is ready")
	bot.players = []

@bot.event
async def on_command_error(ctx, error):
	if isinstance(error, commands.errors.MissingRequiredArgument):
		if ctx.command.name == "startgame":
			await ctx.send("To use u.startgame, run u.startgame then mention all the players excluding yourself, but you will still be included in the game. For example: u.startgame @user2 @user3")
	else:
		print(f"Error occured: {error}")

@bot.command()
async def ping(ctx):
	await ctx.send("Pong!")

def makedeck():
	cards = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r+2", "rskip", "rrev", "g0", "g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "g+2", "gskip", "grev", "b0", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "b+2", "bskip", "brev", "y0", "y1", "y2", "y3", "y4", "y5", "y6", "y7", "y8", "y9", "y+2", "yskip", "yrev", "wild", "wild+4"]
	deck = []
	for x in cards:
		if "wild" in x:
			n = 4
			while n>0: n = n-1; deck.append(x)
		elif not x.endswith("0"):
			deck.append(x)
			deck.append(x)
	return deck

def decode(hand, color=False):
	new = []
	n = 1
	for card in hand:
		if card[0].lower() == "r":
			x = f"[{n}] Red {card[1:]}"
			if color:
				return discord.Color.red()
		elif card[0].lower() == "g":
			x = f"[{n}] Green {card[1:]}"
			if color:
				return discord.Color.green()
		elif card[0].lower() == "b":
			if color:
				return discord.Color.blue()
			x = f"[{n}] Blue {card[1:]}"
		elif card[0].lower() == "y":
			x = f"[{n}] Yellow {card[1:]}"
			if color:
				return discord.Color.gold()
		elif card == "wild":
			x = f"[{n}] Wild Card"
		else:
			x = f"[{n}] Wild Card +4"
		n+= 1
		if len(hand) != 1:
			new.append(x)
		else:
			new.append(x[3:])
	return "\n".join(new)


@bot.command(aliases=["start", "s"])
async def startgame(ctx, *, users):
	"Start a game of Uno by mentioning all the players but yourself"
	try:
		userslist = users.split()
		userslist.insert(0, ctx.author.mention)
		players = []
		deck = makedeck()
		await bot.db.games.insert_one({"_id": ctx.author.id})
		for user in userslist:
			if user.startswith("<@") and user.endswith(">"):
				id = int(user.lstrip("<@").lstrip("!").lstrip("&").strip(">"))
				if not bot.get_user(id).bot:
					if id not in bot.players:
						players.append(id)
						bot.players.append(id)
					else:
						await ctx.send(f"{user} is already in a game so they will not be added to the game. Please wait until they are done to add them to a game.")
				else:
					await ctx.send(f"{user} is a bot therefore they will not be added to the game.")
			else:
				await ctx.send(f"{user} is not a valid user so they will not be added to the game.")
		await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"players": players}})
		#dealing cards
		await ctx.send("Dealing the cards... check your DMs")
		first = random.choice(players)
		for x in players:
			hand = []
			n = 7
			while n>0:
				card = random.choice(deck)
				hand.append(card)
				deck.remove(card)
				n -= 1
			await bot.get_user(x).send(f"Here is your hand: {decode(hand)}")
			await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {f"{str(x)}.hand": hand}})
			await bot.get_user(x).send(f"The game is starting... {bot.get_user(first)} has the first turn. Pay attention to people's card counts so you can call uno on them.")
		while True:
			currentcard = random.choice(deck)
			if "wild" in currentcard:
				continue
			else:
				deck.remove(currentcard)
				break
		query = await bot.db.games.find_one({"_id": ctx.author.id})
		if query["players"].index(first) + 1 == len(query["players"]):
			nextplayer = 0
		else:
			nextplayer = query["players"].index(first) + 1
		nextplayer = bot.get_user(query["players"][nextplayer])
		for x in players:
			cardpic = discord.File(f"assets/{currentcard}.png", filename="image.png")
			embed = discord.Embed(color=decode([currentcard], color=True), title="Uno Game Info", description=f"{bot.get_user(first).name}'s turn\n{nextplayer.name}'s turn is next")
			embed.set_thumbnail(url="attachment://image.png")
			embed.add_field(name="Current Card", value=decode([currentcard]))
			embed.add_field(name="Your Hand", value=decode(query[str(x)]["hand"]))
			embed.add_field(name=f"{bot.get_user(first).name}'s Hand", value=f"{len(query[str(x)]['hand'])} cards", inline=False)
			embed.add_field(name="Rotation of play", value="Forward")
			msg = await bot.get_user(x).send(file=cardpic, embed=embed)
			await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"turn": str(first)}})
			await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {f"{str(x)}.msg": msg.id}})
		await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"currentcard": currentcard}})
		await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"rotation": "forward"}})
		await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"deck": deck}})
		await turn(ctx.author.id, first)
	except pymongo.errors.DuplicateKeyError:
		await ctx.send("You already have a game going. Would you like to delete it and start a new one? [Y/N]")
		try:
			msg = await bot.wait_for("message", check=lambda m: m.author == ctx.author and m.content.lower() in ["y", "n", "yes", "no"], timeout=10)
			if msg.content.lower() == "y" or msg.content.lower() == "yes":
				await asyncio.gather(deletegame(ctx))
				await startgame(ctx=ctx, users=users)
			else:
				await ctx.send("You cannot start a new game until you delete your current game. Please run u.startgame again or run u.deletegame to manually delete your game")
		except asyncio.TimeoutError:
			await ctx.send("You didn't answer the question so I did not delete your game. You can run u.startgame again or run u.deletegame to manually delete your game")


async def turn(id, player):
	try:
		data = await bot.db.games.find_one({"_id": id})
		if not data:
			return
		else:
			pass
		await bot.db.games.update_one({"_id": id}, {"$set": {"turn": str(player)}})
		player = bot.get_user(player)
		notif = await player.send("It is your turn! To play a card enter the number to the left of the card. To draw a card type 'draw', if you only have 2 cards left and you play one remember to type 'uno'")
		await bot.db.games.update_one({"_id": id}, {"$set": {"time": time.time()}})
		try:
			action = await bot.wait_for("message", check=lambda m: m.author.id == player.id and m.channel == player.dm_channel, timeout=60)
		except asyncio.TimeoutError:
			if player.id != id:
				await player.send("You are taking a long time to make a move. In 30 seconds the host will have the option to skip you.")
			else:
				action = await bot.wait_for("message", check=lambda m: m.author.id == player.id and m.channel == player.dm_channel)
			try:
				action = await bot.wait_for("message", check=lambda m: m.author.id == player.id and m.channel == player.dm_channel, timeout=30)
			except asyncio.TimeoutError:
				await bot.get_user(id).send(f"{player.name} is taking a long time to go. You can skip them with u.skip.")
				action = await bot.wait_for("message", check=lambda m: m.author.id == player.id and m.channel == player.dm_channel)
		if action.content.isdigit():
			card = data[str(player.id)]["hand"][int(action.content) - 1]
			if card[0] == data["currentcard"][0].lower() or card[1:] == data["currentcard"][1:]:
				await bot.db.games.update_one({"_id": id}, {"$set": {"currentcard": card}})
				hand = data[str(player.id)]["hand"]
				hand.remove(card)
				await bot.db.games.update_one({"_id": id}, {"$set": {f"{str(player.id)}.hand": hand}})
				if card[1:] == "skip":
					if data["players"].index(player.id) + 1 == len(data["players"]):
						skipped = 0
					else:
						skipped = data["players"].index(player.id) + 1
					skipped = data["players"][skipped]
					await notif.delete()
					await asyncio.gather(uno_check(id, player))
					await update_embeds(id, player, f"{player.name} played a {decode([card])} on {bot.get_user(skipped).name}", skip=True)
				elif card[1:] == "rev":
					if data["rotation"] == "forward":
						await bot.db.games.update_one({"_id": id}, {"$set": {"rotation": "reverse"}})
						move = f"{player.name} played a {decode([card])} and changed the rotation to reverse"
					else:
						await bot.db.games.update_one({"_id": id}, {"$set": {"rotation": "forward"}})
						move = f"{player.name} played a {decode([card])} and changed the rotation to forward"
						await notif.delete()
					await asyncio.gather(uno_check(id, player))
					await update_embeds(id, player, move)
				elif card[1:] == "+2":
					if data["players"].index(player.id) + 1 == len(data["players"]):
						victim = 0
					else:
						victim = data["players"].index(player.id) + 1
					victim = data["players"][victim]
					await draw(id, victim, 2)
					await notif.delete()
					await asyncio.gather(uno_check(id, player))
					await update_embeds(id, player, f"{player.name} played a {decode([card])} on {bot.get_user(victim).name}", skip=True)
				else:
					move = f"{player.name} played a {decode([card])}"
					await notif.delete()
					await asyncio.gather(uno_check(id, player))
					await update_embeds(id, player, move)
			elif "wild" in card:
				await player.send("You played a wild. Please type one of the four colors to change to.")
				choice = await bot.wait_for("message", check=lambda m: m.author.id == player.id and m.content.lower() in ["blue", "red", "green", "yellow"] and m.channel == player.dm_channel)
				if "wild+4" in card:
					colors = {"blue": "Blue Wild +4", "red": "Red Wild +4", "yellow": "Yellow Wild +4", "green": "Green Wild +4"}
				else:
					colors = {"blue": "Blue Wild", "red": "Red Wild", "yellow": "Yellow Wild", "green": "Green Wild"}
				hand = data[str(player.id)]["hand"]
				hand.remove(card)
				await bot.db.games.update_one({"_id": id}, {"$set": {f"{str(player.id)}.hand": hand}})
				await bot.db.games.update_one({"_id": id}, {"$set": {"currentcard": colors[choice.content.lower()]}})
				if card == "wild+4":
					if data["players"].index(player.id) + 1 == len(data["players"]):
						victim = 0
					else:
						victim = data["players"].index(player.id) + 1
					victim = data["players"][victim]
					await draw(id, victim, 4)
					await asyncio.gather(uno_check(id, player))
					await update_embeds(id, player, f"{player.name} used a wild +4 on {bot.get_user(victim).name} and changed the color to {choice.content.lower()}", skip=True)
				else:
					await asyncio.gather(uno_check(id, player))
					await update_embeds(id, player, f"{player.name} used a wild and changed the color to {choice.content.lower()}")
			else:
				await player.send("The card you play must match the current card in either color or numeric value. Please try again.")
				await notif.delete()
				await turn(id, player.id)
		elif action.content.lower() == "draw":
			await draw(id, player.id)
			await notif.delete()
			await update_embeds(id, player, f"{player.name} drew a card.")
		else:
			await player.send("Invalid move! Please try again.")
			await notif.delete()
			await turn(id, player.id)
	except KeyError:
		return

async def draw(id, player, num=1):
	data = await bot.db.games.find_one({"_id": id})
	deck = data["deck"]
	while num>0:
		if len(deck) == 0:
			deck = makedeck()
		card = random.choice(deck)
		deck.remove(card)
		hand = data[str(player)]["hand"]
		hand.append(card)
		num -= 1
	await bot.db.games.update_one({"_id": id}, {"$set": {"deck": deck}})
	await bot.db.games.update_one({"_id": id}, {"$set": {f"{str(player)}.hand": hand}})

async def uno_check(id, player):
	data = await bot.db.games.find_one({"_id": id})
	if len(data[str(player.id)]["hand"]) == 1:
		try:
			uno = await bot.wait_for("message", check=lambda m: m.author.id != 714954865947705426 and m.content.lower() == "uno", timeout=15)
			if uno.author.id != player.id:
				await draw(id, player.id, 2)
				for x in data["players"]:
					await bot.get_user(x).send(f"{player.name} forgot to say Uno. They will be given 2 more cards")
			else:
				for x in data["players"]:
					await bot.get_user(x).send(f"{player.name} said Uno before anybody else so they gain no penalty")
		except asyncio.TimeoutError:
			for x in data["players"]:
				await bot.get_user(x).send(f"Everyone waited too long to call uno on {player.name} so they got away with it. Pay attention next time")

async def update_embeds(id, play, action, next=True, skip=False):
	data = await bot.db.games.find_one({"_id": id})
	if len(data[str(play.id)]["hand"]) ==  0:
		for player in data["players"]:
			await bot.get_user(player).send(f"{play.name} played their last card and won the game! Game over... deleting your game now")
			for player in data["players"]:
				if player in bot.players:
					bot.players.remove(player)
			await bot.db.games.delete_one({"_id": ctx.author.id})
	else:
		for player in data["players"]:
			player = bot.get_user(int(player))
			await player.trigger_typing()
			if next==True:
				if not skip:
					if data["players"].index(play.id) + 1 == len(data["players"]):
						currentplayer = 0
					else:
						currentplayer = data["players"].index(play.id) + 1
				else:
					if len(data["players"]) > 2:
						if data["players"].index(play.id) + 2 > len(data["players"]):
								currentplayer = 1
						elif data["players"].index(play.id) + 2 == len(data["players"]):
								currentplayer = 0
						else:
							currentplayer = data["players"].index(play.id) + 2
					else:
						currentplayer = data["players"].index(play.id)
			else:
				currentplayer = data["players"].index(play.id)
			if data["rotation"] == "forward":
				if len(data["players"]) - 1 == currentplayer:
					nextplayer=0
				else:
					nextplayer = currentplayer + 1
			else:
				if currentplayer == 0:
					nextplayer = len(data["players"]) - 1
				else:
					nextplayer = currentplayer - 1
			if "Wild" in data["currentcard"]:
				if "Wild +4" in data["currentcard"]:
					cardpic = discord.File(f"assets/wild+4.png", filename="image.png")
				else:
					cardpic = discord.File(f"assets/wild.png", filename="image.png")
				currentcard = data["currentcard"]
			else:
				cardpic = discord.File(f"assets/{data['currentcard']}.png", filename="image.png")
				currentcard = decode([data["currentcard"]])
			currentplayer = bot.get_user(data['players'][currentplayer])
			nextplayer = bot.get_user(data["players"][nextplayer])
			embed = discord.Embed(title="Uno Game Info", description=f"{action}\n{currentplayer.name}'s turn\n{nextplayer.name}'s turn is next", color=decode([data["currentcard"]], color=True))
			embed.set_thumbnail(url="attachment://image.png")
			embed.add_field(name="Current Card", value=currentcard)
			embed.add_field(name="Your Hand", value=decode(data[str(player.id)]["hand"]))
			embed.add_field(name=f"{currentplayer.name}'s Hand", value=f"{len(data[str(currentplayer.id)]['hand'])} cards", inline=False)
			embed.add_field(name="Rotation of play", value=data["rotation"])
			msg = await player.fetch_message(int(data[str(player.id)]["msg"]))
			await msg.delete()
			await asyncio.sleep(1.5)
			msg = await player.send(file=cardpic, embed=embed)
			await bot.db.games.update_one({"_id": id}, {"$set": {f"{str(player.id)}.msg": msg.id}})
		if next==True:
			await turn(id, currentplayer.id)

@bot.command()
async def skip(ctx):
	"Skip the current player's turn if they take too long"
	data = await bot.db.games.find_one({"_id": ctx.author.id})
	if data:
		timer = time.time() - data["time"]
		if timer >= 90:
			player = bot.get_user(int(data["turn"]))
			if len(data["players"]) > 2:
				await update_embeds(ctx.author.id, player, f"The host skipped {player.name} for taking too long", skip=True)
			else:
				await update_embeds(ctx.author.id, ctx.author, f"The host skipped {player.name} for taking too long", skip=True)
		else:
			await ctx.send(f"You must wait {round(90 - timer)} more seconds until you can skip the current player")
	else:
		await ctx.send("You must be the host of a game to skip the current player.")


@bot.command()
async def deletegame(ctx):
	"Delete your current Uno game"
	data = await bot.db.games.find_one({"_id": ctx.author.id})
	try:
		for player in data["players"]:
			await bot.get_user(player).send(f"{ctx.author.name} deleted the game you're currently in. You can now participate in a new game.")
			if player in bot.players:
				bot.players.remove(player)
	except KeyError:
		pass
	await bot.db.games.delete_one({"_id": ctx.author.id})
	await ctx.send("Your UNO game was deleted")

@bot.command()
@commands.is_owner()
async def kill(ctx):
	"Forcefully kill the bot"
	await ctx.send("Killing the bot...")
	print("Bot was killed.")
	await bot.close()

@bot.command(aliases=["stats"])
async def info(ctx):
	"Get info about the bot"
	process = psutil.Process(os.getpid())
	memory = f"{process.memory_info()[0] / 1024 / 1024:.2f} MB"
	RAM = psutil.virtual_memory()
	used = RAM.used >> 20
	percent = RAM.percent
	CPU  = psutil.cpu_percent()
	embed = discord.Embed(title="Uno Bot Info", color=discord.Color.red(), timestamp=ctx.message.created_at)
	embed.set_thumbnail(url=bot.user.avatar_url)
	embed.add_field(name="Author", value="-= shadeyg56 =-#8670", inline=False)
	embed.add_field(name="Servers", value=len(bot.guilds), inline=False)
	embed.add_field(name="Active games", value=await bot.db.games.count_documents({}))
	embed.add_field(name='OS', value=platform.system(), inline=False)
		embed.add_field(name="Memory", value=f'**Process Memory:** {memory}\n**Total Memory:** {percent}% ({used}MB)', inline=False)
	embed.add_field(name="CPU", value=f"{CPU}%")
	embed.add_field(name='GitHub', value='[GitHub Repo](https://github.com/shadeyg56/DiscordUnoBot)', inline=False)
	embed.set_footer(text=f'Powered by discord.py v{discord.__version__}')
	await ctx.send(embed=embed)

@bot.command()
async def invite(ctx):
	"Invite the bot to your server"
	await ctx.send("https://discord.com/api/oauth2/authorize?client_id=714954865947705426&permissions=2048&scope=bot")





bot.load_extension("eval")
bot.run(private.token)
