import os
import discord
from dotenv import load_dotenv
from discord.ext import commands, tasks
import pyrebase
import random
import requests
from collections import defaultdict
import json
import time
random.seed()
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
APIKEY = os.getenv('APIKEY')
PATHTOSERVICEACCOUNT = os.getenv('PATHTOSERVICEACCOUNT')
FIREBASEUSER = os.getenv('FIREBASEUSER')
FIREBASEPASS = os.getenv('FIREBASEPASS')

config = {
	'apiKey':APIKEY,
	'authDomain':"lockoutbot-ca541.firebaseapp.com",
	'databaseURL':"https://lockoutbot-ca541-default-rtdb.firebaseio.com",
	'storageBucket':"lockoutbot-ca541.appspot.com",
	'serviceAccount': PATHTOSERVICEACCOUNT
}
firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
user = auth.sign_in_with_email_and_password(FIREBASEUSER, FIREBASEPASS)
db = firebase.database()
bot = commands.Bot(command_prefix='!')
intents = discord.Intents.none()
intents.reactions = True
intents.members = True
intents.guilds = True
"""
the different settings:
game type
	duel - one v one
	free for all - many all locking each other out
	classical - normal contest
duration
	number in minutes

decay
	on or off
decay interval
	how often the decay happens
decay amount
	how much is decayed per time

scoring
	questions or points
point start
	a number, how many points the first question is
point interval
	how many each question up is increasing by

difficulty range
	lower
	upper

number of problems
	number

"""


@bot.event
async def on_ready():
	print(f'{bot.user.name} has connected to Discord!')

@bot.command(name='list')
async def bot_help(ctx):
	toPrint =\
	"""
	set [type|decay|decayInterval|decayAmount|scoring|pointStart|pointInterval|difficulty|numQuestions|duration]
		followed by an appropriate option:
		type: duel|ffa|classic
		decay: on|off
		decayInterval: an int
		decayAmount: an int
		scoring: points|questions
		pointStart: an int
		pointInterval: an int
		difficulty: two ints, a lower bound(inclusive) and an upper bound(inclusive)
		numQuestions: an int
		duration: an int(number of minutes)
	leave gameIdNumber
		leaves a game
	join gameIdNumber
		joins a game
	createGame
		creates a game with your configurations
	register codeforcesUserName
		adds you to the database so you can play!!
	config
		prints your current game configurations
	startGame
		starts your owned game
	"""
	await ctx.send(toPrint)

@bot.command(name='set')
async def change_rules(ctx, *args):
	temp = list(args)
	if len(temp) <= 1:
		return
	userVal = db.child("users").child(ctx.message.author.id).child("key").get().val()
	if temp[0] == 'type':
		if temp[1] not in ['duel', 'ffa', 'classic']:
			return
		db.child("config").child(userVal).child("type").set(temp[1])
	elif temp[0] == 'decay':
		if temp[1] not in ['on', 'off']:
			return
		db.child("config").child(userVal).child("decay").set(temp[1])
		if temp[1] == 'on':
			db.child("config").child(userVal).child("decayInterval").set("1")
			db.child("config").child(userVal).child("decayAmount").set("8")
		else:
			db.child("config").child(userVal).child("decayInterval").set("-")
			db.child("config").child(userVal).child("decayAmount").set("-")
	elif temp[0] == 'decayInterval':
		try:
			a = int(temp[1])
			db.child("config").child(userVal).child("decayInterval").set(str(a))
		except:
			pass
	elif temp[0] == 'decayAmount':
		try:
			a = int(temp[1])
			db.child("config").child(userVal).child("decayAmount").set(str(a))
		except:
			pass
	elif temp[0] == 'scoring':
		if temp[1] not in ['points', 'questions']:
			return
		db.child("config").child(userVal).child("scoring").set(temp[1])
	elif temp[0] == 'pointStart':
		try:
			a = int(temp[1])
			db.child("config").child(userVal).child("pointStart").set(str(a))
		except:
			pass
	elif temp[0] == "pointInterval":
		try:
			a = int(temp[1])
			db.child("config").child(userVal).child("pointInterval").set(str(a))
		except:
			pass
	elif temp[0] == 'difficulty':
		if(len(temp) <= 2):
			return
		try:
			a = int(temp[1])
			b = int(temp[2])
			a = (a//100)*100
			b = (b//100)*100
			if(a > b) or a < 800 or b > 3500:
				return
			db.child("config").child(userVal).child("difficultyLower").set(str(a))
			db.child("config").child(userVal).child("difficultyUpper").set(str(a))
		except:
			pass
	elif temp[0] == 'numQuestions':
		try:
			a = int(temp[1])
			db.child("config").child(userVal).child("numberQuestions").set(str(a))
		except:
			pass
	elif temp[0] == 'duration':
		try:
			a = int(temp[1])
			db.child("config").child(userVal).child("duration").set(str(a))
		except:
			pass
	else:
		return

@bot.command(name='config')
async def pri(ctx):
	userVal = db.child("users").child(ctx.message.author.id).child("key").get().val()
	vals = ['type', 'duration', 'decay', 'decayInterval', 'decayAmount', 'scoring', 'pointStart', 'pointInterval', 'difficultyLower', 'difficultyUpper', 'numberQuestions']
	toPrint = ['Type: ', 'Duration of Contest(minutes): ', 'Decay: ', 'Decay Interval: ', 'Decay Amount: ', 'Scoring: ', 'Point Start: ', 'Point Interval: ', 'Difficulty Lower Bound: ', 'Difficulty Upper Bound: ', 'Number Of Questions: ']
	toSend = [toPrint[i] + db.child("config").child(userVal).child(vals[i]).get().val() for i in range(len(vals))]
	await ctx.send('\n'.join(toSend))

def getPast5Submissions(codeforcesuser):
	r = requests.get(f'https://codeforces.com/api/user.status?handle={codeforcesuser}&from=1&count=5')
	a = json.loads(r.text)
	a = a['result']
	ret = []
	for sub in a:
		if sub['verdict'] == 'OK':
			ret.append(str(sub['problem']['contestId'])+':'+sub['problem']['index'])
	return ret

@bot.command(name='flush')
async def flush(ctx):
	await checkscore()

@tasks.loop(minutes=1)
async def checkscore():
	print("running checkscore")
	games = db.child("games").get()
	if games==None or games.each() == None:
		return
	current_time = time.time()
	for game in games.each():
		gamekey = game.key()
		game = game.val()
		changed = False
		link_start = "https://codeforces.com/problemset/problem/"
		if game['started'] == 'false':
			continue
		ctx = bot.get_channel(int(game['channel']))
		if current_time - float(game['startTime']) >= 60*int(game['duration']):
			a = await game_ender(gamekey)
			for item in a:
				await ctx.send(str(item[0]) + ": " + str(item[1]))
			continue
		key = db.child("users").child(game['owner']).child('key').get().val()
		configs = db.child("config").child(key).get().val()
		for participant, score in game['participants'].items():
			name = db.child("users").child(participant).child("codeforces").get().val()
			passed = set(getPast5Submissions(name))
			toAdd = 0
			if configs['type'] == 'classic':
				if configs['scoring'] == 'questions':
					for prob in passed:
						if prob in game['problems']:
							if 'solved' not in game or prob not in game['solved'] or participant not in games['solved'][prob]:
								toAdd += 1
								db.child("games").child(gamekey).child("solved").child(prob).child(participant).set('1')
				else:
					for prob in passed:
						if prob in game['problems']:
							if 'solved' not in game or prob not in game['solved'] or participant not in game['solved'][prob]:
								if configs['decay'] == 'off':
									for num, probname in game['problems'].items():
										if probname == prob:
											toAdd += (int(num)-1) * int(configs['pointInterval']) + int(configs['pointStart'])
											break
								else:
									for num, probname in game['problems'].items():
										if probname == prob:
											toAdd += min((int(num)) * int(configs['pointInterval']) + int(configs['pointStart']) - int(configs['decayAmount'])*((current_time - float(game['startTime']))//60//int(configs['decayInterval'])), int(configs['pointStart']))
											break
								db.child("games").child(gamekey).child("solved").child(prob).child(participant).set('1')
			elif configs['type'] == 'duel':
				if configs['scoring'] == 'questions':
					for prob in passed:
						if prob in game['problems']:
							if 'solved' not in game or prob not in game['solved']:
								toAdd += 1
								db.child("games").child(gamekey).child("solved").child(prob).set('1')
								prob = prob.replace(":", "/")
								async for x in ctx.history(limit=100):
								    if x.content == link_start+prob:
								        await x.delete()
								        break
				else:
					for prob in passed:
						if prob in game['problems']:
							if 'solved' not in game or prob not in game['solved']:
								if configs['decay'] == 'off':
									for num, probname in game['problems'].items():
										if probname == prob:
											toAdd += (int(num)-1) * int(configs['pointInterval']) + int(configs['pointStart'])
											break
								else:
									for num, probname in game['problems'].items():
										if probname == prob:
											toAdd += min((int(num)) * int(configs['pointInterval']) + int(configs['pointStart']) - int(configs['decayAmount'])*((current_time - float(game['startTime']))//60//int(configs['decayInterval'])), int(configs['pointStart']))
											break
								db.child("games").child(gamekey).child("solved").child(prob).set('1')
								prob = prob.replace(":", "/")
								async for x in ctx.history(limit=100):
								    if x.content == link_start+prob:
								        await x.delete()
								        break
			else:
				if configs['scoring'] == 'questions':
					for prob in passed:
						if prob in game['problems']:
							if 'solved' not in game or prob not in game['solved']:
								toAdd += 1
								db.child("games").child(gamekey).child("solved").child(prob).set('1')
								prob = prob.replace(":", "/")
								async for x in ctx.history(limit=100):
								    if x.content == link_start+prob:
								        await x.delete()
								        break
				else:
					for prob in passed:
						if prob in game['problems']:
							if 'solved' not in game or prob not in game['solved']:
								if configs['decay'] == 'off':
									for num, probname in game['problems'].items():
										if probname == prob:
											toAdd += (int(num)-1) * int(configs['pointInterval']) + int(configs['pointStart'])
											break
								else:
									for num, probname in game['problems'].items():
										if probname == prob:
											toAdd += min((int(num)) * int(configs['pointInterval']) + int(configs['pointStart']) - int(configs['decayAmount'])*((current_time - float(game['startTime']))//60//int(configs['decayInterval'])), int(configs['pointStart']))
											break
								db.child("games").child(gamekey).child("solved").child(prob).set('1')
								prob = prob.replace(":", "/")
								async for x in ctx.history(limit=100):
								    if x.content == link_start+prob:
								        await x.delete()
								        break
			if toAdd != 0:
				changed = True
			db.child("games").child(gamekey).child("participants").child(participant).set(str(int(score)+toAdd))
		if changed:
			async for x in ctx.history(limit=100):
				if 'game ' + str(gamekey) + ' scores:' in x.content:
				    await x.delete()
				    break
			newScores = db.child("games").child(gamekey).child("participants").get().val()
			toPrint = ['game ' +str(gamekey)+' scores:']
			for part, sco in newScores.items():
				name = db.child("users").child(part).child("codeforces").get().val()
				toPrint.append(name+": " + sco)
			strPrint = '\n'.join(toPrint)
			await ctx.send('```'+strPrint+'```')

async def game_ender(gameId):
	participants = db.child("games").child(gameId).child("participants").get()
	toPrint = []
	for person in participants.each():
		name = db.child("users").child(person.key()).child("codeforces").get().val()
		toPrint.append((name, person.val()))
	toPrint.sort(key = lambda x: x[1])
	db.child("games").child(gameId).remove()
	return toPrint

@bot.command(name="endGame")
async def end_game(ctx):
	gameId = db.child("users").child(str(ctx.message.author.id)).child("game").get().val()
	a = await game_ender(gameId)
	for item in a:
		await ctx.send(str(item[0]) + ": " + str(item[1]))

@bot.command(name='startGame')
async def start_duel(ctx, *args):
	current_time = time.time()
	gameId = db.child("users").child(str(ctx.message.author.id)).child("game").get().val()
	if db.child("games").child(str(gameId)).get().val() == None:
		return
	await ctx.send(f'getting game data')
	db.child("games").child(str(gameId)).child("started").set("true")
	db.child("games").child(str(gameId)).child("channel").set(str(ctx.channel.id))
	db.child("games").child(str(gameId)).child("startTime").set(str(current_time))
	key = db.child("users").child(str(ctx.message.author.id)).child('key').get().val()
	configs = db.child("config").child(key).get().val()
	lower = int(configs['difficultyLower'])
	upper = int(configs['difficultyUpper'])
	n = int(configs['numberQuestions'])
	dura = int(configs['duration'])
	db.child("games").child(str(gameId)).child("duration").set(str(dura))
	await ctx.send(f'generating random question list')
	if lower == upper:
		temp_question_list = list(db.child("problems").child(str(lower)).get().val().keys())
		already = set()
		counter = 0
		for i in range(n):
			a = random.randint(1, len(temp_question_list))
			while a in already:
				a = random.randint(1, len(temp_question_list))
			already.add(a)
			db.child("games").child(str(gameId)).child("problems").child(str(counter)).set(temp_question_list[a-1])
			counter += 1
	else:
		level_range = []
		while lower <= upper:
			level_range.append(lower)
			lower += 100
		question_diff = defaultdict(int)
		for i in range(n):
			a = random.randint(0, len(level_range)-1)
			question_diff[level_range[a]] += 1
		counter = 0
		for dif, amount in sorted(question_diff.items()):
			already = set()
			temp_question_list = list(db.child("problems").child(str(dif)).get().val().keys())
			for i in range(amount):
				a = random.randint(1, len(temp_question_list))
				while a in already:
					a = random.randint(1, len(temp_question_list))
				already.add(a)
				db.child("games").child(str(gameId)).child("problems").child(str(counter)).set(temp_question_list[a-1])
				counter += 1
	qs = db.child("games").child(str(gameId)).child("problems").get()
	link_start = "https://codeforces.com/problemset/problem/"
	for q in qs.each():
		if q.val() == None:
			continue
		q = q.val()
		q = q.replace(':','/')
		await ctx.send(link_start+q)
	newScores = db.child("games").child(str(gameId)).child("participants").get().val()
	toPrint = ['game '+str(gameId)+' scores:']
	print(newScores)
	for part, sco in newScores.items():
		name = db.child("users").child(part).child("codeforces").get().val()
		toPrint.append(name+": " + sco)
	strPrint = '\n'.join(toPrint)
	await ctx.send('```'+strPrint+'```')

def syncer(ctx, a):
	db.child("gameNum").set(a+1)
	db.child("games").child(str(a)).child("owner").set(str(ctx.message.author.id))
	db.child("games").child(str(a)).child("num").set("1")
	db.child("games").child(str(a)).child("started").set("false")
	db.child("games").child(str(a)).child("participants").child(str(ctx.message.author.id)).set('0')
	b = db.child("users").child(ctx.message.author.id).child("game").get().val()
	db.child("games").child(b).remove()
	db.child("users").child(ctx.message.author.id).child("game").set(str(a))
@bot.command(name='createGame')
async def create_game(ctx):
	a = int(db.child("gameNum").get().val())
	syncer(ctx, a)
	await ctx.send(f'created game with id: {a}')

@bot.command(name="leave")
async def leave_game(ctx, *args):
	idNum = args[0]
	status = db.child("games").child(idNum).child("started").get().val()
	if status == 'true':
		return
	if db.child("games").child(idNum).child("participants").child(str(ctx.message.author.id)).get().val() == None:
		return
	number = str(int(db.child("games").child(str(idNum)).child("num").get().val())-1)
	if(number == '0'):
		db.child("games").child(idNum).remove()
		return
	val = db.child("games").child(idNum).child("participants").child(str(ctx.message.author.id)).remove()
	db.child("games").child(str(idNum)).child("num").set(number)
	await ctx.send(f'removed from game {idNum}')

@bot.command(name='join')
async def join_game(ctx, *args):
	idNum = args[0]
	status = db.child("games").child(idNum).child("started").get().val()
	if status == 'true':
		return
	check = db.child("games").child(idNum).child("participants").child(str(ctx.message.author.id)).get().val()
	if check != None:
		return
	number = str(int(db.child("games").child(str(idNum)).child("num").get().val())+1)
	owner = db.child("games").child(str(idNum)).child("owner").get().val()
	ownerKey = db.child("users").child(owner).child('key').get().val()
	typeGame = db.child("config").child(ownerKey).child("type").get().val()
	if typeGame == 'duel' and number == '3':
		return
	db.child("games").child(str(idNum)).child("participants").child(str(ctx.message.author.id)).set('0')
	db.child("games").child(str(idNum)).child("num").set(number)
	await ctx.send(f'{ctx.message.author} joined game with id {idNum}')

@bot.command(name='register')
async def register(ctx, codeforces):
	a = codeforces+str(ctx.message.author.id)
	db.child("users").child(ctx.message.author.id).child("key").set(a)
	db.child("users").child(ctx.message.author.id).child("codeforces").set(codeforces)
	db.child("config").child(a).child("type").set("duel")
	db.child("config").child(a).child("decay").set("off")
	db.child("config").child(a).child("decayInterval").set("-")
	db.child("config").child(a).child("decayAmount").set("-")
	db.child("config").child(a).child("scoring").set("questions")
	db.child("config").child(a).child("pointStart").set("-")
	db.child("config").child(a).child("pointInterval").set("-")
	db.child("config").child(a).child("difficultyLower").set("800")
	db.child("config").child(a).child("difficultyUpper").set("3500")
	db.child("config").child(a).child("numberQuestions").set("5")
	db.child("config").child(a).child("duration").set("90")
	db.child("users").child(ctx.message.author.id).child("game").set(0)
	await ctx.send(f'{ctx.message.author} added to the database\n')

@bot.command(name="scrape")
async def scrapte(ctx, password):
	if password != 'acm':
		return
	r = requests.get("https://codeforces.com/api/problemset.problems")
	if r.status_code != 200:
		await ctx.send(f'failed to update problem list\n')
		return
	await ctx.send(f'starting to parse')
	problems = json.loads(r.text)
	problems = problems['result']['problems']
	counts = defaultdict(int)
	names = defaultdict(list)
	for problem in problems:
		if 'rating' not in problem or 'index' not in problem or 'contestId' not in problem:
			continue
		counts[problem['rating']] += 1
		names[problem['rating']].append(str(problem['contestId']) + ':' + problem['index'])
	await ctx.send(f'finished parsing, updating database')
	for rating, count in counts.items():
		db.child("problemNums").child(str(rating)).set(str(count))
	for rating, probs in names.items():
		for prob in probs:
			val = db.child("problems").child(str(rating)).child(str(prob)).get().val()
			if val == None:
				db.child("problems").child(str(rating)).child(str(prob)).set('a')
	await ctx.send(f'updated problems')
checkscore.start()
bot.run(TOKEN)