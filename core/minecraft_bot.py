import asyncio, sys, time, logging, requests, json, re

from javascript import require, On, config

from core.config import ServerConfig, SettingsConfig, AccountConfig

regex_username = re.compile(r"^(?:Guild|Officer) > (?:\[[+A-Z]*\] )*([a-zA-Z0-9_]+) (?:\[[A-Z]*\]: )?(.+)")

mineflayer = require("mineflayer")

def roundToHundreths(x):
    return round((x + sys.float_info.epsilon) * 100) / 100

def ensureValidDenominator(x):
    return 1 if x == 0 else x

def getPlayerStat(mode, x, data):
    if mode == "Bedwars":
        try:
            return data["player"]["stats"][mode][x]
        except:
            return 0

def getInfo(call):
    r = requests.get(call)
    return r.json()


class MinecraftBotManager:
    def __init__(self, client, bot):
        self.client = client
        self.bot = bot
        self.wait_response = False
        self.message_buffer = []
        self.auto_restart = True
        self._online = False

    async def chat(self, message):
        await self.client.loop.run_in_executor(None, self.bot.chat, message)

    def stop(self, restart: bool = True):
        print("Stopping bot.....")
        self.auto_restart = restart
        try:
            self.bot.quit()
        except Exception as e:
            logging.error(f"Failed to quit bot gracefully: {e}")
        finally:
            self._online = False
            while self._online:
                time.sleep(0.2)

    def send_to_discord(self, message):
        asyncio.run_coroutine_threadsafe(self.client.send_discord_message(message), self.client.loop)

    def oncommands(self):
        message_buffer = []

        @On(self.bot, "login")
        def login(this):
            print("Bot is logged in.")
            print(self.bot.username)
            self.bot.chat("§")
            if not self._online:
                self.send_to_discord("Bot Online")
            self._online = True
            self.client.dispatch("minecraft_ready")

        @On(self.bot, "end")
        def end(this, reason):
            print(f"Mineflayer > Bot offline: {reason}")
            self.send_to_discord("Bot Offline")
            self.client.dispatch("minecraft_disconnected")
            self._online = False
            if self.auto_restart:
                time.sleep(120)
                if self.auto_restart:
                    print("Mineflayer > Restarting...")
                    new_bot = self.createbot(self.client)
                    self.client.mineflayer_bot = new_bot
                    return
            for state, handler, thread in config.event_loop.threads:
                thread.terminate()
            config.event_loop.threads = []
            config.event_loop.stop()
        
        @On(self.bot, "kicked")
        def kicked(this, reason, loggedIn):
            print(f"Mineflayer > Bot kicked: {reason}")
            self.client.dispatch("minecraft_disconnected")
            if loggedIn:
                self.send_to_discord(f"Bot kicked: {reason}")
            else:
                self.send_to_discord(f"Bot kicked before logging in: {reason}")
            

        @On(self.bot, "error")
        def error(this, reason):
            print(reason)
            self.client.dispatch("minecraft_error")

        @On(self.bot, "messagestr")
        def chat(this, message, messagePosition, jsonMsg, sender, verified):
            def print_message(_message):
                max_length = 100  # Maximum length of each chunk
                chunks = [_message[i:i + max_length] for i in range(0, len(_message), max_length)]
                for chunk in chunks:
                    print(chunk)

            print_message(message)


            if self.bot.username is None:
                return

            if message.startswith("Guild > " + self.bot.username) or message.startswith(
                    "Officer > " + self.bot.username
                    ):
                return

            if not message.startswith("Guild >") and not message.startswith("Officer >"):
                return
            
            if message == "You cannot say the same message twice!":
                self.send_minecraft_message("None", message, "General")
            
            # Online Command
            if message.startswith("Guild Name: "):
                message_buffer.clear()
                self.wait_response = True
            if message == "-----------------------------------------------------" and self.wait_response:
                self.wait_response = False
                self.send_to_discord("\n".join(message_buffer))
                message_buffer.clear()
            if self.wait_response is True:
                message_buffer.append(message)

            if "Unknown command" in message:
                self.send_to_discord(message)
            if "Click here to accept or type /guild accept " in message:
                self.send_to_discord(message)
                self.send_minecraft_message("None", message, "invite")
            elif " is already in another guild!" in message or \
                    ("You invited" in message and "to your guild. They have 5 minutes to accept." in message) or \
                    " joined the guild!" in message or \
                    " left the guild!" in message or \
                    " was promoted from " in message or \
                    " was demoted from " in message or \
                    " was kicked from the guild!" in message or \
                    " was kicked from the guild by " in message or \
                    "You cannot invite this player to your guild!" in message or \
                    "Disabled guild join/leave notifications!" in message or \
                    "Enabled guild join/leave notifications!" in message or \
                    "You cannot say the same message twice!" in message or \
                    "You don't have access to the officer chat!" in message or \
                    "Your guild is full!" in message or \
                    "is already in your guild!" in message or \
                    ("has muted" in message and "for" in message) or \
                    "has unmuted" in message or \
                    "You're currently guild muted" in message:
                self.send_to_discord(message)


            username, parsed_message = regex_username.match(message).groups()
            username.strip()
            parsed_message = parsed_message.strip()

            if not parsed_message.startswith("!"):
                self.send_to_discord(message)
                return
            
            command_args = parsed_message.split(' ')
            command_args[0] = command_args[0].lower()
            if command_args[0] == "!bedwars" or command_args[0] == "!bw":
                for i in range(len(command_args)):
                    if command_args[i] == "!bedwars" or command_args == "!bw" or command_args == "":
                        pass
                    else:
                        username = command_args[i].strip()
                        break
                player_data = f"https://api.hypixel.net/player?key={SettingsConfig.api_key}&name={username}"
                data = getInfo(player_data) 
                print("Got data")

                if data["success"] == False:
                    print("success: False")
                    if data["cause"] == "Invalid API key":
                        player_stats = "[ERROR] Invalid API key"
                        self.send_minecraft_message("None", player_stats, "General")
                    elif data["cause"] == "You have already looked up this name recently":
                        player_stats = "[ERROR] Please wait before searching for the same user"
                        self.send_minecraft_message("None", player_stats, "General")
                    else:
                        player_stats = "[ERROR] Unknown"
                        self.send_minecraft_message("None", player_stats, "General")
                elif data["player"] == "null":
                    print("[ERROR] Invalid Player")
                    player_stats = "[ERROR] Invalid Player"
                    self.send_minecraft_message("None", player_stats, "General")
                else:
                    wins_bedwars = getPlayerStat("Bedwars", "wins_bedwars", data)
                    losses_bedwars = getPlayerStat("Bedwars", "losses_bedwars", data)
                    final_kills_bedwars = getPlayerStat("Bedwars", "final_kills_bedwars", data)
                    final_deaths_bedwars = getPlayerStat("Bedwars", "final_deaths_bedwars", data)
                    winstreak_bedwars = getPlayerStat("Bedwars", "winstreak", data)
                    target_user = data["player"]["displayname"]
                    print(target_user)

                    win_loss_ratio = roundToHundreths(wins_bedwars / ensureValidDenominator(losses_bedwars))
                    final_kill_death_ratio = roundToHundreths(final_kills_bedwars / ensureValidDenominator(final_deaths_bedwars))

                    player_stats = f"{target_user} | WLR: {win_loss_ratio} | FKDR: {final_kill_death_ratio} | W: {wins_bedwars} | FK: {final_kills_bedwars} | WS: {winstreak_bedwars}"
                    self.send_minecraft_message("None", player_stats, "General")
                return

    def send_minecraft_message(self, discord, message, type):
        if type == "General":
            message_text = f"/gc {discord}: {message}"
            if discord == "None":
                message_text = f"/gc {message}"
            message_text = message_text[:256]
            self.bot.chat(message_text)
            
        if type == "Officer":
            message_text = f"/oc {discord}: {message}"
            if discord == "None":
                message_text = f"/oc {message}"
            message_text = message_text[:256]
            self.bot.chat(message_text)
        if type == "invite":
            if SettingsConfig.autoaccept:
                message = message.split()
                if ("[VIP]" in message or "[VIP+]" in message or
                        "[MVP]" in message or "[MVP+]" in message or "[MVP++]" in message):
                    username = message.split()[2]
                else:
                    username = message.split()[1]
                self.bot.chat(f"/g accept {username}")

    def send_minecraft_command(self, message):
        message = message.replace("!o ", "/")
        self.bot.chat(message)

    @classmethod
    def createbot(cls, client):
        print("Mineflayer > Creating the bot...")
        bot = mineflayer.createBot(
            {
                "host": ServerConfig.host,
                "port": ServerConfig.port,
                "version": "1.8.9",
                "username": AccountConfig.email,
                "auth": "microsoft",
                "viewDistance": "tiny",
            }
        )
        print("Mineflayer > Initialized")
        botcls = cls(client, bot)
        client.mineflayer_bot = botcls
        botcls.oncommands()
        print("Mineflayer > Events registered")
        return botcls
