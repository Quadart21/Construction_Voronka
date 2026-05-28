from telegram.ext import Application

_bot_applications: dict[int, Application] = {}


def set_bot_application(application: Application, bot_id: int) -> None:
    _bot_applications[int(bot_id)] = application
    application.bot_data["bot_id"] = int(bot_id)


def get_bot_application(bot_id: int | None = None) -> Application | None:
    if bot_id is not None:
        return _bot_applications.get(int(bot_id))
    if len(_bot_applications) == 1:
        return next(iter(_bot_applications.values()))
    return None


def get_all_bot_applications() -> dict[int, Application]:
    return dict(_bot_applications)


def clear_bot_applications() -> None:
    _bot_applications.clear()
