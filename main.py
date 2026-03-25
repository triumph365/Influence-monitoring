import os
import sys
import warnings
warnings.filterwarnings("ignore")
warnings.simplefilter("ignore")
if hasattr(sys, 'argv'):
    sys.argv[0] = os.path.basename(sys.argv[0])
if sys.platform == 'win32':
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')
import json
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from colorama import init, Fore, Back, Style
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import User, UserStatusOnline, UserStatusOffline, UserStatusRecently, MessageService
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetHistoryRequest, SearchRequest, GetCommonChatsRequest
from telethon.tl.types import InputMessagesFilterEmpty
init(autoreset=True)
class Colors:
    DARK_RED = Fore.RED
    BRIGHT_RED = Fore.LIGHTRED_EX
    GREEN = Fore.LIGHTGREEN_EX
    YELLOW = Fore.LIGHTYELLOW_EX
    BLUE = Fore.LIGHTBLUE_EX
    MAGENTA = Fore.LIGHTMAGENTA_EX
    CYAN = Fore.LIGHTCYAN_EX
    WHITE = Fore.LIGHTWHITE_EX
    GREY = Fore.LIGHTBLACK_EX
    RESET = Style.RESET_ALL
    BOLD = Style.BRIGHT
    DIM = Style.DIM
    NORMAL = Style.NORMAL
def get_ping_color(ping_ms):
    """Возвращает цвет в зависимости от пинга"""
    if ping_ms < 200:
        return Colors.GREEN
    elif ping_ms < 500:
        return Colors.YELLOW
    else:
        return Colors.BRIGHT_RED
async def measure_ping(client):
    """Измеряет пинг до Telegram (асинхронная функция)"""
    try:
        start = time.time()
        await client.get_me()
        ping = int((time.time() - start) * 1000)
        return ping
    except Exception as e:
        return 999
def censor_string(text, visible_chars=3):
    """Цензурирует строку, оставляя только первые и последние visible_chars символов"""
    if not text:
        return text
    text = str(text)
    if len(text) <= visible_chars * 2:
        return text
    dots_count = len(text) - visible_chars * 2
    return text[:visible_chars] + '.' * dots_count + text[-visible_chars:]
def censor_phone(phone):
    """Цензурирует номер телефона, оставляя только первые 3 и последние 2 цифры"""
    if not phone:
        return phone
    phone = str(phone)
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) <= 8:
        return phone
    return phone[:3] + '.' * (len(phone) - 5) + phone[-2:]
def make_link(label, url):
    return f"{Colors.CYAN}{label}:{Colors.RESET} {url}"
class Target:
    def __init__(self, user_id, name, username=None, last_photo_id=None):
        self.id = user_id
        self.name = name
        self.username = username
        self.messages = []
        self.last_photo_id = last_photo_id
        self.last_status = None
        self.last_bio = None
        self.last_phone = None
        self.last_stories_count = 0
        self.common_groups = []
        self.joined_groups = []
        self.left_groups = []
        self.message_times = []
        self.hourly_activity = {str(i): 0 for i in range(24)}
        self.daily_activity = {}
        self.deleted_messages = []
        self.known_message_ids = set()
        self.settings = {
            'track_messages': True,
            'track_profile_changes': True,
            'track_status': True,
            'track_deleted': True,
            'track_media': True,
            'track_bio': True,
            'track_phone': True,
            'track_stories': True
        }
        safe_name = name.replace('@', '').replace('/', '_').replace('\\', '_').replace(' ', '_')
        self.log_file = Path(f"logs/{safe_name}_{user_id}.txt")
        Path("logs").mkdir(exist_ok=True)
        self.write_line(f"=== Started monitoring {name} ===")
    def write_line(self, text):
        """Запись в файл без fsync для производительности"""
        with open(self.log_file, 'a', encoding='utf-8', buffering=1) as f:
            f.write(text + '\n')
    def save_log(self, log_line):
        self.messages.append(log_line)
        if len(self.messages) > 1000:
            self.messages = self.messages[-1000:]
        self.write_line(log_line)
    def add_message_time(self, timestamp):
        """Добавление временной метки сообщения для статистики"""
        self.message_times.append(timestamp)
        hour = str(timestamp.hour)
        self.hourly_activity[hour] = self.hourly_activity.get(hour, 0) + 1
        day = timestamp.strftime("%Y-%m-%d")
        self.daily_activity[day] = self.daily_activity.get(day, 0) + 1
        if len(self.message_times) > 1000:
            self.message_times = self.message_times[-1000:]
    def get_messages_per_hour(self):
        """Получить среднее количество сообщений в час"""
        if not self.message_times:
            return 0
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        recent = [t for t in self.message_times if t > hour_ago]
        return len(recent)
    def get_messages_per_day(self):
        """Получить количество сообщений за сегодня"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.daily_activity.get(today, 0)
    def get_most_active_hours(self, top=3):
        """Получить самые активные часы"""
        sorted_hours = sorted(self.hourly_activity.items(), key=lambda x: x[1], reverse=True)
        return sorted_hours[:top]
    def to_dict(self):
        """Сериализация для сохранения в конфиг"""
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'last_photo_id': self.last_photo_id,
            'last_bio': self.last_bio,
            'last_phone': self.last_phone,
            'settings': self.settings
        }
class UserBot:
    def __init__(self):
        self.client = None
        self.me = None
        self.targets = []
        self.targets_dict = {}
        self.current_target = None
        self.ping = 0
        self.ping_update_task = None
        self.api_id = None
        self.api_hash = None
        self.phone = None
        self.session_name = None
        self.running = True
        self.config_file = Path('config.json')
        self.prompt_visible = False
        self.load_config()
    def load_config(self):
        """Загрузка конфигурации из файла"""
        if not self.config_file.exists():
            return
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.api_id = data.get('api_id')
            self.api_hash = data.get('api_hash')
            self.phone = data.get('phone')
            self.session_name = data.get('session_name', 'user_session')
            for t in data.get('targets', []):
                target = Target(
                    t['id'],
                    t['name'],
                    t.get('username'),
                    t.get('last_photo_id')
                )
                target.last_bio = t.get('last_bio')
                target.last_phone = t.get('last_phone')
                if 'settings' in t:
                    target.settings.update(t['settings'])
                self.targets.append(target)
                self.targets_dict[target.id] = target
            if self.targets:
                self.current_target = self.targets[0]
        except json.JSONDecodeError as e:
            print(f"{Colors.BRIGHT_RED}Config file corrupted: {e}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.BRIGHT_RED}Error loading config: {e}{Colors.RESET}")
    def save_config(self):
        """Сохранение конфигурации в файл"""
        try:
            data = {
                'api_id': self.api_id,
                'api_hash': self.api_hash,
                'phone': self.phone,
                'session_name': self.session_name or 'user_session',
                'targets': [t.to_dict() for t in self.targets]
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{Colors.BRIGHT_RED}Error saving config: {e}{Colors.RESET}")
    def clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.prompt_visible = False
    def print_banner(self):
        """Красный заголовок ASCII art"""
        banner = f"""
{Colors.DARK_RED}.__        _____.__
{Colors.DARK_RED}|__| _____/ ____\  |  __ __   ____   ____   ____  ____
{Colors.DARK_RED}|  |/    \   __\|  | |  |  \_/ __ \ /    \_/ ___\/ __ \
{Colors.DARK_RED}|  |   |  \  |  |  |_|  |  /\  ___/|   |  \  \__\  ___/
{Colors.DARK_RED}|__|___|  /__|  |____/____/  \___  >___|  /\___  >___  >
{Colors.DARK_RED}        \/                       \/     \/     \/    \/{Colors.RESET}
{Colors.GREY}---------------------------------------------------
v2.0 // developed by {Colors.BRIGHT_RED}triumph{Colors.RESET}
"""
        print(banner)
    async def update_ping_periodically(self):
        """Фоновое обновление пинга каждые 5 секунд"""
        try:
            while self.running:
                if self.client:
                    self.ping = await measure_ping(self.client)
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
    async def print_header(self):
        """Вывод заголовка с информацией о сессии"""
        self.clear()
        self.print_banner()
        if not self.ping_update_task and self.client:
            self.ping_update_task = asyncio.create_task(self.update_ping_periodically())
        ping_color = get_ping_color(self.ping)
        username_display = f"@{self.me.username}" if self.me and self.me.username else "@none"
        user_id_display = self.me.id if self.me else "N/A"
        censored_api_hash = censor_string(self.api_hash, 3) if self.api_hash else "None"
        censored_phone = censor_phone(self.phone) if self.phone else "None"
        print(f"{Colors.BRIGHT_RED}Session details{Colors.RESET}")
        print(
            f"{Colors.GREY}Ping             :{Colors.RESET}       {Colors.DARK_RED}[{ping_color}{self.ping} ms{Colors.DARK_RED}]{Colors.RESET} {Colors.GREY}(updates every 5s){Colors.RESET}")
        print(
            f"{Colors.GREY}Api id           :{Colors.RESET}       {Colors.DARK_RED}[{Colors.WHITE}{self.api_id}{Colors.DARK_RED}]{Colors.RESET}")
        print(
            f"{Colors.GREY}Api HASH         :{Colors.RESET}       {Colors.DARK_RED}[{Colors.WHITE}{censored_api_hash}{Colors.DARK_RED}]{Colors.RESET}")
        print(
            f"{Colors.GREY}Phone            :{Colors.RESET}       {Colors.DARK_RED}[{Colors.WHITE}{censored_phone}{Colors.DARK_RED}]{Colors.RESET}")
        print(
            f"{Colors.GREY}ID // User       :{Colors.RESET}       {Colors.DARK_RED}[{Colors.YELLOW}{user_id_display} // {username_display}{Colors.DARK_RED}]{Colors.RESET}")
        print(
            f"{Colors.GREY}Session          :{Colors.RESET}       {Colors.DARK_RED}[{Colors.WHITE}{self.session_name}{Colors.DARK_RED}]{Colors.RESET}")
        print()
    def print_targets(self):
        """Список целей с выравниванием двоеточий"""
        print(f"{Colors.BRIGHT_RED}Target details{Colors.RESET}")
        if not self.targets:
            print(
                f"{Colors.GREY}1               :{Colors.RESET}   {Colors.DARK_RED}[{Colors.GREY}no targets{Colors.DARK_RED}]{Colors.RESET}")
        else:
            for i, t in enumerate(self.targets, 1):
                marker = "→" if t == self.current_target else " "
                display_name = f"@{t.username}" if t.username else str(t.id)
                num_str = str(i)
                spaces = " " * (15 - len(num_str) - 1)
                print(
                    f"{marker}{num_str}{spaces}:   {Colors.DARK_RED}[{Colors.WHITE}{display_name}{Colors.DARK_RED}]{Colors.RESET}")
        print()
    def print_help(self):
        """Вывод списка команд"""
        self.clear_prompt_line()
        print(f"\n{Colors.BRIGHT_RED}Available commands:{Colors.RESET}")
        print(f"{Colors.GREY}  help{Colors.RESET}            - Show this help message")
        print(f"{Colors.GREY}  add @username{Colors.RESET}   - Add new target to monitor")
        print(f"{Colors.GREY}  remove N{Colors.RESET}         - Remove target number N")
        print(f"{Colors.GREY}  remove @username{Colors.RESET}  - Remove target by username")
        print(f"{Colors.GREY}  switch N{Colors.RESET}        - Switch to target number N")
        print(f"{Colors.GREY}  list{Colors.RESET}            - Show all targets")
        print(f"{Colors.GREY}  settings{Colors.RESET}        - Configure target monitoring settings")
        print(f"{Colors.GREY}  logs [N]{Colors.RESET}        - Show recent N logs (default: 20)")
        print(f"{Colors.GREY}  export{Colors.RESET}          - Export current target logs to file")
        print(f"{Colors.GREY}  stats{Colors.RESET}           - Show activity statistics")
        print(f"{Colors.GREY}  profile{Colors.RESET}         - Show detailed profile info")
        print(f"{Colors.GREY}  deleted{Colors.RESET}         - Show deleted messages")
        print(f"{Colors.GREY}  scrape{Colors.RESET}          - Scrape all messages from chats")
        print(f"{Colors.GREY}  groups{Colors.RESET}          - Show common groups")
        print(f"{Colors.GREY}  clear{Colors.RESET}           - Clear screen")
        print(f"{Colors.GREY}  exit{Colors.RESET}            - Exit program")
        input(f"\n{Colors.GREY}Press Enter to continue...{Colors.RESET}")
        self.print_prompt()
    def print_prompt(self):
        """Строка ввода в нужном формате"""
        username = f"{self.me.username}" if self.me and self.me.username else str(self.me.id) if self.me else "user"
        sys.stdout.write(f"{Colors.DARK_RED}┌─[{Colors.BRIGHT_RED}INFLUENCE{Colors.DARK_RED}]─[{Colors.YELLOW}@{username}{Colors.DARK_RED}]{Colors.RESET}\n")
        sys.stdout.write(f"{Colors.DARK_RED}└──>{Colors.RESET} ")
        sys.stdout.flush()
    def clear_prompt_line(self):
        """Очищает только строку с промптом"""
        if self.prompt_visible:
            sys.stdout.write('\033[2F\033[2K')
            sys.stdout.flush()
            self.prompt_visible = False
    def realtime_print(self, text):
        """Вывод в реальном времени - просто добавляет лог"""
        if self.prompt_visible:
            sys.stdout.write('\r\033[K')
            sys.stdout.write('\033[1A\r\033[K')
            sys.stdout.flush()
        print(f"{Colors.WHITE}{text}{Colors.RESET}")
        self.print_prompt()
        self.prompt_visible = True
    async def authenticate(self):
        """Аутентификация с сохранением сессии"""
        if self.api_id and self.api_hash and self.phone and self.session_name:
            try:
                print(f"{Colors.YELLOW}🔄 Trying to load existing session: {self.session_name}{Colors.RESET}")
                self.client = TelegramClient(
                    self.session_name,
                    int(self.api_id),
                    self.api_hash
                )
                await self.client.connect()
                if await self.client.is_user_authorized():
                    self.me = await self.client.get_me()
                    print(f"{Colors.GREEN}✓ Session loaded successfully!{Colors.RESET}")
                    print(f"{Colors.GREEN}✓ Logged in as: {self.me.first_name} (@{self.me.username}){Colors.RESET}")
                    time.sleep(1)
                    return
                else:
                    print(f"{Colors.YELLOW}⚠ Session exists but not authorized{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.YELLOW}⚠ Session error: {e}{Colors.RESET}")
                print(f"{Colors.YELLOW}⚠ Creating new session...{Colors.RESET}")
        print(f"\n{Colors.BRIGHT_RED}🔐 Authentication required{Colors.RESET}")
        print(f"{Colors.GREY}Enter your Telegram API credentials{Colors.RESET}\n")
        self.api_id = input(f"{Colors.GREY}API ID{Colors.RESET}: ")
        self.api_hash = input(f"{Colors.GREY}API HASH{Colors.RESET}: ")
        self.phone = input(f"{Colors.GREY}Phone (with country code){Colors.RESET}: ")
        session_input = input(f"{Colors.GREY}Session name (enter for 'user_session'){Colors.RESET}: ").strip()
        self.session_name = session_input if session_input else 'user_session'
        print(f"{Colors.YELLOW}🔄 Creating new session: {self.session_name}{Colors.RESET}")
        self.client = TelegramClient(
            self.session_name,
            int(self.api_id),
            self.api_hash
        )
        await self.client.connect()
        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.phone)
            code = input(f"{Colors.GREY}Code from Telegram{Colors.RESET}: ")
            try:
                await self.client.sign_in(self.phone, code)
            except SessionPasswordNeededError:
                pwd = input(f"{Colors.GREY}2FA Password{Colors.RESET}: ")
                await self.client.sign_in(password=pwd)
        self.me = await self.client.get_me()
        self.save_config()
        print(f"{Colors.GREEN}✓ New session created and saved!{Colors.RESET}")
        print(f"{Colors.GREEN}✓ Logged in as: {self.me.first_name} (@{self.me.username}){Colors.RESET}")
        time.sleep(1)
    def setup_handlers(self):
        """Настройка обработчиков событий"""
        @self.client.on(events.NewMessage)
        async def handler(event):
            try:
                if not event.sender_id:
                    return
                target_found = self.targets_dict.get(event.sender_id)
                if target_found:
                    if not target_found.settings.get('track_messages', True):
                        return
                    text = event.raw_text or "[media]"
                    date = event.date.strftime("%d.%m.%Y %H:%M")
                    target_found.known_message_ids.add(event.id)
                    target_found.add_message_time(event.date)
                    if target_found.username:
                        msg_url = f"https://t.me/{target_found.username}/{event.id}"
                    else:
                        chat_id = str(event.chat_id).replace('-100', '')
                        msg_url = f"https://t.me/c/{chat_id}/{event.id}"
                    log = f"{text} [{date}] | {make_link('msg', msg_url)}"
                    target_found.save_log(log)
                    if target_found == self.current_target:
                        self.realtime_print(log)
            except Exception as e:
                print(f"Handler error: {e}")
        @self.client.on(events.MessageDeleted)
        async def deleted_handler(event):
            """Обработчик удаленных сообщений"""
            try:
                chat_id = None
                if hasattr(event, 'chat_id'):
                    chat_id = event.chat_id
                elif hasattr(event, 'peer'):
                    if hasattr(event.peer, 'user_id'):
                        chat_id = event.peer.user_id
                    elif hasattr(event.peer, 'chat_id'):
                        chat_id = event.peer.chat_id
                    elif hasattr(event.peer, 'channel_id'):
                        chat_id = event.peer.channel_id
                for target in self.targets:
                    if not target.settings.get('track_deleted', True):
                        continue
                    if chat_id and chat_id == target.id:
                        for msg_id in event.deleted_ids:
                            if msg_id in target.known_message_ids:
                                date = datetime.now().strftime("%d.%m.%Y %H:%M")
                                log = f"[DELETED] Message ID {msg_id} was deleted [{date}]"
                                target.deleted_messages.append(log)
                                target.save_log(log)
                                target.known_message_ids.discard(msg_id)
                                if target == self.current_target:
                                    self.realtime_print(log)
            except Exception as e:
                pass
        @self.client.on(events.UserUpdate)
        async def user_update(event):
            try:
                target_found = self.targets_dict.get(event.user_id)
                if target_found:
                    changes = []
                    user = await event.get_user()
                    try:
                        full_user = await self.client(GetFullUserRequest(user.id))
                        if target_found.settings.get('track_bio', True):
                            if hasattr(full_user, 'full_user') and hasattr(full_user.full_user, 'about'):
                                current_bio = full_user.full_user.about
                                if current_bio and current_bio != target_found.last_bio:
                                    if target_found.last_bio is not None:
                                        changes.append(f"Bio → {current_bio[:50]}...")
                                    target_found.last_bio = current_bio
                        if target_found.settings.get('track_phone', True):
                            if hasattr(user, 'phone') and user.phone:
                                if user.phone != target_found.last_phone:
                                    if target_found.last_phone is not None:
                                        changes.append(f"Phone → {user.phone}")
                                    target_found.last_phone = user.phone
                        if target_found.settings.get('track_stories', True):
                            if hasattr(full_user, 'full_user') and hasattr(full_user.full_user, 'stories_max_id'):
                                stories_count = full_user.full_user.stories_max_id or 0
                                if stories_count != target_found.last_stories_count:
                                    if stories_count > target_found.last_stories_count:
                                        changes.append("New story added")
                                    elif stories_count < target_found.last_stories_count:
                                        changes.append("Story deleted")
                                    target_found.last_stories_count = stories_count
                    except Exception as e:
                        pass
                    if target_found.settings.get('track_profile_changes', True):
                        if hasattr(user, 'first_name') and user.first_name and user.first_name != target_found.name:
                            changes.append(f"Имя → {user.first_name}")
                            target_found.name = user.first_name
                        if hasattr(user, 'username') and user.username and user.username != target_found.username:
                            changes.append(f"Юзер → @{user.username}")
                            target_found.username = user.username
                        if hasattr(user, 'photo') and user.photo:
                            current_photo_id = user.photo.photo_id if hasattr(user.photo, 'photo_id') else None
                            if current_photo_id and current_photo_id != target_found.last_photo_id:
                                changes.append("Фото обновлено")
                                target_found.last_photo_id = current_photo_id
                        elif not hasattr(user, 'photo') or not user.photo:
                            if target_found.last_photo_id is not None:
                                changes.append("Фото удалено")
                                target_found.last_photo_id = None
                    if target_found.settings.get('track_status', True):
                        if hasattr(user, 'status'):
                            current_status = None
                            if isinstance(user.status, UserStatusOnline):
                                current_status = "online"
                            elif isinstance(user.status, UserStatusOffline):
                                current_status = "offline"
                            elif isinstance(user.status, UserStatusRecently):
                                current_status = "recently"
                            if current_status and current_status != target_found.last_status:
                                if target_found.last_status is not None:
                                    changes.append(f"Статус → {current_status}")
                                target_found.last_status = current_status
                    if changes:
                        date = datetime.now().strftime("%d.%m.%Y %H:%M")
                        log = f"[PROFILE] {', '.join(changes)} [{date}]"
                        target_found.save_log(log)
                        if target_found == self.current_target:
                            self.realtime_print(log)
            except Exception as e:
                print(f"Update error: {e}")
    async def add_target(self, identifier):
        """Добавление цели для отслеживания"""
        try:
            entity = None
            if identifier.startswith('@'):
                result = await self.client(
                    ResolveUsernameRequest(identifier[1:])
                )
                if result.users:
                    entity = result.users[0]
            else:
                try:
                    entity = await self.client.get_entity(int(identifier))
                except:
                    result = await self.client(
                        ResolveUsernameRequest(identifier)
                    )
                    if result.users:
                        entity = result.users[0]
            if not entity or not isinstance(entity, User):
                print(f"{Colors.BRIGHT_RED}User not found{Colors.RESET}")
                time.sleep(1)
                return
            if entity.id in self.targets_dict:
                print(f"{Colors.BRIGHT_RED}Already exists{Colors.RESET}")
                time.sleep(1)
                return
            photo_id = None
            if hasattr(entity, 'photo') and entity.photo:
                photo_id = entity.photo.photo_id if hasattr(entity.photo, 'photo_id') else None
            target = Target(entity.id, entity.first_name, entity.username, photo_id)
            self.targets.append(target)
            self.targets_dict[target.id] = target
            if not self.current_target:
                self.current_target = target
            self.save_config()
            print(f"{Colors.GREEN}✓ Target added: {entity.first_name}{Colors.RESET}")
            time.sleep(1)
        except Exception as e:
            print(f"{Colors.BRIGHT_RED}{e}{Colors.RESET}")
    async def remove_target(self, identifier):
        """Удаление цели по номеру или username"""
        try:
            removed = False
            try:
                idx = int(identifier) - 1
                if 0 <= idx < len(self.targets):
                    removed_target = self.targets[idx]
                    print(f"{Colors.YELLOW}Are you sure you want to remove {removed_target.name}? (y/n){Colors.RESET}")
                    confirm = input().lower()
                    if confirm == 'y':
                        if self.current_target == removed_target:
                            if len(self.targets) > 1:
                                self.current_target = self.targets[0 if idx != 0 else 1]
                            else:
                                self.current_target = None
                        self.targets.pop(idx)
                        del self.targets_dict[removed_target.id]
                        removed = True
                        print(f"{Colors.GREEN}✓ Target removed: {removed_target.name}{Colors.RESET}")
                    else:
                        print(f"{Colors.YELLOW}Removal cancelled{Colors.RESET}")
                else:
                    print(f"{Colors.BRIGHT_RED}Invalid index{Colors.RESET}")
            except ValueError:
                if identifier.startswith('@'):
                    username = identifier[1:].lower()
                    for i, t in enumerate(self.targets):
                        if t.username and t.username.lower() == username:
                            print(
                                f"{Colors.YELLOW}Are you sure you want to remove {t.name} (@{t.username})? (y/n){Colors.RESET}")
                            confirm = input().lower()
                            if confirm == 'y':
                                if self.current_target == t:
                                    if len(self.targets) > 1:
                                        self.current_target = self.targets[0 if i != 0 else 1]
                                    else:
                                        self.current_target = None
                                self.targets.pop(i)
                                del self.targets_dict[t.id]
                                removed = True
                                print(f"{Colors.GREEN}✓ Target removed: {t.name}{Colors.RESET}")
                            else:
                                print(f"{Colors.YELLOW}Removal cancelled{Colors.RESET}")
                            break
                    else:
                        print(f"{Colors.BRIGHT_RED}Target not found{Colors.RESET}")
                else:
                    print(f"{Colors.BRIGHT_RED}Invalid identifier. Use number or @username{Colors.RESET}")
            if removed:
                self.save_config()
            time.sleep(1)
        except Exception as e:
            print(f"{Colors.BRIGHT_RED}{e}{Colors.RESET}")
            time.sleep(1)
    async def show_logs(self, count=20):
        """Показ последних логов"""
        self.clear_prompt_line()
        if not self.current_target:
            print(f"{Colors.BRIGHT_RED}No target selected{Colors.RESET}")
            input(f"{Colors.GREY}Press Enter...{Colors.RESET}")
            self.print_prompt()
            return
        print(f"\n{Colors.BRIGHT_RED}--- logs for {self.current_target.name} (last {count}) ---{Colors.RESET}")
        for m in self.current_target.messages[-count:]:
            print(m)
        input(f"\n{Colors.GREY}Press Enter...{Colors.RESET}")
        self.print_prompt()
    async def export_logs(self):
        """Экспорт логов текущей цели"""
        self.clear_prompt_line()
        if not self.current_target:
            print(f"{Colors.BRIGHT_RED}No target selected{Colors.RESET}")
            time.sleep(1)
            return
        try:
            export_file = Path(f"export_{self.current_target.name}_{int(time.time())}.txt")
            with open(export_file, 'w', encoding='utf-8') as f:
                f.write(f"=== Export for {self.current_target.name} ===\n")
                f.write(f"=== Total messages: {len(self.current_target.messages)} ===\n\n")
                for msg in self.current_target.messages:
                    f.write(msg + '\n')
            print(f"{Colors.GREEN}✓ Logs exported to: {export_file}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.BRIGHT_RED}Export error: {e}{Colors.RESET}")
        time.sleep(1)
    async def show_stats(self):
        """Показать статистику активности"""
        self.clear_prompt_line()
        if not self.current_target:
            print(f"{Colors.BRIGHT_RED}No target selected{Colors.RESET}")
            input(f"{Colors.GREY}Press Enter...{Colors.RESET}")
            self.print_prompt()
            return
        target = self.current_target
        print(f"\n{Colors.BRIGHT_RED}=== Activity Statistics for {target.name} ==={Colors.RESET}\n")
        msgs_per_hour = target.get_messages_per_hour()
        msgs_per_day = target.get_messages_per_day()
        print(f"{Colors.CYAN}Messages per hour:{Colors.RESET} {Colors.WHITE}{msgs_per_hour}{Colors.RESET}")
        print(f"{Colors.CYAN}Messages today:{Colors.RESET} {Colors.WHITE}{msgs_per_day}{Colors.RESET}")
        print(f"{Colors.CYAN}Total messages:{Colors.RESET} {Colors.WHITE}{len(target.messages)}{Colors.RESET}\n")
        print(f"{Colors.BRIGHT_RED}Most Active Hours:{Colors.RESET}")
        top_hours = target.get_most_active_hours(5)
        for hour, count in top_hours:
            if count > 0:
                bar = '█' * min(count, 50)
                print(f"{Colors.GREY}{hour:>2}:00{Colors.RESET} {Colors.GREEN}{bar}{Colors.RESET} {Colors.WHITE}{count}{Colors.RESET}")
        print(f"\n{Colors.BRIGHT_RED}Daily Activity (last 7 days):{Colors.RESET}")
        sorted_days = sorted(target.daily_activity.items(), reverse=True)[:7]
        for day, count in sorted_days:
            bar = '█' * min(count, 50)
            print(f"{Colors.GREY}{day}{Colors.RESET} {Colors.CYAN}{bar}{Colors.RESET} {Colors.WHITE}{count}{Colors.RESET}")
        input(f"\n{Colors.GREY}Press Enter...{Colors.RESET}")
        self.print_prompt()
    async def show_profile(self):
        """Показать детальную информацию о профиле"""
        self.clear_prompt_line()
        if not self.current_target:
            print(f"{Colors.BRIGHT_RED}No target selected{Colors.RESET}")
            input(f"{Colors.GREY}Press Enter...{Colors.RESET}")
            self.print_prompt()
            return
        target = self.current_target
        try:
            user = await self.client.get_entity(target.id)
            full_user = await self.client(GetFullUserRequest(target.id))
            print(f"\n{Colors.BRIGHT_RED}=== Profile Info for {target.name} ==={Colors.RESET}\n")
            print(f"{Colors.CYAN}ID:{Colors.RESET} {Colors.WHITE}{user.id}{Colors.RESET}")
            print(f"{Colors.CYAN}Username:{Colors.RESET} {Colors.WHITE}@{user.username if user.username else 'None'}{Colors.RESET}")
            print(f"{Colors.CYAN}First Name:{Colors.RESET} {Colors.WHITE}{user.first_name or 'None'}{Colors.RESET}")
            print(f"{Colors.CYAN}Last Name:{Colors.RESET} {Colors.WHITE}{user.last_name or 'None'}{Colors.RESET}")
            if hasattr(user, 'phone') and user.phone:
                print(f"{Colors.CYAN}Phone:{Colors.RESET} {Colors.WHITE}{user.phone}{Colors.RESET}")
            if hasattr(full_user.full_user, 'about') and full_user.full_user.about:
                print(f"{Colors.CYAN}Bio:{Colors.RESET} {Colors.WHITE}{full_user.full_user.about}{Colors.RESET}")
            if hasattr(user, 'status'):
                if isinstance(user.status, UserStatusOnline):
                    status = f"{Colors.GREEN}Online{Colors.RESET}"
                elif isinstance(user.status, UserStatusOffline):
                    status = f"{Colors.GREY}Offline{Colors.RESET}"
                else:
                    status = f"{Colors.YELLOW}Recently{Colors.RESET}"
                print(f"{Colors.CYAN}Status:{Colors.RESET} {status}")
            print(f"{Colors.CYAN}Bot:{Colors.RESET} {Colors.WHITE}{'Yes' if user.bot else 'No'}{Colors.RESET}")
            print(f"{Colors.CYAN}Verified:{Colors.RESET} {Colors.WHITE}{'Yes' if user.verified else 'No'}{Colors.RESET}")
            print(f"{Colors.CYAN}Premium:{Colors.RESET} {Colors.WHITE}{'Yes' if hasattr(user, 'premium') and user.premium else 'No'}{Colors.RESET}")
            if hasattr(full_user.full_user, 'common_chats_count'):
                print(f"{Colors.CYAN}Common groups:{Colors.RESET} {Colors.WHITE}{full_user.full_user.common_chats_count}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.BRIGHT_RED}Error: {e}{Colors.RESET}")
        input(f"\n{Colors.GREY}Press Enter...{Colors.RESET}")
        self.print_prompt()
    async def show_deleted(self):
        """Показать удаленные сообщения"""
        self.clear_prompt_line()
        if not self.current_target:
            print(f"{Colors.BRIGHT_RED}No target selected{Colors.RESET}")
            input(f"{Colors.GREY}Press Enter...{Colors.RESET}")
            self.print_prompt()
            return
        target = self.current_target
        print(f"\n{Colors.BRIGHT_RED}=== Deleted Messages for {target.name} ==={Colors.RESET}\n")
        if not target.deleted_messages:
            print(f"{Colors.GREY}No deleted messages recorded{Colors.RESET}")
        else:
            for msg in target.deleted_messages[-20:]:
                print(f"{Colors.YELLOW}{msg}{Colors.RESET}")
        input(f"\n{Colors.GREY}Press Enter...{Colors.RESET}")
        self.print_prompt()
    async def scrape_messages(self):
        """Выгрузка всех сообщений пользователя из чатов"""
        self.clear_prompt_line()
        if not self.current_target:
            print(f"{Colors.BRIGHT_RED}No target selected{Colors.RESET}")
            time.sleep(1)
            return
        target = self.current_target
        print(f"\n{Colors.BRIGHT_RED}=== Scrape Messages ==={Colors.RESET}\n")
        print(f"{Colors.CYAN}1.{Colors.RESET} Common groups only")
        print(f"{Colors.CYAN}2.{Colors.RESET} Specific public chat")
        print(f"{Colors.CYAN}3.{Colors.RESET} Cancel\n")
        choice = input(f"{Colors.GREY}Choose option: {Colors.RESET}")
        if choice == '1':
            await self.scrape_common_groups(target)
        elif choice == '2':
            await self.scrape_specific_chat(target)
        else:
            print(f"{Colors.YELLOW}Cancelled{Colors.RESET}")
            time.sleep(1)
    async def scrape_common_groups(self, target):
        """Выгрузка из общих групп"""
        try:
            print(f"\n{Colors.YELLOW}Searching common groups...{Colors.RESET}")
            result = await self.client(GetCommonChatsRequest(
                user_id=target.id,
                max_id=0,
                limit=100
            ))
            if not result.chats:
                print(f"{Colors.BRIGHT_RED}No common groups found{Colors.RESET}")
                time.sleep(2)
                return
            print(f"{Colors.GREEN}Found {len(result.chats)} common groups{Colors.RESET}\n")
            all_messages = []
            total_count = 0
            for chat in result.chats:
                print(f"{Colors.CYAN}Scraping {chat.title}...{Colors.RESET}")
                try:
                    messages = []
                    offset_id = 0
                    while True:
                        batch = await self.client.get_messages(
                            chat,
                            from_user=target.id,
                            limit=100,
                            offset_id=offset_id
                        )
                        if not batch:
                            break
                        messages.extend(batch)
                        offset_id = batch[-1].id
                        print(f"{Colors.GREY}  Loaded {len(messages)} messages...{Colors.RESET}", end='\r')
                        if len(batch) < 100:
                            break
                    for msg in messages:
                        if msg.text:
                            date = msg.date.strftime("%d.%m.%Y %H:%M")
                            if hasattr(chat, 'username') and chat.username:
                                msg_link = f"https://t.me/{chat.username}/{msg.id}"
                            else:
                                chat_id = str(chat.id).replace('-100', '')
                                msg_link = f"https://t.me/c/{chat_id}/{msg.id}"
                            all_messages.append(f"[{chat.title}] [{date}] {msg.text}\nLink: {msg_link}")
                    total_count += len(messages)
                    print(f"{Colors.GREEN}  Found {len(messages)} messages{Colors.RESET}                    ")
                except Exception as e:
                    print(f"{Colors.BRIGHT_RED}  Error: {e}{Colors.RESET}")
            if all_messages:
                filename = f"scraped_{target.name}_common_{int(time.time())}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"=== Scraped messages from {target.name} ===\n")
                    f.write(f"=== Total: {total_count} messages from {len(result.chats)} chats ===\n\n")
                    for msg in all_messages:
                        f.write(msg + '\n\n')
                print(f"\n{Colors.GREEN}✓ Saved {total_count} messages to {filename}{Colors.RESET}")
            else:
                print(f"\n{Colors.YELLOW}No messages found{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.BRIGHT_RED}Error: {e}{Colors.RESET}")
        time.sleep(2)
    async def scrape_specific_chat(self, target):
        """Выгрузка из конкретного чата"""
        chat_input = input(f"{Colors.GREY}Enter chat username or ID: {Colors.RESET}")
        if not chat_input:
            print(f"{Colors.YELLOW}Cancelled{Colors.RESET}")
            time.sleep(1)
            return
        try:
            print(f"\n{Colors.YELLOW}Connecting to chat...{Colors.RESET}")
            chat = await self.client.get_entity(chat_input)
            print(f"{Colors.CYAN}Scraping messages from {chat.title}...{Colors.RESET}")
            messages = []
            offset_id = 0
            while True:
                batch = await self.client.get_messages(
                    chat,
                    from_user=target.id,
                    limit=100,
                    offset_id=offset_id
                )
                if not batch:
                    break
                messages.extend(batch)
                offset_id = batch[-1].id
                print(f"{Colors.GREY}Loaded {len(messages)} messages...{Colors.RESET}", end='\r')
                if len(batch) < 100:
                    break
            print(f"{Colors.GREEN}Loaded {len(messages)} messages{Colors.RESET}                    ")
            if messages:
                filename = f"scraped_{target.name}_{chat.title}_{int(time.time())}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"=== Messages from {target.name} in {chat.title} ===\n")
                    f.write(f"=== Total: {len(messages)} messages ===\n\n")
                    for msg in messages:
                        if msg.text:
                            date = msg.date.strftime("%d.%m.%Y %H:%M")
                            if hasattr(chat, 'username') and chat.username:
                                msg_link = f"https://t.me/{chat.username}/{msg.id}"
                            else:
                                chat_id = str(chat.id).replace('-100', '')
                                msg_link = f"https://t.me/c/{chat_id}/{msg.id}"
                            f.write(f"[{date}] {msg.text}\n")
                            f.write(f"Link: {msg_link}\n\n")
                print(f"{Colors.GREEN}✓ Saved {len(messages)} messages to {filename}{Colors.RESET}")
            else:
                print(f"{Colors.YELLOW}No messages found{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.BRIGHT_RED}Error: {e}{Colors.RESET}")
        time.sleep(2)
    async def show_groups(self):
        """Показать общие группы"""
        self.clear_prompt_line()
        if not self.current_target:
            print(f"{Colors.BRIGHT_RED}No target selected{Colors.RESET}")
            input(f"{Colors.GREY}Press Enter...{Colors.RESET}")
            self.print_prompt()
            return
        target = self.current_target
        try:
            print(f"\n{Colors.BRIGHT_RED}=== Common Groups with {target.name} ==={Colors.RESET}\n")
            result = await self.client(GetCommonChatsRequest(
                user_id=target.id,
                max_id=0,
                limit=100
            ))
            if not result.chats:
                print(f"{Colors.GREY}No common groups found{Colors.RESET}")
            else:
                for i, chat in enumerate(result.chats, 1):
                    members = "?"
                    try:
                        if hasattr(chat, 'participants_count'):
                            members = chat.participants_count
                    except:
                        pass
                    print(f"{Colors.CYAN}{i}.{Colors.RESET} {Colors.WHITE}{chat.title}{Colors.RESET} {Colors.GREY}({members} members){Colors.RESET}")
        except Exception as e:
            print(f"{Colors.BRIGHT_RED}Error: {e}{Colors.RESET}")
        input(f"\n{Colors.GREY}Press Enter...{Colors.RESET}")
        self.print_prompt()
    def list_targets(self):
        """Показать все цели с номерами"""
        self.clear_prompt_line()
        if not self.targets:
            print(f"\n{Colors.YELLOW}No targets added{Colors.RESET}")
        else:
            print(f"\n{Colors.BRIGHT_RED}Target list:{Colors.RESET}")
            for i, t in enumerate(self.targets, 1):
                marker = "→" if t == self.current_target else " "
                display_name = f"@{t.username}" if t.username else str(t.id)
                print(
                    f"{marker} {i}. {t.name} - {Colors.GREY}{display_name}{Colors.RESET} {Colors.CYAN}[{len(t.messages)} messages]{Colors.RESET}")
        input(f"\n{Colors.GREY}Press Enter...{Colors.RESET}")
        self.print_prompt()
    async def show_settings(self):
        """Панель настроек мониторинга для текущей цели"""
        self.clear_prompt_line()
        if not self.current_target:
            print(f"{Colors.BRIGHT_RED}No target selected{Colors.RESET}")
            time.sleep(1)
            return
        target = self.current_target
        while True:
            self.clear()
            self.print_banner()
            print(f"{Colors.BRIGHT_RED}=== Monitoring Settings for {target.name} ==={Colors.RESET}\n")
            settings_list = [
                ('track_messages', 'Track new messages'),
                ('track_profile_changes', 'Track profile changes (name, username, photo)'),
                ('track_status', 'Track online/offline status'),
                ('track_deleted', 'Track deleted messages'),
                ('track_media', 'Track media files'),
                ('track_bio', 'Track bio/description changes'),
                ('track_phone', 'Track phone number changes'),
                ('track_stories', 'Track stories (add/delete)')
            ]
            for i, (key, description) in enumerate(settings_list, 1):
                status = f"{Colors.GREEN}ON{Colors.RESET}" if target.settings.get(key, True) else f"{Colors.BRIGHT_RED}OFF{Colors.RESET}"
                print(f"{Colors.CYAN}{i}.{Colors.RESET} {description}: {status}")
            print(f"\n{Colors.CYAN}9.{Colors.RESET} Enable all")
            print(f"{Colors.CYAN}0.{Colors.RESET} Disable all")
            print(f"{Colors.CYAN}s.{Colors.RESET} Save and exit")
            print(f"{Colors.CYAN}q.{Colors.RESET} Exit without saving\n")
            choice = input(f"{Colors.GREY}Choose option: {Colors.RESET}").strip().lower()
            if choice == 's':
                self.save_config()
                print(f"{Colors.GREEN}✓ Settings saved{Colors.RESET}")
                time.sleep(1)
                break
            elif choice == 'q':
                print(f"{Colors.YELLOW}Settings not saved{Colors.RESET}")
                time.sleep(1)
                break
            elif choice == '9':
                for key, _ in settings_list:
                    target.settings[key] = True
                print(f"{Colors.GREEN}✓ All enabled{Colors.RESET}")
                time.sleep(0.5)
            elif choice == '0':
                for key, _ in settings_list:
                    target.settings[key] = False
                print(f"{Colors.YELLOW}✓ All disabled{Colors.RESET}")
                time.sleep(0.5)
            elif choice.isdigit() and 1 <= int(choice) <= len(settings_list):
                idx = int(choice) - 1
                key = settings_list[idx][0]
                target.settings[key] = not target.settings.get(key, True)
                status = "enabled" if target.settings[key] else "disabled"
                print(f"{Colors.GREEN}✓ {settings_list[idx][1]} {status}{Colors.RESET}")
                time.sleep(0.5)
            else:
                print(f"{Colors.BRIGHT_RED}Invalid option{Colors.RESET}")
                time.sleep(0.5)
    async def run(self):
        """Основной цикл программы"""
        await self.authenticate()
        self.setup_handlers()
        if self.client and not self.ping_update_task:
            self.ping_update_task = asyncio.create_task(self.update_ping_periodically())
        loop = asyncio.get_event_loop()
        await self.print_header()
        self.print_targets()
        while self.running:
            self.print_prompt()
            self.prompt_visible = True
            cmd = await loop.run_in_executor(None, input)
            self.prompt_visible = False
            cmd = cmd.strip().lower()
            if cmd == "exit":
                break
            elif cmd == "help":
                self.print_help()
            elif cmd == "list":
                self.list_targets()
            elif cmd == "settings":
                await self.show_settings()
            elif cmd.startswith("add "):
                await self.add_target(cmd[4:].strip())
            elif cmd.startswith("remove "):
                await self.remove_target(cmd[7:].strip())
            elif cmd.startswith("switch "):
                try:
                    idx = int(cmd.split()[1]) - 1
                    if 0 <= idx < len(self.targets):
                        self.current_target = self.targets[idx]
                        print(f"{Colors.GREEN}✓ Switched to: {self.current_target.name}{Colors.RESET}")
                    else:
                        print(f"{Colors.BRIGHT_RED}✗ Invalid index{Colors.RESET}")
                except:
                    print(f"{Colors.BRIGHT_RED}✗ Invalid command{Colors.RESET}")
            elif cmd == "logs":
                await self.show_logs()
            elif cmd.startswith("logs"):
                try:
                    parts = cmd.split()
                    count = int(parts[1]) if len(parts) > 1 else 20
                    await self.show_logs(count)
                except ValueError:
                    print(f"{Colors.BRIGHT_RED}✗ Invalid number{Colors.RESET}")
                    time.sleep(1)
            elif cmd == "export":
                await self.export_logs()
            elif cmd == "stats":
                await self.show_stats()
            elif cmd == "profile":
                await self.show_profile()
            elif cmd == "deleted":
                await self.show_deleted()
            elif cmd == "scrape":
                await self.scrape_messages()
            elif cmd == "groups":
                await self.show_groups()
            elif cmd == "clear":
                await self.print_header()
                self.print_targets()
            else:
                print(f"{Colors.BRIGHT_RED}✗ Unknown command. Type 'help' for available commands{Colors.RESET}")
                time.sleep(1)
        self.running = False
        if self.ping_update_task:
            self.ping_update_task.cancel()
            try:
                await self.ping_update_task
            except asyncio.CancelledError:
                pass
        if self.client:
            await self.client.disconnect()
        self.save_config()
def main():
    """Точка входа"""
    bot = UserBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.BRIGHT_RED}👋 Bye!{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.BRIGHT_RED}Fatal error: {e}{Colors.RESET}")
if __name__ == "__main__":
    main()