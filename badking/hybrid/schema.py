"""اسکیمای RPC داخلی بله — تولیدشده از پروتکل واقعی.

این فایل را دستی ویرایش نکن. اگر بله پروتکل را عوض کرد،
با BADKING_RPC_SCHEMA override کن یا این فایل را بازتولید کن.

شکل هر فیلد:
    عدد                      → فیلد ساده
    {"field": N, "fields": "Type"}  → پیام تودرتو
    {"field": N, "fields": "Type", "repeated": True}  → لیست پیام
"""

from __future__ import annotations

# ---------- تایپ‌های تودرتو ----------
NESTED: dict[str, dict[str, object]] = {
    "Peer": {"type": 1, "id": 2, "accessHash": 3},
    "Chat": {"type": 1, "id": 2},
    "ShortPeer": {"id": 1, "accessHash": 2},
    "StringValue": {"value": 1},
    "IntValue": {"value": 1},
    "BoolValue": {"value": 1},
    "IntBool": {"value": 1},
    "IntListValue": {"values": 1},
    "TextMessage": {"value": 1},
    "MessageCaption": {"content": 1, "mentions": 2, "ext": 3},
    "Thumbnail": {"w": 1, "h": 2, "image": 3},
    "DocumentMessage": {"fileId": 1, "accessHash": 2, "size": 3, "name": 4, "mimeType": 5, "thumb": {"field": 6, "fields": "Thumbnail"}, "ext": 7, "caption": {"field": 8, "fields": "MessageCaption"}},
    "MessageContent": {"document": {"field": 4, "fields": "DocumentMessage"}, "empty": 5, "serviceMessage": 11, "botMessage": {"field": 13, "fields": "TemplateMessage"}, "text": {"field": 15, "fields": {'value': 1}}, "gift": {"field": 17, "fields": "GiftPacket"}},
    "TemplateMessage": {"message": {"field": 1, "fields": "MessageContent"}, "tempId": 2, "inlineKeyboardMarkup": {"field": 5, "fields": "InlineKeyboard"}},
    # ساختار تأییدشده از aiobale 0.3.9 types/inline_keyboard.py:
    #   InlineKeyboardMarkup{1: [Row{1: [Button]}]}
    #   Button{1: text, 2: {1: url}, 3: {1: callback_data}, 9: {1: copy_text}}
    # فیلدهای ۲/۳/۹ wrapper تکفیلدیاند (StringValue{value:1}).
    "InlineButton": {"text": 1, "url": {"field": 2, "fields": "StringValue"}, "callbackData": {"field": 3, "fields": "StringValue"}, "copyText": {"field": 9, "fields": "StringValue"}},
    "InlineKeyboardRow": {"buttons": {"field": 1, "fields": "InlineButton", "repeated": True}},
    "InlineKeyboard": {"rows": {"field": 1, "fields": "InlineKeyboardRow", "repeated": True}},
    "OtherMessage": {"date": 1, "messageId": 2, "seq": 3},
    "InfoMessage": {"peer": {"field": 1, "fields": "Peer"}, "messageId": 2, "date": 3},
    "QuotedMessage": {"messageId": 1, "senderId": 3, "date": 4, "content": {"field": 5, "fields": "MessageContent"}, "peer": {"field": 6, "fields": "Peer"}},
    "MessageData": {"senderId": 1, "messageId": 2, "date": 3, "content": {"field": 4, "fields": "MessageContent"}, "repliedTo": 8, "previousMessage": 10, "nextMessage": 11, "editedAt": 12},
    "PeerData": {"peer": {"field": 1, "fields": "Peer"}, "unreadCount": 2, "sortDate": 3, "senderId": 4, "messageId": 5, "date": 6, "content": {"field": 7, "fields": "MessageContent"}, "firstUnreadMessage": 9, "unreadMentions": 13},
    "User": {"id": 1, "accessHash": 2, "name": 3, "localName": 4, "sex": 5, "isBot": 7, "username": 9, "isDeleted": 16, "createdAt": 19},
    "Group": {"id": 1, "accessHash": 2, "title": 3, "isMember": 5, "isHidden": 12, "groupType": 15, "canSendMessage": 16, "username": 17, "isOrphaned": 18, "membersCount": 20, "permissions": {"field": 30, "fields": "Permissions"}, "defaultPermissions": {"field": 31, "fields": "Permissions"}, "ownerId": 32, "availableReactions": 33, "isSuspend": 36, "restriction": 40},
    "Member": {"id": 1, "inviterId": 2, "date": 3, "isAdmin": 4, "promotedBy": 5, "promotedAt": 6},
    "Permissions": {"seeMessage": 1, "deleteMessage": 2, "kickUser": 3, "pinMessage": 4, "inviteUser": 5, "addAdmin": 6, "changeInfo": 7, "sendMessage": 8, "seeMembers": 9, "editMessage": 10, "sendMedia": 11, "sendGifStickers": 12, "replyToStory": 13, "forwardMessageFrom": 14, "sendGiftPacket": 15, "startCall": 16, "sendLinkMessage": 17, "sendForwardedMessage": 18, "addStory": 19, "manageCall": 20},
    "Reaction": {"users": 1, "emojy": 2, "count": 3},
    "MessageReaction": {"id": 1, "date": 2, "reactions": {"field": 3, "fields": "Reaction", "repeated": True}},
    "MessageViews": {"message": {"field": 1, "fields": "OtherMessage"}, "views": 2},
    "Wallet": {"isMerchant": 1, "app": 2, "balance": 3, "token": 4, "level": 5, "pan": 6, "account": 7},
    # aiobale 0.3.9 FileInfo: file_id=1, access_hash=2, file_storage_version=3
    # (IntValue(value=1) پیشفرض). فیلد 3 اختیاری است و در درخواست ارسال نمیشود.
    "FileInfo": {"fileId": 1, "accessHash": 2, "fileStorageVersion": {"field": 3, "fields": "IntValue"}},
    "FileUploadInfo": {"fileId": 1, "url": 2, "chunkSize": 4},
    "GiftPacket": {"count": 1, "totalAmount": 2, "givingType": 3, "token": 4, "message": 5, "ownerId": 6, "showAmounts": 7},
    "BanData": {"bannedId": 1, "bannerId": 2},
    "InfoPeer": {"id": 1, "type": 2},
    "ContactRequest": {"phoneNumber": 1, "name": 2},
    "ContactData": {"id": 1, "phone": 2, "name": 3},
    "Report": {"peer": {"field": 1, "fields": "Peer"}, "messages": 2, "kind": 3},
    "Condition": {"exceptedPermissions": 1, "contacts": 2},
}

# aiobale 0.3.9 FileURL (types/file_url.py) — شماره فیلدها از سورس رسمی:
#   file_id=1, url=2, timeout=3 (ms), chunk_size=7 (پیشفرض 65536)
# قبلاً به اشتباه {url:1, name:2, size:3} بود که پاسخ سرور را خراب دیکود میکرد.
NESTED["FileURL"] = {"fileId": 1, "url": 2, "timeout": 3, "chunkSize": 7}
NESTED["MessageReactions"] = {
    "message": {"field": 1, "fields": "OtherMessage"},
    "reactions": {"field": 2, "fields": "Reaction", "repeated": True},
}

# ---------- اسکیمای پاسخ ----------
# {نام متد: {نام فیلد: قاعده}}
RESPONSES: dict[str, dict[str, object]] = {
    "AddContact": {"seq": 1, "date": 2},
    "BlockUser": {"seq": 1, "date": 2},
    "ClearChat": {"seq": 1, "date": 2},
    "CreateGroup": {"group": {"field": 3, "fields": "Group"}, "users": {"field": 5, "fields": "ShortPeer", "repeated": True}, "not_added_users": {"field": 6, "fields": "ShortPeer", "repeated": True}, "invite_link": 7},
    "DeleteChat": {"seq": 1, "date": 2},
    "DeleteMessage": {"seq": 1, "date": 2},
    "EditAbout": {"seq": 1, "date": 2},
    "EditChannelNick": {"seq": 1, "date": 2},
    "EditGroupAbout": {"seq": 1, "date": 2},
    "EditGroupTitle": {"seq": 1, "date": 2},
    "EditName": {"seq": 1, "date": 2},
    "EditNickName": {"seq": 1, "date": 2},
    "EditParameter": {"seq": 1, "date": 2},
    "EditUserLocalName": {"seq": 1, "date": 2},
    "ForwardMessages": {"seq": 1, "date": 2},
    "GetBannedUsers": {"users": {"field": 3, "fields": "BanData", "repeated": True}},
    "GetContacts": {"users": {"field": 1, "fields": "InfoPeer", "repeated": True}},
    "GetFullGroup": {"fullgroup": 1},
    "GetGroupInviteURL": {"url": 1},
    "GetGroupPreview": {"fullgroup": 1},
    "GetMemberPermissions": {"permissions": {"field": 1, "fields": "Permissions"}},
    "GetMessageReactionsList": {"data": 1},
    "GetMessagesReactions": {"messages": {"field": 1, "fields": "MessageReaction", "repeated": True}},
    "GetMessagesViews": {"messages": {"field": 1, "fields": "MessageViews", "repeated": True}},
    "GetMyKifpools": {"wallet": {"field": 1, "fields": "Wallet"}, "first_name": 2, "last_name": 3},
    "GetNasimFileUrl": {"file_urls": {"field": 1, "fields": "FileURL", "repeated": True}},
    "GetParameters": {"params": 1},
    "GetPins": {"pins_data": {"field": 1, "fields": "MessageData", "repeated": True}, "count": 2},
    "ImportContacts": {"peers": {"field": 4, "fields": "InfoPeer", "repeated": True}},
    "InviteUsers": {"not_added_users": {"field": 1, "fields": "Peer", "repeated": True}},
    "KickUser": {"seq": 1, "date": 2},
    "LeaveGroup": {"seq": 1, "date": 2},
    "LoadBlockedUsers": {"users": {"field": 1, "fields": "InfoPeer", "repeated": True}},
    "LoadDialogs": {"dialogs": {"field": 3, "fields": "PeerData", "repeated": True}},
    "LoadHistory": {"data": {"field": 1, "fields": "MessageData", "repeated": True}},
    "LoadPinnedMessages": {"data": {"field": 1, "fields": "MessageData", "repeated": True}},
    "LoadUsers": {"data": {"field": 1, "fields": "User", "repeated": True}},
    "MakeUserAdmin": {"seq": 1, "date": 2},
    "MessageRead": {"seq": 1, "date": 2},
    "MessageRemoveReaction": {"reactions": {"field": 2, "fields": "Reaction", "repeated": True}},
    "MessageSetReaction": {"reactions": {"field": 2, "fields": "Reaction", "repeated": True}},
    "PinMessage": {"seq": 1, "date": 2},
    "RemoveContact": {"seq": 1, "date": 2},
    "RemovePin": {"seq": 1, "date": 2},
    "RemoveSinglePin": {"seq": 1, "date": 2},
    "RemoveUserAdmin": {"seq": 1, "date": 2},
    "ReportInappropriateContent": {"seq": 1, "date": 2},
    "ResetContacts": {"seq": 1, "date": 2},
    "RevokeInviteURL": {"url": 1},
    "RevokeUpvotedPost": {"upvote": 1},
    "SendGiftPacketWithWallet": {"seq": 1, "date": 2},
    "SendMessage": {"seq": 1, "date": 2},
    "SetGroupDefaultPermissions": {"seq": 1, "date": 2},
    "SetMemberPermissions": {"seq": 1, "date": 2},
    "SetOnline": {"seq": 1, "date": 2},
    "SetRestriction": {"seq": 1, "date": 2},
    "SignOut": {"seq": 1, "date": 2},
    "StopTyping": {"seq": 1, "date": 2},
    "TransferOwnership": {"seq": 1, "date": 2},
    "Typing": {"seq": 1, "date": 2},
    "UnBanUser": {"seq": 1, "date": 2},
    "UnPinMessages": {"seq": 1, "date": 2},
    "UnblockUser": {"seq": 1, "date": 2},
    "UpdateMessage": {"seq": 1, "date": 2},
    "UpvotePost": {"upvote": 1},
}

# ---------- سرویس‌ها ----------
SERVICES: dict[str, str] = {
    "MESSAGING": "bale.messaging.v2.Messaging",
    "AUTH": "bale.auth.v1.Auth",
    "USER": "bale.users.v1.Users",
    "PRESENCE": "bale.presence.v1.Presence",
    "REPORT": "bale.report.v1.Report",
    "CONFIGS": "bale.v1.Configs",
    "ABACUS": "bale.abacus.v1.Abacus",
    "GROUPS": "bale.groups.v1.Groups",
    "FILES": "ai.bale.server.Files",
    "GIFT_PACKET": "bale.giftpacket.v1.GiftPacket",
    "KIFPOOL": "bale.kifpool.v1.Kifpool",
    "MAGAZINE": "bale.magazine.v1.Magazine",
}

# ---------- متدها ----------
# (service_key, method, {نام فیلد: قاعده}, doc, dangerous, needs_peer)
METHODS: list[tuple[str, str, dict[str, object], str, bool, bool]] = [
    # ===== ABACUS =====
    ("ABACUS", "GetMessageReactionsList", {"peer": {"field": 1, "fields": "Peer"}, "message_id": 2, "date": 3, "emojy": 4, "page": 5, "limit": 6}, "لیست کسانی که واکنش دادند", False, True),
    ("ABACUS", "GetMessagesReactions", {"peer": {"field": 1, "fields": "Peer"}, "message_ids": {"field": 2, "fields": "OtherMessage", "repeated": True}, "origin_peer": {"field": 3, "fields": "Peer"}, "origin_message_ids": {"field": 4, "fields": "OtherMessage", "repeated": True}}, "واکنش‌های چند پیام", False, True),
    ("ABACUS", "GetMessagesViews", {"peer": {"field": 1, "fields": "Peer"}, "message_ids": {"field": 2, "fields": "OtherMessage", "repeated": True}}, "تعداد بازدید پیام", False, True),
    ("ABACUS", "MessageRemoveReaction", {"peer": {"field": 1, "fields": "Peer"}, "message_id": 2, "emojy": 3, "date": 4}, "برداشتن واکنش", False, True),
    ("ABACUS", "MessageSetReaction", {"peer": {"field": 1, "fields": "Peer"}, "message_id": 2, "emojy": 3, "date": 4}, "گذاشتن واکنش", False, True),
    # ===== AUTH =====
    ("AUTH", "SignOut", {}, "خروج", True, False),
    ("AUTH", "SignUp", {"transaction_hash": 1, "name": 2}, "ثبت‌نام", False, False),
    ("AUTH", "StartPhoneAuth", {"phone_number": 1, "app_id": 2, "app_key": 3, "device_hash": 4, "device_title": 5, "send_code_type": 9, "options": 10}, "شروع ورود با شماره", False, False),
    ("AUTH", "ValidateCode", {"transaction_hash": 1, "code": 2, "is_jwt": 3}, "تأیید کد SMS", False, False),
    ("AUTH", "ValidatePassword", {"transaction_hash": 1, "password": 2, "is_jwt": 3}, "تأیید رمز دومرحله‌ای", False, False),
    # ===== CONFIGS =====
    ("CONFIGS", "EditParameter", {"key": 1, "value": {"field": 2, "fields": "StringValue"}}, "تغییر تنظیمات سرور", True, False),
    ("CONFIGS", "GetParameters", {}, "خواندن تنظیمات سرور", False, False),
    # ===== FILES =====
    ("FILES", "GetNasimFileUploadUrl", {"expected_size": 1, "user_id": 3, "name": 4, "mime_type": 5, "chat": {"field": 6, "fields": "Chat"}, "send_type": 7}, "گرفتن URL آپلود فایل", False, False),
    ("FILES", "GetNasimFileUrl", {"file": {"field": 1, "fields": "FileInfo"}}, "گرفتن URL دانلود فایل", False, False),
    # ===== GIFT_PACKET =====
    ("GIFT_PACKET", "OpenGiftPacket", {"message": {"field": 1, "fields": "InfoMessage"}, "receiver_token": 2, "page_no": 3, "order_type": 4}, "باز کردن بسته هدیه", False, False),
    ("GIFT_PACKET", "SendGiftPacketWithWallet", {"peer": {"field": 1, "fields": "Peer"}, "random_id": 2, "gift": {"field": 3, "fields": "GiftPacket"}, "token": 4}, "ارسال هدیه از کیف پول", True, False),
    # ===== GROUPS =====
    ("GROUPS", "CreateGroup", {"random_id": 1, "title": 2, "users": {"field": 3, "fields": "ShortPeer", "repeated": True}, "group_type": 6, "username": {"field": 8, "fields": "StringValue"}, "restriction": 9}, "ساخت گروه/کانال", False, True),
    ("GROUPS", "EditChannelNick", {"group": {"field": 1, "fields": "ShortPeer"}, "username": 2, "random_id": 3}, "تغییر یوزرنیم کانال", False, True),
    ("GROUPS", "EditGroupAbout", {"group": {"field": 1, "fields": "ShortPeer"}, "random_id": 2, "about": {"field": 3, "fields": "StringValue"}}, "تغییر توضیحات گروه", False, True),
    ("GROUPS", "EditGroupTitle", {"group": {"field": 1, "fields": "ShortPeer"}, "title": 3, "random_id": 4}, "تغییر نام گروه", False, True),
    ("GROUPS", "GetBannedUsers", {"group": {"field": 1, "fields": "ShortPeer"}}, "لیست کاربران مسدود", False, True),
    ("GROUPS", "GetFullGroup", {"group": {"field": 1, "fields": "ShortPeer"}}, "اطلاعات کامل گروه", False, True),
    ("GROUPS", "GetGroupInviteURL", {"group": {"field": 1, "fields": "ShortPeer"}}, "ساخت لینک دعوت", False, True),
    ("GROUPS", "GetGroupPreview", {"token": 1}, "پیش‌نمایش گروه با لینک", False, True),
    ("GROUPS", "GetMemberPermissions", {"group": {"field": 1, "fields": "ShortPeer"}, "user": {"field": 2, "fields": "ShortPeer"}}, "دسترسی‌های عضو", False, True),
    ("GROUPS", "GetPins", {"group": {"field": 1, "fields": "ShortPeer"}, "page": 2, "limit": 3}, "لیست سنجاق‌ها", False, True),
    ("GROUPS", "InviteUsers", {"group": {"field": 1, "fields": "ShortPeer"}, "random_id": 2, "users": {"field": 3, "fields": "ShortPeer", "repeated": True}}, "دعوت کاربران", False, True),
    ("GROUPS", "JoinGroup", {"token": 1}, "ورود با لینک دعوت", False, True),
    ("GROUPS", "JoinPublicGroup", {"peer": {"field": 1, "fields": "Peer"}}, "ورود به گروه عمومی", False, True),
    ("GROUPS", "KickUser", {"group": {"field": 1, "fields": "ShortPeer"}, "random_id": 2, "user": {"field": 3, "fields": "ShortPeer"}}, "اخراج کاربر", True, True),
    ("GROUPS", "LeaveGroup", {"group": {"field": 1, "fields": "ShortPeer"}, "random_id": 2}, "ترک گروه", True, True),
    ("GROUPS", "LoadMembers", {"group": {"field": 1, "fields": "ShortPeer"}, "limit": 2, "next_offset": {"field": 3, "fields": "StringValue"}, "condition": {"field": 4, "fields": "Condition"}}, "لیست اعضا", False, True),
    ("GROUPS", "MakeUserAdmin", {"group": {"field": 1, "fields": "ShortPeer"}, "user": {"field": 2, "fields": "ShortPeer"}, "admin_name": {"field": 3, "fields": "StringValue"}}, "ادمین کردن کاربر", False, True),
    ("GROUPS", "PinMessage", {"group": {"field": 2, "fields": "ShortPeer"}, "date": 3, "message_id": 4}, "سنجاق پیام", False, True),
    ("GROUPS", "RemovePin", {"group": {"field": 1, "fields": "ShortPeer"}}, "حذف سنجاق", False, True),
    ("GROUPS", "RemoveSinglePin", {"group": {"field": 1, "fields": "ShortPeer"}, "message_id": 2, "date": 3}, "حذف یک سنجاق", False, True),
    ("GROUPS", "RemoveUserAdmin", {"group": {"field": 1, "fields": "ShortPeer"}, "user": {"field": 2, "fields": "ShortPeer"}}, "حذف ادمین", True, True),
    ("GROUPS", "RevokeInviteURL", {"group": {"field": 1, "fields": "ShortPeer"}}, "ابطال لینک دعوت", False, True),
    ("GROUPS", "SetGroupDefaultPermissions", {"group": {"field": 1, "fields": "ShortPeer"}, "permissions": {"field": 2, "fields": "Permissions"}}, "دسترسی پیش‌فرض گروه", False, True),
    ("GROUPS", "SetMemberPermissions", {"group": {"field": 1, "fields": "ShortPeer"}, "user": {"field": 2, "fields": "ShortPeer"}, "permissions": {"field": 3, "fields": "Permissions"}}, "تنظیم دسترسی عضو", False, True),
    ("GROUPS", "SetRestriction", {"group": {"field": 1, "fields": "ShortPeer"}, "restriction": 2, "username": {"field": 3, "fields": "StringValue"}}, "تعیین عمومی/خصوصی", True, True),
    ("GROUPS", "TransferOwnership", {"group": {"field": 1, "fields": "ShortPeer"}, "new_owner": 2}, "انتقال مالکیت", True, True),
    ("GROUPS", "UnBanUser", {"group": {"field": 1, "fields": "ShortPeer"}, "user": {"field": 2, "fields": "ShortPeer"}}, "رفع مسدودی کاربر", False, True),
    # ===== KIFPOOL =====
    ("KIFPOOL", "GetMyKifpools", {}, "کیف‌پول‌های من", False, False),
    # ===== MAGAZINE =====
    ("MAGAZINE", "GetMessageUpvoters", {"load_more_state": {"field": 1, "fields": "StringValue"}, "message": {"field": 2, "fields": "InfoMessage"}}, "لیست لایک‌کنندگان", False, False),
    ("MAGAZINE", "RevokeUpvotedPost", {"message": {"field": 1, "fields": "InfoMessage"}, "album_id": {"field": 2, "fields": "IntValue"}}, "برداشتن لایک", False, False),
    ("MAGAZINE", "UpvotePost", {"message": {"field": 1, "fields": "InfoMessage"}, "album_id": {"field": 2, "fields": "IntValue"}}, "لایک پست مجله", False, False),
    # ===== MESSAGING =====
    ("MESSAGING", "ClearChat", {"peer": {"field": 1, "fields": "Peer"}}, "پاک کردن تاریخچه چت", True, True),
    ("MESSAGING", "DeleteChat", {"peer": {"field": 1, "fields": "Peer"}}, "حذف کامل چت", True, True),
    ("MESSAGING", "DeleteMessage", {"peer": {"field": 1, "fields": "Peer"}, "message_ids": 2, "dates": {"field": 3, "fields": "IntListValue"}, "just_me": {"field": 4, "fields": "IntValue"}}, "حذف پیام", True, True),
    ("MESSAGING", "ForwardMessages", {"peer": {"field": 1, "fields": "Peer"}, "message_ids": 2, "forwarded_messages": {"field": 3, "fields": "InfoMessage", "repeated": True}}, "فوروارد پیام", False, True),
    ("MESSAGING", "LoadDialogs", {"offset_date": 1, "limit": 2, "exclude_pinned": 5}, "لیست گفتگوها", False, True),
    ("MESSAGING", "LoadHistory", {"peer": {"field": 1, "fields": "Peer"}, "offset_date": 2, "load_mode": 4, "limit": 5}, "خواندن تاریخچه پیام‌ها", False, True),
    ("MESSAGING", "LoadPinnedMessages", {"peer": {"field": 1, "fields": "Peer"}}, "پیام‌های سنجاق‌شده", False, True),
    ("MESSAGING", "MessageRead", {"peer": {"field": 1, "fields": "Peer"}, "date": 2}, "علامت‌گذاری خوانده‌شده", False, True),
    ("MESSAGING", "PinMessage", {"peer": {"field": 1, "fields": "Peer"}, "message": {"field": 2, "fields": "OtherMessage"}, "just_me": {"field": 3, "fields": "IntBool"}}, "سنجاق پیام", False, True),
    ("MESSAGING", "SendMessage", {"peer": {"field": 1, "fields": "Peer"}, "message_id": 2, "content": {"field": 3, "fields": "MessageContent"}, "reply_to": {"field": 5, "fields": "InfoMessage"}, "chat": {"field": 6, "fields": "Chat"}}, "ارسال پیام (متن/فایل/ربات)", False, True),
    ("MESSAGING", "UnPinMessages", {"peer": {"field": 1, "fields": "Peer"}, "messages": {"field": 2, "fields": "OtherMessage", "repeated": True}, "all_messages": {"field": 3, "fields": "IntBool"}}, "برداشتن سنجاق", False, True),
    ("MESSAGING", "UpdateMessage", {"peer": {"field": 1, "fields": "Peer"}, "message_id": 2, "updated_message": {"field": 3, "fields": "MessageContent"}}, "ویرایش پیام", False, True),
    # ===== PRESENCE =====
    ("PRESENCE", "SetOnline", {"is_online": {"field": 1, "fields": "IntBool"}, "timeout": 2}, "اعلام آنلاین", False, True),
    ("PRESENCE", "StopTyping", {"peer": {"field": 1, "fields": "Peer"}, "typing_type": 2}, "توقف تایپ", False, True),
    ("PRESENCE", "Typing", {"peer": {"field": 1, "fields": "Peer"}, "typing_type": 3}, "شروع تایپ", False, True),
    # ===== REPORT =====
    ("REPORT", "ReportInappropriateContent", {"report_body": {"field": 1, "fields": "Report"}}, "گزارش محتوای نامناسب", True, False),
    # ===== USER =====
    ("USER", "AddContact", {"user_id": 1, "type": 2}, "افزودن مخاطب", False, False),
    ("USER", "BlockUser", {"peer": {"field": 1, "fields": "InfoPeer"}}, "مسدود کردن کاربر", True, False),
    ("USER", "CheckNickName", {"nick_name": 1}, "بررسی آزاد بودن یوزرنیم", False, False),
    ("USER", "EditAbout", {"about": {"field": 1, "fields": "StringValue"}}, "تغییر بیو", False, False),
    ("USER", "EditName", {"name": 1}, "تغییر نام", False, False),
    ("USER", "EditNickName", {"nick_name": {"field": 1, "fields": "StringValue"}}, "تغییر نام نمایشی", False, False),
    ("USER", "EditUserLocalName", {"user_id": 1, "access_hash": 2, "name": 3}, "نام محلی مخاطب", False, False),
    ("USER", "GetContacts", {}, "لیست مخاطبین", False, False),
    ("USER", "ImportContacts", {"phones": {"field": 1, "fields": "ContactData", "repeated": True}}, "ورود دسته‌ای مخاطبین", False, False),
    ("USER", "LoadBlockedUsers", {}, "لیست مسدودشده‌ها", False, False),
    ("USER", "LoadFullUsers", {"peers": {"field": 1, "fields": "InfoPeer", "repeated": True}}, "اطلاعات کامل کاربران", False, False),
    ("USER", "LoadUsers", {"peers": {"field": 1, "fields": "InfoPeer", "repeated": True}}, "اطلاعات کاربران", False, False),
    ("USER", "RemoveContact", {"user_id": 1, "type": 2}, "حذف مخاطب", False, False),
    ("USER", "ResetContacts", {}, "پاک کردن همه مخاطبین", True, False),
    ("USER", "SearchContacts", {"request": 1}, "جستجوی مخاطب", False, False),
    ("USER", "UnblockUser", {"peer": {"field": 1, "fields": "InfoPeer"}}, "رفع مسدودی", False, False),
]
