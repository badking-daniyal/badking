"""دسترسی مستقیم و خام به تمام متدهای Bot API بله.

لایه خام: هر متدی که بله دارد را میشود با `bot.request("MethodName", {...})` صدا زد.
این ماژول لیست متدهای شناختهشده را برای مرجع نگه میدارد (بدون محدود کردن دسترسی).
"""

# متدهای مستندشده در docs.bale.ai (مرجع؛ Bot.request هیچ محدودیتی ندارد)
KNOWN_METHODS = [
    "getMe", "getUpdates", "sendMessage", "forwardMessage", "copyMessage",
    "sendPhoto", "sendAudio", "sendDocument", "sendVideo", "sendAnimation",
    "sendVoice", "sendLocation", "sendContact", "sendChatAction",
    "editMessageText", "editMessageCaption", "editMessageReplyMarkup",
    "deleteMessage", "getFile", "answerCallbackQuery",
    "getChat", "getChatAdministrators", "getChatMember", "getChatMembersCount",
    "setWebhook", "deleteWebhook", "getWebhookInfo",
    "setMyCommands", "getMyCommands", "sendInvoice", "createInvoiceLink",
    "answerPreCheckoutQuery", "answerShippingQuery", "askReview",
    "inquireTransaction", "sendPoll", "sendDice", "setChatMenuButton",
]

__all__ = ["KNOWN_METHODS"]
