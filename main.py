import os
import asyncio
import random
import time
import requests
from datetime import datetime
from telethon import TelegramClient, events
from dotenv import load_dotenv
load_dotenv()

# ========== CONFIG ==========
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

SESSION_NAME = "session"

START_NEW_CHAT = False          # True → бот сам напишет первой новой девушке
NEW_CHAT_USERNAME = "kjiuyv"          # username девушки (без @)

# ============================

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

dialogs = {}

def allowed_time():
    h = datetime.now().hour
    return (10 <= h <= 13) or (17 <= h <= 21)

def get_dialog(uid):
    if uid not in dialogs:
        dialogs[uid] = {
            "stage": "start",
            "interest": 0,
            "last_incoming": time.time(),
            "last_outgoing": 0,
            "pings_sent": 0
        }
    return dialogs[uid]

CRINGE = ["маск", "глуб", "раскры", "шаг", "под поверх"]

def is_cringe(text):
    return any(x in text.lower() for x in CRINGE)

def llm(prompt):
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты живой парень 21–23 лет. Пишешь как в Telegram. "
                        "Коротко, спокойно, без философии. "
                        "Флирт лёгкий. Вопросы — только если реально уместно."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 120
        },
        timeout=30
    )
    return r.json()["choices"][0]["message"]["content"].strip()

def build_prompt(text, stage):
    return f"""
Сообщение девушки:
"{text}"

Стадия: {stage}

Ответь:
- 1–2 предложения
- естественно
- без философии
- максимум 1 простой вопрос
"""

def generate_reply(text, dialog):
    for _ in range(3):
        reply = llm(build_prompt(text, dialog["stage"]))
        if not is_cringe(reply):
            return reply
    return "Понял 🙂"

def update_stage(dialog, text):
    if len(text) > 15:
        dialog["interest"] += 1
    if dialog["interest"] >= 4:
        dialog["stage"] = "interest"
    elif dialog["interest"] >= 2:
        dialog["stage"] = "talk"

FIRST_MESSAGES = [
    "Привет 🙂 решил написать — как день проходит?",
    "Привет! Надеюсь, не отвлекаю. Чем сегодня занята?",
    "Привет 🙂 показалась интересной, решил написать"
]

async def start_new_chat():
    if START_NEW_CHAT and NEW_CHAT_USERNAME and allowed_time():
        await client.send_message(
            NEW_CHAT_USERNAME,
            random.choice(FIRST_MESSAGES)
        )
        print("✅ Первое сообщение отправлено")

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not event.is_private:
        return

    uid = event.sender_id
    text = event.text.strip()
    if not text:
        return

    dialog = get_dialog(uid)
    dialog["last_incoming"] = time.time()
    dialog["pings_sent"] = 0

    update_stage(dialog, text)

    await asyncio.sleep(random.uniform(5, 15))

    if not allowed_time():
        return

    reply = generate_reply(text, dialog)
    await event.respond(reply)

    dialog["last_outgoing"] = time.time()

async def auto_initiative():
    while True:
        await asyncio.sleep(600)
        if not allowed_time():
            continue

        now = time.time()
        for uid, d in dialogs.items():
            if d["stage"] == "start":
                continue
            if d["pings_sent"] >= 1:
                continue
            if now - d["last_incoming"] < 3600:
                continue
            if now - d["last_outgoing"] < 3600:
                continue

            msg = random.choice([
                "Кстати, вспомнил наш разговор 🙂",
                "Как у тебя сегодня день складывается?",
                "Надеюсь, день проходит спокойно 🙂"
            ])

            await client.send_message(uid, msg)
            d["last_outgoing"] = now
            d["pings_sent"] += 1

async def main():
    await client.start()
    await start_new_chat()
    asyncio.create_task(auto_initiative())
    print("🤖 Bot running 24/7")
    await client.run_until_disconnected()

asyncio.run(main())
