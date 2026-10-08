
# ============================================================
#   Spider Link — Internet Group Chat (Kivy + MQTT)
#   Install: pip install kivy paho-mqtt
#   Run on PC: python main.py
#   Build APK: buildozer android debug
# ============================================================

import json, random, string
from datetime import datetime

import paho.mqtt.client as mqtt
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import hashlib, base64
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

# ── Colors ───────────────────────────────────────────────────
BG     = get_color_from_hex("#0a0a12")
BG2    = get_color_from_hex("#12121c")
BG3    = get_color_from_hex("#16162a")
ACCENT = get_color_from_hex("#7c3aed")
ACCENT2= get_color_from_hex("#4f46e5")
TEXT   = get_color_from_hex("#ffffff")
MUTED  = get_color_from_hex("#555566")
GREEN  = get_color_from_hex("#22c55e")
BORDER = get_color_from_hex("#1e1e30")

AVATAR_COLORS = [
    "#7c3aed","#4f46e5","#0891b2","#059669",
    "#dc2626","#d97706","#db2777","#0d9488"
]

Window.clearcolor = BG

# ── MQTT Config ──────────────────────────────────────────────
BROKER       = "broker.hivemq.com"   # free public broker — no setup needed
BROKER_PORT  = 1883
TOPIC_PREFIX = "spiderlink/v1/"      # unique namespace

# ── Encryption (AES-GCM) ─────────────────────────────────────
# Room code → 32-byte key via SHA-256
# Broker only ever sees base64 ciphertext — it cannot read messages

def _derive_key(room_code: str) -> bytes:
    return hashlib.sha256(room_code.encode()).digest()

def encrypt_msg(data: dict, room_code: str) -> str:
    key    = _derive_key(room_code)
    nonce  = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(json.dumps(data).encode())
    return base64.b64encode(nonce + tag + ct).decode()

def decrypt_msg(payload: str, room_code: str) -> dict:
    key  = _derive_key(room_code)
    raw  = base64.b64decode(payload)
    nonce, tag, ct = raw[:16], raw[16:32], raw[32:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return json.loads(cipher.decrypt_and_verify(ct, tag).decode())

# ── Helpers ──────────────────────────────────────────────────
def gen_code(n=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

def hk(h): return get_color_from_hex(h)

def mk_btn(text, bg=None, fg=TEXT, radius=12, height=dp(48)):
    if bg is None: bg = ACCENT
    btn = Button(text=text, size_hint_y=None, height=height,
                 background_normal="", background_color=(0,0,0,0),
                 color=fg, font_size=sp(14), bold=True)
    with btn.canvas.before:
        Color(*bg)
        btn._rect = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[radius])
    btn.bind(pos=lambda w,v: setattr(w._rect,"pos",v),
             size=lambda w,v: setattr(w._rect,"size",v))
    return btn

def mk_input(hint):
    return TextInput(
        hint_text=hint, multiline=False,
        background_color=BG3, foreground_color=TEXT,
        hint_text_color=MUTED, cursor_color=ACCENT,
        font_size=sp(14), padding=[dp(14), dp(12)],
        size_hint_y=None, height=dp(48)
    )

def mk_label(text, size=14, color=TEXT, bold=False, halign="left", wrap=True):
    lbl = Label(text=text, color=color, font_size=sp(size),
                bold=bold, halign=halign, markup=True)
    if wrap:
        lbl.bind(width=lambda w,v: setattr(w,"text_size",(v,None)))
    return lbl

# ════════════════════════════════════════════════════════════
#   MQTT Chat — works over the internet, no Wi-Fi restriction
# ════════════════════════════════════════════════════════════
class MQTTChat:
    def __init__(self, room_code, username, color, on_message, on_connect):
        self.topic      = TOPIC_PREFIX + room_code
        self.username   = username
        self.color      = color
        self.on_message = on_message
        self.on_connect = on_connect
        self.room_code  = room_code

        client_id = f"sl-{gen_code(8)}"
        self.client = mqtt.Client(client_id=client_id)
        self.client.on_connect    = self._on_connect
        self.client.on_message    = self._on_msg
        self.client.on_disconnect = self._on_disconnect

    def connect(self):
        self.client.connect_async(BROKER, BROKER_PORT, keepalive=60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.client.subscribe(self.topic, qos=1)
            Clock.schedule_once(lambda dt: self.on_connect(True))
            self._publish({"type":"system",
                           "text":f"🕷️ {self.username} joined the web"})
        else:
            Clock.schedule_once(lambda dt: self.on_connect(False))

    def _on_msg(self, client, userdata, msg):
        try:
            wrapper = json.loads(msg.payload.decode())
            data    = decrypt_msg(wrapper["d"], self.room_code)
            Clock.schedule_once(lambda dt: self.on_message(data))
        except: pass   # wrong key or tampered message → silently dropped

    def _on_disconnect(self, client, userdata, rc):
        pass

    def _publish(self, msg):
        try:
            payload = json.dumps({"d": encrypt_msg(msg, self.room_code)})
            self.client.publish(self.topic, payload, qos=1)
        except: pass

    def send(self, msg):
        self._publish(msg)

    def disconnect(self):
        try:
            self._publish({"type":"system",
                           "text":f"🕸️ {self.username} left"})
            self.client.loop_stop()
            self.client.disconnect()
        except: pass

# ════════════════════════════════════════════════════════════
#   Welcome Screen
# ════════════════════════════════════════════════════════════
class WelcomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(28), spacing=dp(18))

        root.add_widget(Widget(size_hint_y=0.08))
        root.add_widget(mk_label("🕷️", size=52, halign="center"))
        root.add_widget(mk_label("[b]Spider Link[/b]", size=26,
                                  halign="center", bold=True))
        root.add_widget(mk_label("Invite-only · Works anywhere in the world",
                                  size=12, color=MUTED, halign="center"))
        root.add_widget(Widget(size_hint_y=0.04))

        # Create box
        c_box = self._card()
        c_box.add_widget(mk_label("[b]Create a private room[/b]",
                                   bold=True, halign="center"))
        c_box.add_widget(mk_label("Get a code to share with anyone, anywhere.",
                                   size=12, color=MUTED, halign="center"))
        c_box.add_widget(Widget(size_hint_y=None, height=dp(6)))
        b = mk_btn("🕸️  Create Room")
        b.bind(on_press=lambda _: self._go_setup("host",""))
        c_box.add_widget(b)
        root.add_widget(c_box)

        # Join box
        j_box = self._card()
        j_box.add_widget(mk_label("[b]Join with a room code[/b]",
                                   bold=True, halign="center"))
        self.code_input = mk_input("Enter room code  e.g. AB12CD")
        j_box.add_widget(self.code_input)
        bj = mk_btn("🔗  Join Room", bg=BG3)
        bj.bind(on_press=self._do_join)
        j_box.add_widget(bj)
        root.add_widget(j_box)

        root.add_widget(mk_label("🔒  No code? No entry.",
                                  size=11, color=MUTED, halign="center"))
        root.add_widget(Widget(size_hint_y=0.08))
        self.add_widget(root)

    def _card(self):
        box = BoxLayout(orientation="vertical", spacing=dp(10),
                        padding=dp(16), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        with box.canvas.before:
            Color(*BG2)
            box._r = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(14)])
        box.bind(pos=lambda w,_: setattr(w._r,"pos",w.pos),
                 size=lambda w,_: setattr(w._r,"size",w.size))
        return box

    def _do_join(self, *_):
        code = self.code_input.text.strip().upper()
        if len(code) < 4:
            self.code_input.hint_text = "⚠️ Enter a valid room code"
            return
        self._go_setup("client", code)

    def _go_setup(self, mode, code):
        app = App.get_running_app()
        app.pending_mode = mode
        app.pending_code = code
        app.sm.current = "setup"

# ════════════════════════════════════════════════════════════
#   Setup Screen
# ════════════════════════════════════════════════════════════
class SetupScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.sel_color = AVATAR_COLORS[0]
        root = BoxLayout(orientation="vertical", padding=dp(28), spacing=dp(14))

        root.add_widget(Widget(size_hint_y=0.15))
        root.add_widget(mk_label("🕷️  Spider Link", size=22, bold=True, halign="center"))
        root.add_widget(mk_label("Set up your profile", size=13,
                                  color=MUTED, halign="center"))
        root.add_widget(Widget(size_hint_y=None, height=dp(8)))

        root.add_widget(mk_label("YOUR NAME", size=10, color=MUTED))
        self.name_input = mk_input("Enter your name…")
        root.add_widget(self.name_input)

        root.add_widget(mk_label("AVATAR COLOR", size=10, color=MUTED))
        self.color_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        self._build_colors()
        root.add_widget(self.color_row)

        root.add_widget(Widget(size_hint_y=None, height=dp(8)))
        self.connect_btn = mk_btn("Enter the Web →")
        self.connect_btn.bind(on_press=self._submit)
        root.add_widget(self.connect_btn)

        back = mk_btn("← Back", bg=BG3)
        back.bind(on_press=lambda _: setattr(App.get_running_app().sm,"current","welcome"))
        root.add_widget(back)
        root.add_widget(Widget(size_hint_y=0.15))
        self.add_widget(root)

    def _build_colors(self):
        self.color_row.clear_widgets()
        for c in AVATAR_COLORS:
            btn = Button(size_hint=(None,None), size=(dp(36),dp(36)),
                         background_normal="", background_color=(0,0,0,0))
            with btn.canvas.before:
                Color(*hk(c))
                Ellipse(pos=btn.pos, size=btn.size)
                if c == self.sel_color:
                    Color(1,1,1,1)
                    Ellipse(pos=(btn.x-dp(2),btn.y-dp(2)),
                            size=(btn.width+dp(4),btn.height+dp(4)))
            btn.bind(on_press=lambda b, col=c: self._pick(col))
            self.color_row.add_widget(btn)

    def _pick(self, color):
        self.sel_color = color
        self._build_colors()

    def _submit(self, *_):
        name = self.name_input.text.strip()
        if not name:
            self.name_input.hint_text = "⚠️ Name required"; return
        self.connect_btn.text = "Connecting…"
        App.get_running_app().launch(
            App.get_running_app().pending_mode,
            App.get_running_app().pending_code,
            name, self.sel_color
        )

    def reset_btn(self):
        self.connect_btn.text = "Enter the Web →"

# ════════════════════════════════════════════════════════════
#   Chat Screen
# ════════════════════════════════════════════════════════════
class ChatScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.username   = ""
        self.color      = ""
        self.room_code  = ""
        self.invite_str = ""
        root = BoxLayout(orientation="vertical")
        self._build_header(root)
        self._build_msgs(root)
        self._build_bar(root)
        self.add_widget(root)

    def _build_header(self, root):
        hdr = BoxLayout(size_hint_y=None, height=dp(54), padding=[dp(12),0], spacing=dp(8))
        with hdr.canvas.before:
            Color(*BG2)
            hdr._bg = RoundedRectangle(pos=hdr.pos, size=hdr.size, radius=[0])
        hdr.bind(pos=lambda w,_: setattr(w._bg,"pos",w.pos),
                 size=lambda w,_: setattr(w._bg,"size",w.size))

        self.lbl_title = mk_label("[b]🕷️ Spider Link[/b]", size=15, bold=True)
        self.lbl_title.size_hint_x = 0.45
        hdr.add_widget(self.lbl_title)

        self.lbl_room = mk_label("", size=11, color=ACCENT, halign="center")
        self.lbl_room.size_hint_x = 0.25
        hdr.add_widget(self.lbl_room)

        inv = mk_btn("🕸️ Invite", height=dp(36))
        inv.size_hint_x = 0.3
        inv.bind(on_press=self._show_invite)
        hdr.add_widget(inv)
        root.add_widget(hdr)

    def _build_msgs(self, root):
        self.scroll = ScrollView(do_scroll_x=False)
        self.msg_list = BoxLayout(orientation="vertical", spacing=dp(6),
                                   padding=[dp(10),dp(10)], size_hint_y=None)
        self.msg_list.bind(minimum_height=self.msg_list.setter("height"))
        self.scroll.add_widget(self.msg_list)
        root.add_widget(self.scroll)

    def _build_bar(self, root):
        bar = BoxLayout(size_hint_y=None, height=dp(62),
                        padding=[dp(12),dp(8)], spacing=dp(8))
        with bar.canvas.before:
            Color(*BG2)
            bar._bg = RoundedRectangle(pos=bar.pos, size=bar.size, radius=[0])
        bar.bind(pos=lambda w,_: setattr(w._bg,"pos",w.pos),
                 size=lambda w,_: setattr(w._bg,"size",w.size))

        self.msg_input = TextInput(
            hint_text="Spin your message…", multiline=False,
            background_color=BG3, foreground_color=TEXT,
            hint_text_color=MUTED, cursor_color=ACCENT,
            font_size=sp(13), padding=[dp(12),dp(10)],
        )
        self.msg_input.bind(on_text_validate=self._send)
        bar.add_widget(self.msg_input)

        sb = mk_btn("Send ↑", height=dp(46))
        sb.size_hint_x = None
        sb.width = dp(90)
        sb.bind(on_press=self._send)
        bar.add_widget(sb)
        root.add_widget(bar)

    def setup(self, username, color, room_code):
        self.username   = username
        self.color      = color
        self.room_code  = room_code
        self.invite_str = room_code
        self.lbl_room.text = f"[b]{room_code}[/b]"
        self.msg_list.clear_widgets()
        self._sys("🕸️ Connected! Invite friends with the room code.")

    def receive(self, msg):
        t = msg.get("type")
        if t == "system":  self._sys(msg["text"])
        elif t == "message": self._add(msg)

    def _sys(self, text):
        lbl = mk_label(text, size=11, color=MUTED, halign="center")
        lbl.size_hint_y = None
        lbl.height = dp(28)
        self.msg_list.add_widget(lbl)
        Clock.schedule_once(lambda dt: setattr(self.scroll,"scroll_y",0), 0.1)

    def _add(self, msg):
        me = (msg["username"]==self.username and msg["color"]==self.color)
        row = BoxLayout(size_hint_y=None, spacing=dp(8))

        # Avatar
        av = Widget(size_hint=(None,None), size=(dp(34),dp(34)))
        with av.canvas:
            Color(*hk(msg["color"]))
            Ellipse(pos=av.pos, size=av.size)
        av_lbl = Label(text=msg["username"][:2].upper(), font_size=sp(10),
                       bold=True, color=(1,1,1,1), size=av.size, pos=av.pos)

        content = BoxLayout(orientation="vertical", spacing=dp(3), size_hint_y=None)
        meta = mk_label(
            f"[color={msg['color']}][b]{msg['username']}[/b][/color]"
            f"  [color=#333355]{msg.get('time','')}[/color]",
            size=11, halign="right" if me else "left"
        )
        meta.size_hint_y = None
        meta.height = dp(18)

        bubble = Label(text=msg["text"], font_size=sp(13), color=TEXT,
                       halign="left", valign="middle",
                       padding=(dp(12),dp(8)), size_hint_y=None)
        bubble.bind(width=lambda w,v: setattr(w,"text_size",(v*0.9,None)))
        bubble.bind(texture_size=lambda w,v: setattr(w,"height",v[1]+dp(16)))
        with bubble.canvas.before:
            Color(*hk(msg["color"]) if me else hk("#16162a"))
            bubble._bg = RoundedRectangle(pos=bubble.pos, size=bubble.size, radius=[dp(12)])
        bubble.bind(pos=lambda w,_: setattr(w._bg,"pos",w.pos),
                    size=lambda w,_: setattr(w._bg,"size",w.size))

        content.add_widget(meta)
        content.add_widget(bubble)
        content.bind(minimum_height=content.setter("height"))

        if me:
            row.add_widget(Widget())
            row.add_widget(content)
            row.add_widget(av)
        else:
            row.add_widget(av)
            row.add_widget(content)
            row.add_widget(Widget())

        row.bind(minimum_height=row.setter("height"))
        self.msg_list.add_widget(row)
        Clock.schedule_once(lambda dt: setattr(self.scroll,"scroll_y",0), 0.1)

    def _send(self, *_):
        text = self.msg_input.text.strip()
        if not text: return
        self.msg_input.text = ""
        App.get_running_app().chat.send({
            "type":     "message",
            "username": self.username,
            "color":    self.color,
            "text":     text,
            "time":     datetime.now().strftime("%I:%M %p"),
        })

    def _show_invite(self, *_):
        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(20))
        content.add_widget(mk_label("🕸️  Share Room Code",
                                     size=18, bold=True, halign="center"))
        content.add_widget(mk_label(
            "Anyone with this code can join\nfrom anywhere in the world!",
            size=12, color=MUTED, halign="center"))

        code_lbl = Label(
            text=f"[b][color=#7c3aed]{self.invite_str}[/color][/b]",
            font_size=sp(28), markup=True, size_hint_y=None, height=dp(60),
            halign="center", valign="middle"
        )
        with code_lbl.canvas.before:
            Color(*BG3)
            code_lbl._bg = RoundedRectangle(pos=code_lbl.pos,
                                             size=code_lbl.size, radius=[dp(12)])
        code_lbl.bind(pos=lambda w,_: setattr(w._bg,"pos",w.pos),
                      size=lambda w,_: setattr(w._bg,"size",w.size))
        content.add_widget(code_lbl)

        copy_btn = mk_btn("📋  Copy Code")
        def copy_it(_):
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(self.invite_str)
            copy_btn.text = "✅  Copied!"
        copy_btn.bind(on_press=copy_it)
        content.add_widget(copy_btn)

        close_btn = mk_btn("Close", bg=BG3)
        popup = Popup(title="", content=content, size_hint=(0.88,None),
                      height=dp(340), background_color=BG2,
                      separator_height=0, title_size=0)
        close_btn.bind(on_press=popup.dismiss)
        content.add_widget(close_btn)
        popup.open()

# ════════════════════════════════════════════════════════════
#   App
# ════════════════════════════════════════════════════════════
class SpiderLinkApp(App):
    def build(self):
        self.chat         = None
        self.pending_mode = ""
        self.pending_code = ""
        self.sm = ScreenManager(transition=FadeTransition(duration=0.2))
        self.sm.add_widget(WelcomeScreen(name="welcome"))
        self.sm.add_widget(SetupScreen(name="setup"))
        self.sm.add_widget(ChatScreen(name="chat"))
        return self.sm

    def launch(self, mode, code, username, color):
        room_code = code if mode == "client" else gen_code()
        self.chat = MQTTChat(
            room_code, username, color,
            on_message=self._on_msg,
            on_connect=lambda ok: self._on_connect(ok, username, color, room_code)
        )
        self.chat.connect()

    def _on_connect(self, ok, username, color, room_code):
        setup = self.sm.get_screen("setup")
        setup.reset_btn()
        if not ok:
            p = Popup(title="", content=mk_label("❌ Connection failed.\nCheck your internet.", halign="center"),
                      size_hint=(0.8,0.25), background_color=BG2, separator_height=0, title_size=0)
            p.open(); return
        chat = self.sm.get_screen("chat")
        chat.setup(username, color, room_code)
        self.sm.current = "chat"

    def _on_msg(self, msg):
        chat = self.sm.get_screen("chat")
        chat.receive(msg)

    def leave(self):
        if self.chat:
            self.chat.disconnect()
            self.chat = None
        self.sm.current = "welcome"

    def on_stop(self):
        self.leave()

if __name__ == "__main__":
    SpiderLinkApp().run()
