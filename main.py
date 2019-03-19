from auth import jwt_token, access_token, token, api_token, client_id
from twitchio.ext import commands

from apscheduler.schedulers.asyncio import AsyncIOScheduler
sched = AsyncIOScheduler()
sched.start()
import threading
import requests
import asyncio
import aiohttp
import logging
import random
import json
import re

import datetime as _datetime
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import locale
locale.setlocale(locale.LC_ALL, 'en_AU.UTF8')

r = requests.get('https://api.twitch.tv/kraken/channel', headers =
{
    'Content-Type': 'application/vnd.twitchtv.v5+json',
    'Client-ID': client_id,
    'Authorization':access_token
})
channel_id = r.json()['_id']

with open('./channels.json', 'r+') as channels_file:
	channels = json.load(channels_file)
	channels = channels['channels']

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

coinreward = '500'

async def parse_datetime(dt):
    compiled = re.compile("""(?:(?P<hours>[0-9]{1,5})(?:hours?|h))?
                             (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?
                             (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?
                          """, re.VERBOSE)

    match = compiled.fullmatch(dt)
    if match is None or not match.group(0):
        return None

    data = { k: int(v) for k, v in match.groupdict(default=0).items() }
    return data

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
        self.triviajob = None
        self.trivia = None
        super().__init__(prefix=['!', '?'], irc_token=token, api_token=api_token, client_id=channel_id, nick='adure_bot', initial_channels=channels)

    async def end_trivia(self, message):
        if self.trivia.answered == True:
            return
        self.trivia.answered = True
        channel = message.channel
        await channel.send(f'/me You took too long! The correct answer was {self.trivia.answer[0]}. Other accepted answers: {", ".join(self.trivia.answer[1:])}')

    async def post_trivia(self, message):
        with open('videogame_trivia.json', 'r') as tquestions:
            content = json.load(tquestions)
            question = random.choice(content['QandAs'])

        self.trivia = Trivia(question['q'], question['a'])
        channel = message.channel
        await channel.send('/me '+self.trivia.question)
        print(self.trivia.question, self.trivia.answer)

        now = datetime.now()
        run_at = now + timedelta(seconds=30)
        end = self.end_trivia
        sched.add_job(end, 'date', [message], run_date=run_at)

    async def event_ready(self):
        logger.info("Ready!")

    async def event_message(self, message):
        print(f"{message.author.name}: {message.content}")
        await self.handle_commands(message)

        if self.trivia.answered == True:
            return

        correct = self.trivia.check_answer(message.content)
        if correct == True:
            await message.channel.send(f'/me Correct, {message.author.name}! You won {coinreward} Coins!')
            await add_points(message.channel.name, message.author.name, coinreward)

            channel = message.channel.name
            username = message.author.name
            coinswon = coinreward

            with open('trivia_leaderboard.json', 'r+') as leaderboard_file:
                try:
                    contents = json.load(leaderboard_file)

                    # add user entry to leaderboard if it does not exist already
                    if not any(u['userName'] == username for u in contents['users']):
                        out = {
                            'userName': username,
                            'correctAnswers': 1,
                            'coinsWon': int(coinswon)
                        }
                        contents['users'].append(out)

                        leaderboard_file.seek(0)
                        json.dump(contents, leaderboard_file, indent=4, sort_keys=True)
                        leaderboard_file.truncate()

                        logger.info(f'Added {username} to leaderboard')
                        return

                    # update user entry
                    for entry in contents['users']:
                        if entry['userName'] == username:
                            entry['correctAnswers'] += 1
                            entry['coinsWon'] += int(coinswon)

                            leaderboard_file.seek(0)
                            json.dump(contents, leaderboard_file, indent=4, sort_keys=True)
                            leaderboard_file.truncate()

                            logger.info(f"Updated {username} in leaderboard with a total of {entry['correctAnswers']} correct answers")

                except json.decoder.JSONDecodeError:
                    logger.error('Error reading trivia leaderboard. Initialising file...')
                    out = {'users': []}
                    json.dump(out, leaderboard_file, indent=4, sort_keys=True, separators=(',', ': '))

    @commands.command(aliases=['triviatimer'])
    async def triviatimer_command(self, message, amount):
        if message.message.tags['mod'] == 1 or any(message.author.name in s for s in channels):
            dt = await parse_datetime(amount)
            if dt == None:
                print('error resolving interval time')
                await ctx.send('error resolving interval time')
                return

            post = self.post_trivia
            self.triviajob.remove()
            self.triviajob = sched.add_job(post, 'interval', [message], seconds=dt['seconds'], minutes=dt['minutes'], hours=dt['hours'], replace_existing=True)
            now = datetime.now(_datetime.timezone(timedelta(hours=11)))
            dt = now + relativedelta(**dt)
            await message.channel.send(f"Success! Trivia will run next at {dt.strftime('%X %Z')}")

    @commands.command(aliases=['triviaon'])
    async def triviaon_command(self, message):
        if message.message.tags['mod'] == 1 or any(message.author.name in s for s in channels):
            await message.channel.send("Trivia on!")
            await self.post_trivia(message)
            self.triviajob = sched.add_job(lambda: self.post_trivia(message), 'interval', minutes=5, replace_existing=True)

    @commands.command(aliases=['triviaoff'])
    async def triviaoff_command(self, message):
        if message.message.tags['mod'] == 1 or any(message.author.name in s for s in channels):
            self.triviajob.remove()
            await message.channel.send("Trivia off!")

    async def event_error(self, error, data):
        logger.error(f"{error} - {ctx.channel.name}")


bot = Botto()
bot.run()