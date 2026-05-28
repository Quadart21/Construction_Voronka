from telegram.ext import Application


def bot_id_from(application: Application) -> int:
    bot_id = application.bot_data.get("bot_id")
    if bot_id is None:
        raise RuntimeError("bot_id is not set on application.bot_data")
    return int(bot_id)
