from telethon import TelegramClient, events
import logging
from datetime import datetime, timedelta
import requests
import re
import os
from dotenv import load_dotenv
logging.basicConfig(level=logging.ERROR)
load_dotenv()

# Get your own values from https://my.telegram.org
API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')

# Visit https://shocklink.net/#/dashboard/tokens
# Make a new token and copy the API key 
SHOCK_API = os.environ.get('SHOCK_API')

# Visit https://shocklink.net/#/dashboard/shockers/own
# Click on 'Edit' and copy the ID
SHOCK_ID = os.environ.get('SHOCK_ID')

# Check if stuff is set
if None in [API_ID,API_HASH,SHOCK_API,SHOCK_ID]:
    print('ERROR: A required environment variable hasn\'t been set! Check the README!')
    exit()

# Create a Telegram client
client = TelegramClient('anon', API_ID, API_HASH)

# User preferences
VIBE_STR_MIN = int(os.environ.get('VIBE_STR_MIN', '25'))
VIBE_STR_MAX = int(os.environ.get('VIBE_STR_MAX', '100'))
VIBE_DUR_MIN = int(os.environ.get('VIBE_DUR_MIN', '300'))
VIBE_DUR_MAX = int(os.environ.get('VIBE_DUR_MAX', '1000'))
VIBE_COOLDOWN = int(os.environ.get('VIBE_COOLDOWN', '10'))
SHOCK_STR_MIN = int(os.environ.get('SHOCK_STR_MIN', '1'))
SHOCK_STR_MAX = int(os.environ.get('SHOCK_STR_MAX', '1'))
SHOCK_DUR_MIN = int(os.environ.get('SHOCK_DUR_MIN', '300'))
SHOCK_DUR_MAX = int(os.environ.get('SHOCK_DUR_MAX', '300'))
SHOCK_COOLDOWN = int(os.environ.get('SHOCK_COOLDOWN', '60'))

BLACKLIST = os.environ.get('BLACKLIST', '')
blacklisted_ids = re.findall('-?\\d+',BLACKLIST)
blacklisted_ids = [int(x) for x in blacklisted_ids]

WHITELIST = os.environ.get('WHITELIST', 'false')
WHITELIST = WHITELIST.lower() == 'true'


# API endpoint, view more at https://api.shocklink.net/swagger/index.html (select a definition on the top right)
url = 'https://api.shocklink.net/2/shockers/control'
# Authenticate with OpenShock
headers = {'accept': 'application/json', 'OpenShockToken': SHOCK_API, 'Content-Type': 'application/json'}

# Initialise shock cooldowns (available immediately when bot started)
next_action = datetime.now()

# Define a general usage string
USAGE = f'''Usage: /shock|vibrate <strength> <duration>
Shocks: **{SHOCK_STR_MIN}** - **{SHOCK_STR_MAX}**% strength for **{SHOCK_DUR_MIN / 1000}** - **{SHOCK_DUR_MAX / 1000}**s
Vibrations: **{VIBE_STR_MIN}** - **{VIBE_STR_MAX}**% strength for **{VIBE_DUR_MIN / 1000}** - **{VIBE_DUR_MAX / 1000}**s'''

#This fuinction is used to select a value between min and max, with a default used otherwise
def clamp(min_val, max_val, default_val):
    return max(min_val, min(default_val, max_val))

# This function handles the two actions
async def command(event, cmd):
    global next_action

    # Get action and its parameters from the command args
    action = cmd[0].split('/')[1].capitalize()
    action_strength = cmd[1]
    action_length = int(cmd[2] * 1000)
    action_cooldown = 0

    # Determine the correct length and strength depending on the type of the action
    match action:
        case 'Shock':
            action_strength = clamp(SHOCK_STR_MIN, SHOCK_STR_MAX, action_strength)
            action_length = clamp(SHOCK_DUR_MIN, SHOCK_DUR_MAX, action_length)
            action_cooldown = SHOCK_COOLDOWN
        case 'Vibrate':
            action_strength = clamp(VIBE_STR_MIN, VIBE_STR_MAX, action_strength)
            action_length = clamp(VIBE_DUR_MIN, VIBE_DUR_MAX, action_length)
            action_cooldown = VIBE_COOLDOWN

    sender = await client.get_entity(event.sender_id)
    if (event.sender_id not in blacklisted_ids and not WHITELIST) or (event.sender_id in blacklisted_ids and WHITELIST):
        # If enough time has passed since last action
        if datetime.now() > next_action:
            print(f'{datetime.now()}: {action} request received from {sender.first_name} ({event.sender_id})')
        
            # Disable action for <action>_COOLDOWN seconds
            next_action = datetime.now() + timedelta(seconds = action_cooldown)
            
            # Message to send to the API
            payload = {'shocks': [{'id': SHOCK_ID, 'type': action, 'intensity': action_strength,
                       'duration': action_length, 'exclusive': True}], 'customName': 'string'}
            
            # Send the request and save the response
            response = requests.post(url = url, headers = headers, json = payload)
            
            # If everything went okay, reply with success
            if response.status_code == 200:
                await event.reply(f'(OpenShock) {action} sent successfully.')
            print(f'{datetime.now()}: {response.content}; {action} at {action_strength}% for {action_length / 1000}s')
            
        # If not enough time has passed, say how long is left
        else:
            print(f'{datetime.now()}: {action} request from {sender.first_name} ({event.sender_id}) denied due to cooldown.')
            await event.reply(f'(OpenShock) Next {action.lower()} available in {str((next_action - datetime.now()).seconds)} seconds.')
    else:
        print(f'{datetime.now()}: Blacklisted user {sender.first_name} ({event.sender_id}) has tried to use {action.lower()}!')
        return

# On new message received that starts with "/"
@client.on(events.NewMessage(pattern='^/.+'))
async def main(event):
    # Is it a PM?
    if event.is_private:
        # Split args by space to a list
        cmd = event.raw_text.lower().split(" ")

        # Try to convert the len, dur args to numbers from string, if missing, set them to 0
        try:
            cmd[1] = int(cmd[1])
            cmd[2] = float(cmd[2])
        except IndexError:
            cmd.extend([0, 0])
        # Reply with the usage if the args are not numbers
        except ValueError:
            if event.user_id not in BLACKLIST: await event.reply(f'The supplied arguments are not numbers. {USAGE}')
            return
            
        # Handle individual commands
        match cmd[0]:
            case '/shock':
                await command(event, cmd)
            case '/vibrate':
                await command(event, cmd)
            case '/help':
                await event.reply(USAGE)
            case _:
                await event.reply(f'Unknown command. {USAGE}')
                print(f'{datetime.now()}: Unknown command sent.')

# Message to let you know the bot is working
async def welcome_msg():
    ready_msg = "(OpenShock) Bot Ready!"
    me = await client.get_me()
    # If the blacklist is treated as a whitelist, the first whitelisted ID is treated as the owner
    if WHITELIST and me.bot:
        await client.send_message(blacklisted_ids[0], ready_msg)
    else:
        await client.send_message(me.id, ready_msg)
    print(f'{datetime.now()}: Python script running as {me.first_name} ({me.id})')

# Run the bot
client.start()
client.loop.run_until_complete(welcome_msg())
client.run_until_disconnected()
