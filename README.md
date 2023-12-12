# mBot

Experimental Discord to iMessage forwarding bot using [pypush](https://github.com/JJTech0130/pypush)

## Setup
1. Run `setup.sh` (or install dependencies manually with `requirements.txt`)
2. Create `constants.py` and `config.json`
3. Run main.py

## config.json
This should be created by pypush or automatically generated once you run main.py and input your Apple credentials. See pypush repo for more info.

## constants.py structure:
```
BOT_TOKEN = [Discord bot token]
LOGGING = [True/False]

# Name of Discord channel to watch for messages in:
DESIGN_CHANNEL = [channel name]

# Name of Discord role to watch for mentions of:
DESIGN_ROLE = [role name]

# iMessage numbers to send messages to, a list of strings:
#   - phone format "tel:+1416XXXXXXX"
#   - email format "mailto:bot@mtran.ca"
IMSG_NUMBERS = [
    "number1",
    "number2",
    "etc.",
]
```
