import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
import json
import os
from config import TELEGRAM_TOKEN, STEAM_API_KEY

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Placeholder for user data
user_data = {}
USER_DATA_FILE = 'user_data.json'
HERO_NAMES_FILE = 'hero_names.json'


def load_user_data():
    global user_data
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as file:
            user_data = json.load(file)


def save_user_data():
    with open(USER_DATA_FILE, 'w') as file:
        json.dump(user_data, file)


def start(update: Update, context: CallbackContext) -> None:
    commands = [
        "/start - Start the bot",
        "/adduser <alias> <steamid> <dotaid> - Add a user with alias, Steam ID, and DotA ID",
        "/showuser <alias> - Show the status of the user with the given alias including last 10 games results",
        "/resetuser <alias> - Remove the user with the given alias and all associated nicknames",
        "/changeuser <alias> <newalias> - Change the alias of the user",
        "/userlist - Show all registered aliases",
        "/commandlist - Show all available commands",
        "/addnickname <alias> <nickname> - Add a nickname for a registered alias"
    ]
    update.message.reply_text(
        "Welcome to the Steam Status Bot! Use the commands below to manage users:\n" + "\n".join(commands))


def add_user(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 3:
        update.message.reply_text('Usage: /adduser <alias> <steamid> <dotaid>')
        return
    alias = args[0].lower()  # Convert alias to lowercase
    steam_id = args[1]
    dotaid = args[2]
    # Check if alias already exists (case-insensitive)
    if alias in (existing_alias.lower() for existing_alias in user_data):
        update.message.reply_text('Alias is already taken. Try again with a different alias.')
        return
    user_data[alias] = {'steam_id': steam_id, 'dotaid': dotaid}
    save_user_data()
    update.message.reply_text(f'User {alias} with Steam ID {steam_id} and DotA ID {dotaid} added.')


def add_nickname(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 2:
        update.message.reply_text('Usage: /addnickname <alias> <nickname>')
        return
    alias = args[0].lower()  # Convert alias to lowercase
    nickname = args[1].lower()  # Convert nickname to lowercase

    # Check if alias exists
    if alias not in user_data:
        update.message.reply_text(f'No user found with alias {args[0]}.')
        return

    # Check if nickname is already taken or is a nickname itself
    if nickname in (existing_alias.lower() for existing_alias in user_data) or 'nickname' in user_data.get(nickname,
                                                                                                           {}):
        update.message.reply_text('Nickname is already taken or cannot be used as a nickname.')
        return

    # Add nickname
    user_data[nickname] = user_data[alias].copy()
    user_data[nickname]['nickname'] = alias  # Store the original alias as 'nickname' value
    save_user_data()
    update.message.reply_text(f'Nickname {nickname} added for alias {alias}.')


def show_user(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 1:
        update.message.reply_text('Usage: /showuser <alias>')
        return
    alias_or_nickname = args[0].lower()  # Convert alias or nickname to lowercase
    if alias_or_nickname not in user_data:
        update.message.reply_text(f'No user found with alias or nickname {args[0]}.')
        return

    if alias_or_nickname in user_data:
        alias = alias_or_nickname
    else:
        alias = next(
            key for key, value in user_data.items() if 'nickname' in value and value['nickname'] == alias_or_nickname)

    steam_id = user_data[alias]['steam_id']
    dotaid = user_data[alias]['dotaid']
    steam_status, game_info = get_steam_status(steam_id)

    # Fetch Steam user's profile name
    steam_user_name = get_steam_user_name(steam_id)

    if game_info:
        update.message.reply_text(f'User {alias} is currently {steam_status}.\nPlaying: {game_info}')
    else:
        update.message.reply_text(f'User {alias} is currently {steam_status}.')

    # Fetch and display match history
    match_history = get_match_history(dotaid)
    if match_history is None:
        update.message.reply_text(f'Failed to fetch match history for DotA ID {dotaid}.')
    else:
        results = "\n".join([
            f"{match['match_id']}: {'Won' if match['radiant_win'] == (match['player_slot'] < 128) else 'Lost'} - Hero: {get_hero_name(match['hero_id'])}"
            for match in match_history])
        update.message.reply_text(f'Last 10 games results for {steam_user_name}:\n{results}')


def reset_user(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 1:
        update.message.reply_text('Usage: /resetuser <alias>')
        return
    alias = args[0].lower()  # Convert alias to lowercase
    if alias not in user_data:
        update.message.reply_text(f'No user found with alias {args[0]}.')
        return

    # Remove main alias
    del user_data[alias]

    # Remove associated nicknames
    nicknames_to_remove = [key for key, value in user_data.items() if
                           'nickname' in value and value['nickname'] == alias]
    for nickname in nicknames_to_remove:
        del user_data[nickname]

    save_user_data()
    update.message.reply_text(f'User {args[0]} and all associated nicknames have been removed.')


def change_user(update: Update, context: CallbackContext) -> None:
    args = context.args
    if len(args) != 2:
        update.message.reply_text('Usage: /changeuser <alias> <newalias>')
        return
    alias = args[0].lower()  # Convert alias to lowercase
    newalias = args[1]
    if alias not in user_data:
        update.message.reply_text(f'No user found with alias {args[0]}.')
        return
    if newalias.lower() in (existing_alias.lower() for existing_alias in user_data):
        update.message.reply_text('New alias is already taken. Try with a different one.')
        return
    user_data[newalias] = user_data.pop(alias)
    save_user_data()
    update.message.reply_text(f'Alias changed from {args[0]} to {args[1]}.')


def user_list(update: Update, context: CallbackContext) -> None:
    if not user_data:
        update.message.reply_text('No users registered.')
    else:
        alias_list = []
        for alias, data in user_data.items():
            if 'nickname' in data:
                original_alias = data['nickname']
                alias_list.append(f'{alias} - nickname for {original_alias}')
            else:
                alias_list.append(alias)
        update.message.reply_text(f'Registered aliases:\n' + '\n'.join(alias_list))


def command_list(update: Update, context: CallbackContext) -> None:
    commands = [
        "/start - Start the bot",
        "/adduser <alias> <steamid> <dotaid> - Add a user with alias, Steam ID, and DotA ID",
        "/showuser <alias> - Show the status of the user with the given alias including last 10 games results",
        "/resetuser <alias> - Remove the user with the given alias and all associated nicknames",
        "/changeuser <alias> <newalias> - Change the alias of the user",
        "/userlist - Show all registered aliases",
        "/commandlist - Show all available commands",
        "/addnickname <alias> <nickname> - Add a nickname for a registered alias"
    ]
    update.message.reply_text("Available commands:\n" + "\n".join(commands))


def get_steam_status(steam_id):
    url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steam_id}"
    response = requests.get(url)
    if response.status_code != 200:
        return "offline or unable to fetch status", None
    data = response.json()
    if "response" in data and "players" in data["response"] and len(data["response"]["players"]) > 0:
        player = data["response"]["players"][0]
        status = player.get("personastate", 0)
        status_descriptions = {
            0: "Offline",
            1: "Online",
            2: "Busy",
            3: "Away",
            4: "Snooze",
            5: "Looking to trade",
            6: "Looking to play"
        }
        status_description = status_descriptions.get(status, "Unknown")
        game_info = ""
        if player.get("gameextrainfo"):
            game_info = f"{player['gameextrainfo']}"
            if player.get("personastate") == 1:
                game_info += " (Online)"
            elif player.get("personastate") == 2:
                game_info += " (Busy)"
            elif player.get("personastate") == 3:
                game_info += " (Away)"
            elif player.get("personastate") == 4:
                game_info += " (Snooze)"
            elif player.get("personastate") == 5:
                game_info += " (Looking to trade)"
            elif player.get("personastate") == 6:
                game_info += " (Looking to play)"
        return status_description, game_info
    return "offline", None


def get_match_history(dotaid):
    url = f"https://api.opendota.com/api/players/{dotaid}/matches?limit=10"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to fetch match history for DotA ID {dotaid}. Status code: {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Error fetching match history for DotA ID {dotaid}: {e}")
        return None


def get_hero_name(hero_id):
    with open(HERO_NAMES_FILE, 'r') as file:
        hero_names = json.load(file)
    return hero_names.get(str(hero_id), "Unknown")


def get_steam_user_name(steam_id):
    url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steam_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "response" in data and "players" in data["response"] and len(data["response"]["players"]) > 0:
                return data["response"]["players"][0].get("personaname", "Unknown")
            else:
                logger.warning(f"Failed to fetch Steam user profile for Steam ID {steam_id}.")
        else:
            logger.warning(
                f"Failed to fetch Steam user profile for Steam ID {steam_id}. Status code: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"Error fetching Steam user profile for Steam ID {steam_id}: {e}")
    return "Unknown"


def main() -> None:
    load_user_data()
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("adduser", add_user))
    dp.add_handler(CommandHandler("showuser", show_user))
    dp.add_handler(CommandHandler("resetuser", reset_user))
    dp.add_handler(CommandHandler("changeuser", change_user))
    dp.add_handler(CommandHandler("userlist", user_list))
    dp.add_handler(CommandHandler("commandlist", command_list))
    dp.add_handler(CommandHandler("addnickname", add_nickname))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
