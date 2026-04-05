"""ChitChat Server

Usage:
    python socket_server.py

Starts a TCP chat server on 127.0.0.1:1234. Run this before starting any
client. Multiple clients can connect simultaneously; every message sent by
one client is broadcast to all connected clients.

All connections and messages are logged to chitchat.log in the working
directory.

ChatBot commands (type in the chat):
  /bot weather <city>          current weather via wttr.in
  /bot stock <SYMBOL>          latest stock price via Yahoo Finance
  /bot sports [nfl|nba|mlb|nhl]  live scores via ESPN
  /bot help                    show this command list
"""
import json
import logging
import socket
import threading
import urllib.parse
import urllib.request

logging.basicConfig(
    filename="chitchat.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class ChatBot:
    NAME = "ChitBot"
    HELP = (
        "Commands: /bot weather <city>  |  "
        "/bot stock <SYMBOL>  |  "
        "/bot sports [nfl|nba|mlb|nhl]"
    )

    def handle(self, text):
        """Return a reply string, or None if the text is not a bot command."""
        if not text.startswith("/bot"):
            return None
        parts = text.split(None, 2)
        sub = parts[1].lower() if len(parts) > 1 else "help"
        arg = parts[2].strip() if len(parts) > 2 else ""
        try:
            if sub == "weather":
                return self._weather(arg)
            if sub == "stock":
                return self._stock(arg.upper())
            if sub == "sports":
                return self._sports(arg.lower() or "nfl")
        except Exception as e:
            return f"Sorry, something went wrong: {e}"
        return self.HELP

    def _fetch(self, url, as_json=False):
        req = urllib.request.Request(url, headers={"User-Agent": "ChitChat/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw) if as_json else raw

    def _weather(self, city):
        if not city:
            return "Usage: /bot weather <city>"
        data = self._fetch(
            f"https://wttr.in/{urllib.parse.quote(city)}?format=3"
        )
        return data.strip()

    def _stock(self, symbol):
        if not symbol:
            return "Usage: /bot stock <SYMBOL>"
        data = self._fetch(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
            "?range=1d&interval=1d",
            as_json=True,
        )
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice", "N/A")
        prev = meta.get("chartPreviousClose", "N/A")
        currency = meta.get("currency", "")
        if isinstance(price, (int, float)) and isinstance(prev, (int, float)):
            change = round(price - prev, 2)
            sign = "+" if change >= 0 else ""
            return f"{symbol}: {price} {currency}  ({sign}{change} today)"
        return f"{symbol}: {price} {currency}"

    def _sports(self, league):
        league_map = {
            "nfl": ("football", "nfl"),
            "nba": ("basketball", "nba"),
            "mlb": ("baseball", "mlb"),
            "nhl": ("hockey", "nhl"),
        }
        if league not in league_map:
            return f"Unknown league '{league}'. Choose: nfl, nba, mlb, nhl"
        sport, lg = league_map[league]
        data = self._fetch(
            f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{lg}/scoreboard",
            as_json=True,
        )
        events = data.get("events", [])
        if not events:
            return f"No {league.upper()} games found right now."
        lines = []
        for event in events[:5]:
            comp = event.get("competitions", [{}])[0]
            teams = comp.get("competitors", [])
            if len(teams) == 2:
                a, b = teams[0], teams[1]
                line = (
                    f"{a['team']['abbreviation']} {a.get('score', '?')} "
                    f"- {b.get('score', '?')} {b['team']['abbreviation']}"
                    f"  [{event.get('status', {}).get('type', {}).get('shortDetail', '')}]"
                )
                lines.append(line)
        return "\n".join(lines) if lines else f"No {league.upper()} scores available."


class ServerThread(threading.Thread):
    def __init__(self, server, client_socket):
        super().__init__(daemon=True)
        self.server = server
        self.client_socket = client_socket
        self.name_label = None
        self.reader = client_socket.makefile(mode="r", buffering=1, encoding="utf-8")
        self.writer = client_socket.makefile(mode="w", buffering=1, encoding="utf-8")

    def _handle_bot_command(self, text):
        reply = self.server.bot.handle(text)
        if reply:
            for line in reply.splitlines():
                self.server.broadcast(f"[{ChatBot.NAME}] {line}")

    def send(self, message):
        self.writer.write(message + "\n")
        self.writer.flush()

    def run(self):
        try:
            self.name_label = self.reader.readline().strip()
            logger.info("JOIN  [%s] from %s", self.name_label, self.client_socket.getpeername())
            self.server.broadcast(f"**[{self.name_label}] Entered**")
            self.server.broadcast_user_list()

            for data in self.reader:
                data = data.strip()
                if data.startswith("__IMG__:"):
                    logger.info("IMG   [%s]", self.name_label)
                    self.server.broadcast(f"__IMG__:{self.name_label}:{data[len('__IMG__:'):]}")
                elif data.startswith("/bot"):
                    logger.info("BOT   [%s] %s", self.name_label, data)
                    threading.Thread(
                        target=self._handle_bot_command,
                        args=(data,),
                        daemon=True,
                    ).start()
                else:
                    logger.info("MSG   [%s] %s", self.name_label, data)
                    self.server.broadcast(f"[{self.name_label}] {data}")
        except Exception as e:
            print(f"Error handling client communication: {e} ---->")  
        finally:
            self.server.remove_thread(self)
            self.server.broadcast(f"**[{self.name_label}] Left**")
            self.server.broadcast_user_list()
            try:
                addr = self.client_socket.getpeername()
                print(f"{addr} - [{self.name_label}] Exit")
                logger.info("LEAVE [%s] from %s", self.name_label, addr)
            except OSError:
                print(f"[{self.name_label}] Exit")
                logger.info("LEAVE [%s]", self.name_label)
            try:
                self.reader.close()
                self.writer.close()
                self.client_socket.close()
            except Exception:
                pass


class SocketServer:
    def __init__(self, host="127.0.0.1", port=1234):
        self.host = host
        self.port = port
        self.clients = []
        self.lock = threading.Lock()
        self.bot = ChatBot()

    def add_thread(self, thread):
        with self.lock:
            self.clients.append(thread)

    def remove_thread(self, thread):
        with self.lock:
            self.clients.remove(thread)

    def get_user_list(self):
        with self.lock:
            return [t.name_label for t in self.clients if t.name_label]

    def broadcast_user_list(self):
        names = ",".join(self.get_user_list())
        self.broadcast(f"__USERS__:{names}")

    def broadcast(self, message):
        print(message)
        with self.lock:
            for client in self.clients:
                try:
                    client.send(message)
                except Exception:
                    pass

    def serve(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(50)
            print(f"\n Waiting for Client connection on {self.host}:{self.port}")

            while True:
                client_socket, addr = server_socket.accept()
                print(f"{addr} connect")
                logger.info("CONNECT %s", addr)

                thread = ServerThread(self, client_socket)
                self.add_thread(thread)
                thread.start()


if __name__ == "__main__":
    SocketServer().serve()
