import asyncio
import json
import logging
from base64 import b64decode, b64encode
from threading import Thread

import discord
import trio
from rich.logging import RichHandler

import constants
from pypush import apns, ids, imessage

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

intents = discord.Intents.default()
disc_client = discord.Client(intents=intents)


async def iMessageMain():
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

        im = imessage.iMessageUser(conn, user)

        return im


def run_trio_in_thread(async_fn, result_queue, *args, **kwargs):
    def trio_thread_target():
        try:
            result = trio.run(async_fn, *args, **kwargs)
        except Exception as e:
            result_queue.put(e)
        else:
            result_queue.put(result)

    thread = Thread(target=trio_thread_target)
    thread.start()
    return thread


@disc_client.event
async def on_ready():
    print("Logged in as {0.user}".format(disc_client))


@disc_client.event
async def on_message(message):
    if message.author == disc_client.user:
        return

    if message.channel.name == constants.DESIGN_CHANNEL and constants.DESIGN_ROLE in [
        x.name for x in message.role_mentions
    ]:
        await message.add_reaction("👀")

        result_queue = asyncio.Queue()
        thread = run_trio_in_thread(iMessageMain, result_queue)
        thread.join()
        iMessageBot = await result_queue.get()

        if isinstance(iMessageBot, Exception):
            raise iMessageBot

        send_thread = run_trio_in_thread(
            iMessageBot.send,
            args=(
                imessage.iMessage.create(
                    user=iMessageBot,
                    text=f"Discord Message: {message.content}",
                    participants=constants.IMSG_NUMBERS,
                    effect=None,
                )
            ),
            result_queue=result_queue,
        )
        send_thread.join()

        res = await result_queue.get()
        if isinstance(res, Exception):
            raise res

        """
        if message.attachments:
            for a in message.attachments:
                send_thread = Thread(
                    target=send_message_in_trio_thread,
                    args=(iMessageBot, a.url, constants.IMSG_NUMBERS),
                )
                send_thread.start()
                send_thread.join()
        """

        await message.channel.send(
            "You mentioned the Design role in our channel, so I forwarded your message to the team's iMessage group chat!"
        )


if __name__ == "__main__":
    disc_client.run(constants.BOT_TOKEN)
