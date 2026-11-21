# Client API Correctness — Pagination, Message Parsing, Response Schema

> Date: 2026-11-21 · Version: 0.2.2
> Test status: **Mock/Offline** — no Live Verification is claimed.

This document describes the **predictable** behaviour of `iter_dialogs`, `iter_messages`
and message parsing. All field numbers come from **aiobale 0.3.9** source, which is a
**comparison source**, not proof of the official Bale protocol or live server behaviour.
Items requiring real traffic are explicitly marked `BLOCKED`.

---

## 1. `iter_dialogs(limit, batch)`

**RPC:** `messaging.LoadDialogs` · **Response:** `{3: [PeerData]}`

| Behaviour | Detail |
|---|---|
| First request | `offset_date=0`, `limit=batch` |
| Next cursor | `sortDate` of the last raw row (`PeerData.field 3`) — **never the row count** |
| Empty page / missing `dialogs` key | Safe end of iteration |
| Malformed row (non-dict) | Becomes `Dialog(peer=Peer(id=0))`; iteration continues |
| Duplicate dialog | Filtered by `(peer.type, peer.id)` |
| Server repeats cursor | Stops after two requests (no infinite loop) |
| Short page | **Not necessarily the end**; continues while cursor advances |
| `limit` | Honoured even if the server returns more rows |
| Network error / Timeout / Cancellation | Propagated to caller, never silently swallowed |

---

## 2. `iter_messages(ref, limit, batch, reverse)`

**RPC:** `messaging.LoadHistory` · **Response:** `{1: [MessageData]}`
**Request:** `LoadHistory{1: peer, 2: offset_date, 3: load_mode, 4: limit}` · `load_mode=2` (backward)

| Behaviour | Detail |
|---|---|
| First request | `offset_date=-1` |
| Next cursor | Oldest `date` in the page (`MessageData.field 3`) |
| Fully duplicate page | Does not stop early; cursor advances by one to break the cycle |
| `messageId=0` | Tagged with a global unique counter, not confused with other anonymous messages |
| Duplicate message across pages | Delivered once |
| `limit` | Honoured even if the server returns more rows |
| `reverse=True` | Page order flipped (older first) |
| Page boundary | No message lost or duplicated (dedicated test) |
| Network error / Timeout / Cancellation | Propagated to caller |

**Honest limitation:** the exact meaning of `offset_date` and the no-loss guarantee at page
boundaries are inferred from aiobale source, **not from live Bale server traffic** →
`NOT VERIFIED (Live)`.

---

## 3. Message Parsing

`MessageData` (aiobale 0.3.9): `senderId=1, messageId=2, date=3, content=4,
repliedTo=8, previousMessage=10, nextMessage=11, editedAt=12`.

`MessageContent` variants:

| Field | Number | Parsing |
|---|---|---|
| `text` | 15 | `TextMessage{1: value}` → `Message.text` |
| `document` | 4 | Caption (`caption.content`) or file name → `Message.text`; `media_info()` reads it |
| `serviceMessage` | 11 | `ServiceMessage{1: text, 2: ext}` → `Message.text`, `is_service=True` |
| `botMessage` | 13 | `TemplateMessage.message` → `Message.text` |
| `gift` | 17 | `GiftPacket.message` (`StringValue`) → `Message.text` |
| `empty` | 5 | `content_type="empty"`, `is_forwarded=True` |

Also: `repliedTo` → `reply_to_id`, `editedAt` → `is_edited`. Unknown content is **not dropped** —
it stays in `Message.raw`. Missing/`None`/incomplete fields get safe defaults, never fabricated
text. If no text can be extracted, `text=""`.

---

## 4. Dialog Parsing

`PeerData{1: peer, 2: unreadCount, 3: sortDate, 4: senderId, 5: messageId,
6: date, 7: content, 9: firstUnreadMessage, 13: unreadMentions}`.

`_parse_dialog` reads `peer.id`, `peer.type`, `peer.accessHash`, `peer.title`,
`peer.username`, `unreadCount`, `sortDate`/`date` and the last message. Fields absent from
the data are **not guessed**.

---

## 5. Response Schema — honest status

| Structure | Status | Source |
|---|---|---|
| `ServiceMessage{text:1, ext:2}` | IMPLEMENTED | aiobale 0.3.9 `service_message.py` |
| `ServiceExt{giftOpened:18}` | IMPLEMENTED | aiobale 0.3.9 `service_ext.py` |
| `GiftOpened{...}` | IMPLEMENTED | same |
| `GiftPacket{count:1, totalAmount:2, givingType:3, token:4(StringValue), message:5(StringValue), ownerId:6, showAmounts:7(BoolValue)}` | IMPLEMENTED | aiobale 0.3.9 `gift_packet.py` |
| Structured `repliedTo/previousMessage/nextMessage` | IMPLEMENTED | aiobale 0.3.9 `message_content.py` |
| Empty RPC response (`{seq, date}`) | No schema added on purpose — generic response | existing `RESPONSES` |

**Fixed bug:** `GiftPacket` was defined twice; the second (scalar) definition overrode the
accurate one and encoded `token`/`message`/`showAmounts` as scalars instead of wrappers.
The duplicate was removed. An AST check confirmed no other duplicate keys in `NESTED` /
`RESPONSES` / `SERVICES`.

Round-trip tests use real `encode_named` + `decode` with resolved schemas and check the binary
output (raw `decode` returns strings as `bytes` — correct wire-level behaviour).

---

## 6. Request Correlation

The internal Bale protocol does **not confirm a request ID**. Therefore:

- `stamp_req_id=False` is the default; guessing a req_id is forbidden.
- FIFO correlation is reliable **only for one connection with serial requests**.
- Out-of-order responses, late responses and updates between responses → **BLOCKED / NOT VERIFIED** without real traffic.
- Predictable current behaviour: requests are sent and consumed in order; no response is
  assigned to the wrong request unless the server breaks ordering (unconfirmed).

---

## 7. Inline Keyboard & Callback

- `make_inline_keyboard(rows)` builds `Markup{1:[Row{1:[Button]}]}` with
  `text=1, url=2(wrapped), callbackData=3(wrapped), copyText=9(wrapped)`.
- `send_message(..., reply_markup=...)` sends it from SelfBot.
- Backward compatible: a flat list of buttons is treated as one row.
- **Callback Query does not exist in SelfBot** — the internal protocol lacks it. Sending a
  `callbackData` button does not imply the SelfBot can receive callbacks. See
  `docs/SELF_INLINE_KEYBOARD.md`.

---

## 8. Limitations / BLOCKED

| Item | Status |
|---|---|
| Exact `offset_date` semantics / no-loss boundary guarantee on live server | NOT VERIFIED (Live) |
| Request Correlation with out-of-order responses | BLOCKED (needs real traffic) |
| Callback Query in SelfBot | BLOCKED (protocol lacks it) |
| Media Resume, JWT verification | NOT_IMPLEMENTED / BLOCKED (prior reports) |
| Live tests | SKIP — no authorized test account |

---

## 9. Tests

`tests/test_client_api_correctness.py` — 51 offline tests: multi-page pagination, page
boundaries, incomplete/malformed responses, duplicate messages, fully duplicate page,
`messageId=0`, limit, reverse, network error, timeout, cancellation, all content types,
dialog parsing, schema field numbers, binary round-trip.

Actual result: **1418 passed + 6 skipped** (full suite), exit 0. Mock PASS, not Live PASS.
