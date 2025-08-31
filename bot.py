import os, json, time
from dotenv import load_dotenv
import vk_api
import time
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

load_dotenv()
TOKEN = os.getenv("GROUP_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))  # можно не указывать, если знаете id
YANDEX_EDA_LINK = os.getenv("YANDEX_EDA_LINK", "https://eda.yandex.ru")
VK_CONTEST_POST_URL = os.getenv("VK_CONTEST_POST_URL", "https://vk.com")

session = vk_api.VkApi(token=TOKEN, api_version='5.199')
vk = session.get_api()
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
longpoll = VkBotLongPoll(session, int(os.getenv("GROUP_ID")))
send = lambda **p: vk.messages.send(random_id=0, **p)
HANDOFF_COOLDOWN = 60  # секунд

# ---------- keyboards ----------
def kb(rows, inline=False, one_time=False):
    def btn(b):
        if b.get("type") == "open_link":
            return {
                "action": {
                    "type": "open_link",
                    "link": b["link"],
                    "label": b["text"]
                }
            }
        else:
            return {
                "action": {
                    "type": "text",
                    "label": b["text"],
                    "payload": json.dumps({"cmd": b.get("payload", b["text"])}, ensure_ascii=False)
                },
                "color": b.get("color", "primary")
            }
    return json.dumps({
        "one_time": one_time,
        "inline": inline,
        "buttons": [[btn(b) for b in row] for row in rows]
    }, ensure_ascii=False)


MAIN_KB = kb([
    [ {"text":"🥗 Заказать через Яндекс Еду", "type":"open_link", "link": os.getenv("YANDEX_EDA_LINK")},
      {"text":"💸 Скидки и акции", "payload":"deals"} ],
    [ {"text":"🎁 Участвовать в конкурсе", "payload":"contest"},
      {"text":"🍴 Подробнее о блюдах", "payload":"about"} ]
])

BACK_KB = kb([
    [ {"text":"🥗 Заказать через Яндекс Еду", "type":"open_link", "link": os.getenv("YANDEX_EDA_LINK")}]
])

MORE_KB = kb([
    [ {"text":"🔥Да, хочу знать больше", "payload":"about_next"} ],
    [ {"text":"🥗 Заказать через Яндекс Еду", "type":"open_link", "link": os.getenv("YANDEX_EDA_LINK")},
      {"text":"💸 Скидки и акции", "payload":"deals"} ],
    [ {"text":"🎁 Участвовать в конкурсе", "payload":"contest"} ]
])

FINAL_KB = kb([
    [ {"text":"🥗 Заказать через Яндекс Еду", "type":"open_link", "link": os.getenv("YANDEX_EDA_LINK")} ],
    [ {"text":"💸 Скидки и акции", "payload":"deals"},
      {"text":"🎁 Участвовать в конкурсе", "payload":"contest"} ],
    [ {"text":"↩️ Меню", "payload":"menu"} ]
])

# ---------- state ----------
STATE = {}  # user_id -> {"about_step": int, "welcomed": bool}
def reset(uid):
    STATE[uid] = {"about_step": 0, "welcomed": False, "last_handoff": 0.0}

# ---------- texts ----------
GREET = (
    "👋 Привет! Рады, что ты заглянул к нам.\n"
    "Очень хочется, чтобы здесь тебе было вкусно и приятно.\n\n"
    "Большой салат — это блюда как маленькие путешествия. "
    "Франция, Аргентина, Скандинавия — каждая страна в одной порции.\n\n"
    "А еще Большой салат это:\n"
    "⭐ Топ ресторан Яндекс Еды\n"
    "⭐ Рейтинг 4,8 (на основании 200+ отзывов).\n"
    "А в каждой упаковке — маленький кусочек культуры: музыка, фильм или классный рецепт.\n\n"
    "Что тебе интересно прямо сейчас?"
)

DEALS = (
    "Не только вкусно, но и выгодно!\n"
    "Сейчас на Яндекс Еде действует скидка −20% на любой заказ из «Большого салата».\n\n"
    "Промокод: SALE20\n"
    "Просто введи его при оформлении заказа, и ужин или обед станет ещё вкуснее.\n\n"
    "Хочешь перейти к заказу прямо сейчас?"
)

HUMAN_HANDOFF = (
    "Мы получили твоё сообщение и скоро на него ответим!"
)

CONTEST = (
    "🎁 У нас идёт розыгрыш!\n\n"
    "Мы дарим 2 блюда и 2 напитка в подарок с доставкой 🚚\n"
    "С тебя — только лайк и комментарий! И вкусный ужин из блюд, вдохновлённых разными странами нашей планеты, может быть твоим.\n\n"
    "Принять участие очень просто:\n"
    "1. Нужно подписаться на наше сообщество «Большой салат»\n"
    "2. Поставить лайк и написать комментарий «участвую» к посту с конкурсом\n"
    "3. Дождаться итогов 10 сентября\n\n"
    "Итоги объявим прямо здесь. Хочешь перейти к посту и участвовать?"
)

ABOUT_STEPS = [
    ("🍴 Салаты у нас — это не гарнир, а полноценный приём пищи.\n"
     "Каждое блюдо — баланс зелени, белков и углеводов. "
     "Сытные боулы и салаты, вдохновленные разными уголками мира — это вкус, который перенесёт тебя в небольшое путешествие.\n\n"
     "Не терпится рассказать о популярных блюдах подробнее:\n"
     "🌧️ Боул «Гроза Сицилии» — яркий, как улицы Палермо после дождя. "
     "Сочный, с пастой, курицей, нутом, томатами, руколой и мини-моцареллой — соединяет свежесть овощей с плотным южным вкусом. "
     "Это Сицилия без фильтров: чуть дерзкая, немного резкая, но настоящая.\n\n"
     "🥇 Салат «Цезарь» — классика, выполненная со вкусом. Много курицы. "
     "Хрустящий романо, куриный ростбиф, черри, чиабатта и пармезан под нежным соусом — простой, как импровизация, и точный, как легенда.\n\n"
     "Продолжим?"),
    ("Отлично, рассказываем о следующих двух любимчиках.\n"
     "🗼Боул «Сен-Реми» — нежный боул, как полдень в Провансе. "
     "Тёплая киноа, куриный ростбиф, чечевица, брокколи, пармезан и дижонская заправка — боул, где соединились уют, природа и французская гастрономия.\n\n"
     "🥬 Салат «Буэнос Диас» — аргентинское утро в каждом ингредиенте: шпинат, яйцо, курица, вяленые томаты, тёртая моцарелла, орехи кешью и пикантная заправка чимичурри. "
     "Сытно, ярко, по-южному — чтобы день точно задался.\n\n"
     "Продолжим?"),
    ("Отлично, рассказываем о следующих двух любимчиках.\n"
     "Боул «По воскресеньям в Ла-Боке» — как прогулка по яркому кварталу: фарш, цветная капуста, морковь, салат, томаты и чимичурри. "
     "Уличный дух Буэнос-Айреса в дерзком, сочном боуле — для тех, кто любит по-настоящему.\n\n"
     "Салат «Скандинавия» — свежесть северного сада: шпинат, красные яблоки, козий сыр, паста-ракушки и вяленые томаты со специями. "
     "Лёгкий, хрустящий, сбалансированный — как скандинавский дизайн, только на вкус."),
    ("Отлично, рассказываем о следующих двух любимчиках.\n"
     "Боул «7/11» — тайский стритфуд в тарелке: креветки, манго, фунчоза, эдамаме, кешью, лайм и свежая кинза. "
     "Ярко, сочно, остро — будто собрали прямо на рынке в Бангкоке.\n\n"
     "Салат «Malina de Прованс» — французская нежность: руккола, шпинат, козий сыр, ялтинский лук, малиновая заправка и лепестки миндаля. "
     "Салат для тех, кто выбирает вкус вместо суеты.\n\n"
     "Что ты хочешь заказать сегодня? Выберем подходящие блюда под твоё настроение в Яндекс Еде?\n\n"
     "По промокоду SALE20 ты получишь скидку 20% на любой заказ!")
]

# ---------- handlers ----------
def show_menu(user_id):
    if user_id not in STATE:
        reset(user_id)
    STATE[user_id]["welcomed"] = True
    send(user_id=user_id, message=GREET, keyboard=MAIN_KB)

def handle_order(user_id):
    send(user_id=user_id, message=f"🥗 Заказать через Яндекс Еду:\n{YANDEX_EDA_LINK}", keyboard=BACK_KB)

def handle_deals(user_id):
    send(user_id=user_id, message=DEALS, keyboard=kb([
        [ {"text":"🥗 Заказать через Яндекс Еду", "type":"open_link", "link": os.getenv("YANDEX_EDA_LINK")} ],
        [ {"text":"🎁 Участвовать в конкурсе", "payload":"contest"},
          {"text":"🍴 Подробнее о блюдах", "payload":"about"} ]
    ]))

def handle_contest(user_id):
    send(user_id=user_id, message=f"{CONTEST}\n\nСсылка: {VK_CONTEST_POST_URL}", keyboard=kb([
        [ {"text":"🎁 Перейти к посту", "payload":"contest_go"} ],
        [ {"text":"🥗 Заказать через Яндекс Еду", "type":"open_link", "link": os.getenv("YANDEX_EDA_LINK")},
          {"text":"💸 Скидки и акции", "payload":"deals"} ]
    ]))

def is_known_command(text: str) -> bool:
    if not text:
        return False
    low = text.strip().lower()
    known = {
        "menu","меню","/start","start","начать","привет",
        "order","перейти в яндекс еду","🥗 заказать через яндекс еду","🥗 перейти в яндекс еду",
        "deals","скидки","акции","💸 скидки и акции","💸 скидки",
        "contest","🎁 участвовать в конкурсе","contest_go","перейти к посту","🎁 перейти к посту",
        "about","🍴 подробнее о блюдах","about_next","да, хочу знать больше"
    }
    return low in known

def handle_about(user_id, next_step=False):
    STATE.setdefault(user_id, {"about_step": 0})
    if next_step:
        STATE[user_id]["about_step"] = min(STATE[user_id]["about_step"] + 1, len(ABOUT_STEPS)-1)
    step = STATE[user_id]["about_step"]
    text = ABOUT_STEPS[step]
    kb_use = MORE_KB if step < len(ABOUT_STEPS)-1 else FINAL_KB
    send(user_id=user_id, message=text, keyboard=kb_use)

def route_text(user_id, text_or_payload):
    t = (text_or_payload or "").strip()
    # кнопки присылают label, поэтому сравниваем по payload (cmd)
    low = t.lower()

    # Главное меню
    if low in ("menu","↩️ меню","начать","/start","start","привет"):
        show_menu(user_id); return

    # Переходы
    if low in ("order","🥗 заказать через яндекс еду","🥗 перейти в яндекс еду","перейти в яндекс еду"):
        handle_order(user_id); return
    if low in ("deals","💸 скидки и акции","скидки","акции"):
        handle_deals(user_id); return
    if low in ("contest","🎁 участвовать в конкурсе"):
        handle_contest(user_id); return
    if low in ("contest_go","🎁 перейти к посту","перейти к посту"):
        send(user_id=user_id, message=f"Ссылка на пост: {VK_CONTEST_POST_URL}", keyboard=BACK_KB); return
    if low in ("about","🍴 подробнее о блюдах"):
        STATE[user_id] = {"about_step": 0}; handle_about(user_id, next_step=False); return
    if low in ("about_next","да, хочу знать больше"):
        handle_about(user_id, next_step=True); return

    # Фолбэк — показать меню
    show_menu(user_id)

# ---------- main loop ----------
if __name__ == "__main__":
    print("VK bot is running…")
    while True:
        try:
            for event in longpoll.listen():

                # 1) Входящее сообщение от пользователя
                if event.type == VkBotEventType.MESSAGE_NEW and event.from_user:
                    message = event.obj.message
                    user_id = message["from_id"]
                    payload_raw = message.get("payload")
                    text = (message.get("text") or "").strip()

                    # инициализация состояния
                    if user_id not in STATE:
                        reset(user_id)

                    # 1.1 системная кнопка «Начать» (payload {"command":"start"})
                    if payload_raw:
                        try:
                            data = json.loads(payload_raw)
                            if data.get("command") == "start":
                                show_menu(user_id)
                                continue
                            cmd = data.get("cmd")
                            if cmd:
                                route_text(user_id, cmd)
                                continue
                        except Exception:
                            pass

                    # 1.2 Первое касание: любое сообщение -> приветствие и стоп
                    if not STATE[user_id]["welcomed"]:
                        show_menu(user_id)
                        continue

                    # 1.3 Уже приветствовали: если это наша команда — обычный роутинг
                    if is_known_command(text):
                        route_text(user_id, text)
                        continue

                    # 1.4 Иначе — «свободный текст» вне сценария: автоответ с кулдауном
                    now = time.time()
                    last = STATE[user_id].get("last_handoff", 0)
                    if now - last >= HANDOFF_COOLDOWN:
                        send(user_id=user_id, message=HUMAN_HANDOFF)
                        STATE[user_id]["last_handoff"] = now

                # 2) Разрешение на сообщения (message_allow) => приветствие
                if event.type == VkBotEventType.MESSAGE_ALLOW:
                    uid = event.obj["user_id"]
                    show_menu(uid)
                    continue

                # 3) Подписка на сообщество (group_join) => приветствие
                if event.type == VkBotEventType.GROUP_JOIN:
                    uid = event.obj["user_id"]
                    show_menu(uid)
                    continue

        except Exception as e:
            print("Error:", e)
            time.sleep(2)

