import asyncio
import json
import logging
import queue
import textwrap
import typing
from base64 import b64decode, b64encode
from threading import Event, Thread

import discord
import trio
from rich.logging import RichHandler

import constants
from pypush import apns, ids, imessage

# Setup logging
logging.basicConfig(
    level=logging.NOTSET, format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("py.warnings").setLevel(logging.ERROR)  # Ignore warnings from urllib3
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("jelly").setLevel(logging.INFO)
logging.getLogger("nac").setLevel(logging.INFO)
logging.getLogger("apns").setLevel(logging.DEBUG)
logging.getLogger("albert").setLevel(logging.INFO)
logging.getLogger("ids").setLevel(logging.DEBUG)
logging.getLogger("bags").setLevel(logging.INFO)
logging.getLogger("imessage").setLevel(logging.DEBUG)
logging.getLogger("pypush").setLevel(logging.DEBUG)
logging.getLogger("discord").setLevel(logging.INFO)

logging.captureWarnings(True)


# Try load config.json
try:
    with open("config.json", "r") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    CONFIG = {}

# Initialize Discord client
intents = discord.Intents(
    guilds=True,
    members=True,
    reactions=True,
    messages=True,
    message_content=True,
)
disc_client = discord.Client(intents=intents)


# Main iMessage function
async def iMessageMain(msg: str):
    """
    Initialize iMessage connection using config.json, and sends a message to hardcoded iMessage group chat.
    Group chat is hardcoded in constants.py

    msg: Message to send to iMessage group chat. (str)
    """
    token = CONFIG.get("push", {}).get("token")
    if token is not None:
        token = b64decode(token)
    else:
        token = b""

    push_creds = apns.PushCredentials(
        CONFIG.get("push", {}).get("key", ""),
        CONFIG.get("push", {}).get("cert", ""),
        token,
    )

    async with apns.APNSConnection.start(push_creds) as conn:
        await conn.set_state(1)
        await conn.filter(["com.apple.madrid"])

        user = ids.IDSUser(conn)
        user.auth_and_set_encryption_from_config(CONFIG)

        # Write config.json
        CONFIG["encryption"] = {
            "rsa_key": user.encryption_identity.encryption_key,
            "ec_key": user.encryption_identity.signing_key,
        }
        CONFIG["id"] = {
            "key": user._id_keypair.key,
            "cert": user._id_keypair.cert,
        }
        CONFIG["auth"] = {
            "key": user._auth_keypair.key,
            "cert": user._auth_keypair.cert,
            "user_id": user.user_id,
            "handles": user.handles,
        }
        CONFIG["push"] = {
            "token": b64encode(user.push_connection.credentials.token).decode(),
            "key": user.push_connection.credentials.private_key,
            "cert": user.push_connection.credentials.cert,
        }

        with open("config.json", "w") as f:
            json.dump(CONFIG, f, indent=4)

        print(f"Authenticating as: {user}.")
        iMessageBot = imessage.iMessageUser(conn, user)

        iMessage = imessage.iMessage.create(
            user=iMessageBot,
            text=msg,
            participants=constants.IMSG_NUMBERS,
            effect=None,
        )

        with trio.move_on_after(6):
            await iMessageBot.send(iMessage)


# Pypush uses trio for async handling, whilst discord.py uses asyncio.
# To handle these incompatible async calls together, this function runs trio in a separate thread.
def run_trio_in_thread(
    async_fn: typing.Callable, result_queue: queue.Queue, *args, **kwargs
):
    """
    Runs an async function in a separate thread using trio.

    async_fn: Async function to run in a separate thread. (typing.Callable)
    result_queue: Queue to put the result of the async function in. (queue.Queue)
    *args: Arguments to pass to async_fn.
    **kwargs: Keyword arguments to pass to async_fn.

    Returns: Thread object, and an Event object that is set when the thread is done.
    """
    done_event = Event()

    def trio_thread_target():
        try:
            result = trio.run(async_fn, *args, **kwargs)
            result_queue.put(result)
        except Exception as e:
            result_queue.put(e)
        finally:
            done_event.set()

    thread = Thread(target=trio_thread_target)
    thread.start()

    return thread, done_event


@disc_client.event
async def on_ready():
    print("Logged into Discord as {0.user}".format(disc_client))
    print("Awaiting messages...")


@disc_client.event
async def on_message(message):
    if message.author == disc_client.user:
        return

    if message.channel.name == constants.DESIGN_CHANNEL and constants.DESIGN_ROLE in [
        x.name for x in message.role_mentions
    ]:
        await message.add_reaction("👀")

        iMessageText = (
            f"Discord ping from {message.author.display_name}:\n{message.clean_content}"
        )
        print(
            f"Processing message:\n{textwrap.indent(text=iMessageText, prefix='    ')}"
        )

        result_queue = queue.Queue()
        thread, done_event = run_trio_in_thread(
            iMessageMain, result_queue, iMessageText
        )

        while not done_event.is_set():
            await asyncio.sleep(1)

        thread.join()
        res = result_queue.get()

        if isinstance(res, Exception):
            logging.exception("Error occurred in trio thread", exc_info=res)
            raise res
        else:
            print("iMessage sent, sending response to channel.")
            await message.channel.send(
                "You mentioned the Design role in our channel, so I forwarded your message to the team's iMessage group chat!"
            )

        print("Done.\n")


if __name__ == "__main__":
    disc_client.run(constants.BOT_TOKEN)
