from auth import jwt_token, access_token, token, api_token, client_id
from apscheduler.schedulers.asyncio import AsyncIOScheduler
sched = AsyncIOScheduler()
sched.start()
from twitchio.ext import commands
import datetime
import threading
import requests
import asyncio
import aiohttp
import logging
import random
import json
import re

r = requests.get('https://api.twitch.tv/kraken/channel', headers =
{
    'Content-Type': 'application/vnd.twitchtv.v5+json',
    'Client-ID': client_id,
    'Authorization':access_token
})
channel_id = r.json()['_id']

logger = logging.getLogger('main')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('logs.log')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s]: %(message)s', '%Y-%m-%d %H:%M:%S')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)

async def add_points(channel, user, amount):
	with open('./channels.json') as channels_file:
		content = json.load(channels_file)
		token = content[channel]['token']
		channel = content[channel]['id']

	async def fetch(session, url):
		async with session.put(url,headers = {"Authorization":token}) as response:
			return await response.json()

	async def main():
		async with aiohttp.ClientSession() as session:
			r = await fetch(session, f'https://api.streamelements.com/kappa/v2/points/{channel}/{user}/{amount}')
			logger.info(r)

	await main()

class Trivia:
    def __init__(self, question, answer):
        self.question = question
        self.answer = answer
        self.answered = False

    def check_answer(self, answer):
        if answer.lower() in (correctanswer.lower() for correctanswer in self.answer):
            self.answered = True
            return True
        else:
            return False

class Botto(commands.Bot):
    def __init__(self):
        super().__init__(prefix=['!', '?'], irc_token=token, api_token=api_token, client_id=channel_id, nick='adure_bot', initial_channels=["thebigoce"])

    async def end_trivia(self):
        if trivia.answered == True:
            return
        trivia.answered = True
        channel = self.get_channel('thebigoce')
        await channel.send(f'You took too long! The correct answer was {trivia.answer[0]}. Other accepted answers: {", ".join(trivia.answer[1:])}')

    async def post_trivia(self):
        global trivia
        with open('videogame_trivia.json', 'r') as tquestions:
            content = json.load(tquestions)
            question = random.choice(content['QandAs'])

        trivia = Trivia(question['q'], question['a'])
        channel = self.get_channel('thebigoce')
        await channel.send(trivia.question)
        print(trivia.question, trivia.answer)

        now = datetime.datetime.now()
        run_at = now + datetime.timedelta(seconds=30)
        sched.add_job(self.end_trivia, 'date', run_date=run_at)

    async def event_ready(self):
        logger.info("Ready!")
        await self.post_trivia()
        sched.add_job(self.post_trivia, 'interval', minutes=5)

    async def event_message(self, message):
        print(f"{message.author.name}: {message.content}")

        if trivia.answered == True:
            return

        correct = trivia.check_answer(message.content)
        if correct == True:
            await message.channel.send(f'Correct, {message.author.name}! You won 500 Coins!')
            await add_points(message.channel.name, message.author.name, '500')

    async def event_error(self, error, data):
        logger.error(f"{error} - {ctx.channel.name}")


bot = Botto()
bot.run()