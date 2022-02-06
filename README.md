# PLWardstoneBot

A script for watching matchups in a Primeleague group for events such as new scheduling suggestions
and sending alerts about new events to a Discord channel via a Webhook.

## Getting started

Install the required dependencies:
``pip install schedule request beautifulsoup4``

Create a file called settings.py in the same folder as the project with the following lines:
```
group_url = "https://www.primeleague.gg/leagues/prm/..."
team = "your-team-name"
webhook = "https://discord.com/api/webhooks/...
```
Insert the url to the Primeleague group as the first value,
the name of your team with dashes '-' instead of spaces and
a Discord Webhook.

Create a folder called "saved_logs".

Then start main.py with Python 3.

## What it does

The script will look up all match urls that involve the given team name and add them to its watchlist.
Any matches that are completed will be removed from the watchlist.
To keep track of what are new and old events, the script saves the events of not completed matches in a folder as json files.
When a match is completed, the script will delete the log file for it.
When the script detects any significant events that require your attention, it will send a message to the given Discord Webhook.


