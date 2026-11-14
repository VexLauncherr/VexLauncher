import os
import sys
import json
import threading
import subprocess
import urllib.parse
import re
import time
import ctypes
import webview
import requests
import customtkinter as ctk
from tkinter import messagebox
import minecraft_launcher_lib as mclib

LAUNCHER_NAME = "VexLauncher"
APPDATA = os.getenv("APPDATA")
BASE_DIR = os.path.join(APPDATA, LAUNCHER_NAME)
USERS_DIR = os.path.join(BASE_DIR, "users")
MODS_DIR = os.path.join(BASE_DIR, "mods")
ACCOUNT_FILE = os.path.join(USERS_DIR, "account.json")
SETTINGS_FILE = os.path.join(USERS_DIR, "settings.json")
CACHE_FILE = os.path.join(BASE_DIR, "versions_cache.json")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(USERS_DIR, exist_ok=True)
os.makedirs(MODS_DIR, exist_ok=True)

CLIENT_ID = "00000000441cc96b"
REDIRECT_URI = "https://login.live.com/oauth20_desktop.srf"

ctk.set_appearance_mode("dark")

THEMES = {
    "Cyber Blue": {
        "primary": "#1f6feb", "hover": "#388bfd", 
        "bg": "#0d1117", "sidebar": "#161b22", "card": "#21262d", "text": "#ffffff"
    },
    "Crimson Red": {
        "primary": "#da3633", "hover": "#f85149", 
        "bg": "#120a0a", "sidebar": "#1f1414", "card": "#2d1d1d", "text": "#ffffff"
    },
    "Emerald Green": {
        "primary": "#2ea043", "hover": "#3fb950", 
        "bg": "#0a120d", "sidebar": "#141f17", "card": "#1d2d21", "text": "#ffffff"
    },
    "Neon Purple": {
        "primary": "#8957e5", "hover": "#a371f7", 
        "bg": "#100a17", "sidebar": "#1c1424", "card": "#291d36", "text": "#ffffff"
    }
}


class VexLauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("VexLauncher v1.1 // Horizon Engine")
        self.geometry("1000x620")
        self.resizable(False, False)
        self.overrideredirect(True)

        self.account_data = self.load_account()
        self.settings_data = self.load_settings()
        self.versions_list = []
        self.current_theme = self.settings_data.get("theme", "Cyber Blue")
        self.active_tab = "play"

        # UI se kreira trenutačno bez blokiranja
        self.setup_ui()
        self.fix_taskbar_and_minimize()
        self.update_account_ui()
        
        # Pozadinsko učitavanje verzija da start bude u sekundi
        threading.Thread(target=self.load_versions_fast, daemon=True).start()

    def fix_taskbar_and_minimize(self):
        try:
            self.update()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self.withdraw()
            self.deiconify()
        except Exception:
            pass

    def minimize_window(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.user32.ShowWindow(hwnd, 6) # SW_MINIMIZE
        except Exception:
            try:
                self.iconify()
            except Exception:
                pass

    def load_account(self):
        if os.path.exists(ACCOUNT_FILE):
            try:
                with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def save_account(self, data):
        self.account_data = data
        with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        self.update_account_ui()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_settings(self):
        try:
            selected_ver = self.version_dropdown.get()
            selected_loader = self.loader_var.get()
            selected_ram = self.ram_slider.get()
            selected_theme = self.current_theme

            data = {
                "version": selected_ver,
                "loader": selected_loader,
                "ram": selected_ram,
                "theme": selected_theme
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def logout(self):
        if os.path.exists(ACCOUNT_FILE):
            os.remove(ACCOUNT_FILE)
        self.account_data = None
        self.update_account_ui()
        messagebox.showinfo("Logout", "Successfully logged out from VexLauncher.")

    def change_theme(self, choice):
        self.current_theme = choice
        cfg = THEMES[choice]

        self.configure(fg_color=cfg["bg"])
        self.sidebar.configure(fg_color=cfg["sidebar"])
        self.title_bar.configure(fg_color=cfg["sidebar"])
        self.btn_play.configure(fg_color=cfg["primary"], hover_color=cfg["hover"])
        
        self.nav_play.configure(fg_color=cfg["primary"] if self.active_tab == "play" else "transparent")
        self.nav_mods.configure(fg_color=cfg["primary"] if self.active_tab == "mods" else "transparent")
        self.nav_logs.configure(fg_color=cfg["primary"] if self.active_tab == "logs" else "transparent")
        self.nav_settings.configure(fg_color=cfg["primary"] if self.active_tab == "settings" else "transparent")

        for card in self.themed_cards:
            card.configure(fg_color=cfg["card"])

        self.save_settings()
        self.log_message(f"System: Theme changed to {choice}")

    def start_microsoft_login(self):
        try:
            login_url = (
                f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?"
                f"client_id={CLIENT_ID}&"
                f"response_type=code&"
                f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
                f"scope=XboxLive.signin%20offline_access&"
                f"prompt=select_account"
            )

            self.log_message("Opening Microsoft login window...")
            
            window = webview.create_window(
                "VexLauncher - Microsoft Login", 
                login_url, 
                width=500, 
                height=650, 
                resizable=True,
                on_top=True
            )
            
            captured_data = {"done": False}

            def check_url():
                while not captured_data["done"]:
                    try:
                        current_url = window.get_current_url()
                        if current_url and "code=" in current_url:
                            captured_data["done"] = True
                            window.destroy()
                            self.process_oauth_code(current_url)
                            break
                    except Exception:
                        pass
                    time.sleep(0.3)

            window.events.shown += lambda: threading.Thread(target=check_url, daemon=True).start()
            webview.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start login:\n{e}")

    def process_oauth_code(self, redirected_url):
        try:
            self.log_message("Processing Microsoft OAuth code...")
            parsed_url = urllib.parse.urlparse(redirected_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            if "code" not in query_params and parsed_url.fragment:
                fragment_params = urllib.parse.parse_qs(parsed_url.fragment)
                if "code" in fragment_params:
                    query_params = fragment_params

            if "code" not in query_params and "code=" in redirected_url:
                match = re.search(r'code=([^&]+)', redirected_url)
                if match:
                    auth_code = match.group(1)
                else:
                    raise Exception("Authorization code not found in URL.")
            elif "code" in query_params:
                auth_code = query_params["code"][0]
            else:
                raise Exception("Authorization code not found.")

            token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
            payload = {
                "client_id": CLIENT_ID,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI
            }
            resp = requests.post(token_url, data=payload).json()
            ms_token = resp.get("access_token")

            if not ms_token:
                err_desc = resp.get("error_description", resp.get("error", "Unknown error"))
                raise Exception(f"Failed to fetch Microsoft access token: {err_desc}")

            self.log_message("Connecting to Xbox Live...")
            xbl_resp = requests.post(
                "https://user.auth.xboxlive.com/user/authenticate",
                json={
                    "Properties": {
                        "AuthMethod": "RPS",
                        "SiteName": "user.auth.xboxlive.com",
                        "RpsTicket": f"d={ms_token}"
                    },
                    "RelyingParty": "http://auth.xboxlive.com",
                    "TokenType": "JWT"
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            ).json()
            xbl_token = xbl_resp["Token"]
            user_hash = xbl_resp["DisplayClaims"]["xui"][0]["uhs"]

            self.log_message("Fetching XSTS token...")
            xsts_resp = requests.post(
                "https://xsts.auth.xboxlive.com/xsts/authorize",
                json={
                    "Properties": {
                        "SandboxId": "RETAIL",
                        "UserTokens": [xbl_token]
                    },
                    "RelyingParty": "rp://api.minecraftservices.com/",
                    "TokenType": "JWT"
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            ).json()
            
            if "Token" not in xsts_resp:
                err_code = xsts_resp.get("XErr", "Unknown")
                raise Exception(f"XSTS error (XErr: {err_code}). Account might lack an Xbox profile.")
                
            xsts_token = xsts_resp["Token"]

            self.log_message("Fetching Minecraft token and profile...")
            mc_resp = requests.post(
                "https://api.minecraftservices.com/authentication/login_with_xbox",
                json={"identityToken": f"XBL3.0 x={user_hash};{xsts_token}"},
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            ).json()
            minecraft_token = mc_resp["access_token"]

            profile_resp = requests.get(
                "https://api.minecraftservices.com/minecraft/profile",
                headers={"Authorization": f"Bearer {minecraft_token}"}
            ).json()

            if "name" not in profile_resp:
                raise Exception("User does not own Minecraft on this account!")

            login_data = {
                "name": profile_resp["name"],
                "id": profile_resp["id"],
                "access_token": minecraft_token,
                "type": "microsoft"
            }

            self.after(0, lambda: self.save_account(login_data))
            self.log_message(f"Successfully logged in as: {login_data['name']}")
            self.after(
                0, 
                lambda name=login_data['name']: messagebox.showinfo(
                    "Success", 
                    f"Successfully logged in as {name}!"
                )
            )
        except Exception as e:
            err_msg = str(e)
            self.log_message(f"Login error: {err_msg}")
            self.after(
                0, 
                lambda msg=err_msg: messagebox.showerror("Login Error", f"An error occurred:\n{msg}")
            )

    def setup_ui(self):
        cfg = THEMES[self.current_theme]
        self.configure(fg_color=cfg["bg"])
        self.themed_cards = []

        self.title_bar = ctk.CTkFrame(self, height=35, fg_color=cfg["sidebar"], corner_radius=0)
        self.title_bar.pack(fill="x", side="top")
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)

        title_lbl = ctk.CTkLabel(self.title_bar, text="  VEXLAUNCHER v1.2 // HORIZON ENGINE", font=ctk.CTkFont(size=12, weight="bold"), text_color="#aaa")
        title_lbl.pack(side="left")
        title_lbl.bind("<Button-1>", self.start_move)
        title_lbl.bind("<B1-Motion>", self.do_move)

        btn_close = ctk.CTkButton(self.title_bar, text="✕", width=40, height=35, fg_color="transparent", hover_color="#da3633", command=self.destroy)
        btn_close.pack(side="right")
        btn_min = ctk.CTkButton(self.title_bar, text="—", width=40, height=35, fg_color="transparent", hover_color="#333", command=self.minimize_window)
        btn_min.pack(side="right")

        body_frame = ctk.CTkFrame(body_frame if 'body_frame' in locals() else self, fg_color="transparent", corner_radius=0) # safe fallback
        # Pravilno pakiranje body frame-a:
        body_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        body_frame.pack(fill="both", expand=True)

        self.sidebar = ctk.CTkFrame(body_frame, width=220, fg_color=cfg["sidebar"], corner_radius=0)
        self.sidebar.pack(side="left", fill="y")

        logo_lbl = ctk.CTkLabel(self.sidebar, text="⚡ VEXLAUNCHER v1.1", font=ctk.CTkFont(size=18, weight="bold"))
        logo_lbl.pack(pady=(25, 20))

        self.nav_play = ctk.CTkButton(self.sidebar, text="🎮  Play", height=45, fg_color=cfg["primary"], anchor="w", font=ctk.CTkFont(size=14, weight="bold"), command=lambda: self.switch_tab("play"))
        self.nav_play.pack(fill="x", padx=12, pady=5)

        self.nav_mods = ctk.CTkButton(self.sidebar, text="📦  Mods", height=45, fg_color="transparent", anchor="w", font=ctk.CTkFont(size=14, weight="bold"), hover_color="#333", command=lambda: self.switch_tab("mods"))
        self.nav_mods.pack(fill="x", padx=12, pady=5)

        self.nav_logs = ctk.CTkButton(self.sidebar, text="📋  Logs", height=45, fg_color="transparent", anchor="w", font=ctk.CTkFont(size=14, weight="bold"), hover_color="#333", command=lambda: self.switch_tab("logs"))
        self.nav_logs.pack(fill="x", padx=12, pady=5)

        self.nav_settings = ctk.CTkButton(self.sidebar, text="⚙️  Settings", height=45, fg_color="transparent", anchor="w", font=ctk.CTkFont(size=14, weight="bold"), hover_color="#333", command=lambda: self.switch_tab("settings"))
        self.nav_settings.pack(fill="x", padx=12, pady=5)

        self.status_label = ctk.CTkLabel(self.sidebar, text="Ready.", font=ctk.CTkFont(size=11), text_color="#777", wraplength=190, anchor="w")
        self.status_label.pack(side="bottom", padx=15, pady=20)

        self.content_area = ctk.CTkFrame(body_frame, fg_color="transparent", corner_radius=0)
        self.content_area.pack(side="right", fill="both", expand=True, padx=25, pady=20)

        self.setup_play_tab()
        self.setup_mods_tab()
        self.setup_logs_tab()
        self.setup_settings_tab()

        self.switch_tab("play")
        self.log_message("VexLauncher v1.1 successfully initialized.")

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        x = self.winfo_x() + (event.x - self.x)
        y = self.winfo_y() + (event.y - self.y)
        self.geometry(f"+{x}+{y}")

    def switch_tab(self, tab_name):
        self.active_tab = tab_name
        cfg = THEMES[self.current_theme]

        self.nav_play.configure(fg_color=cfg["primary"] if tab_name == "play" else "transparent")
        self.nav_mods.configure(fg_color=cfg["primary"] if tab_name == "mods" else "transparent")
        self.nav_logs.configure(fg_color=cfg["primary"] if tab_name == "logs" else "transparent")
        self.nav_settings.configure(fg_color=cfg["primary"] if tab_name == "settings" else "transparent")

        self.tab_play_frame.pack_forget()
        self.tab_mods_frame.pack_forget()
        self.tab_logs_frame.pack_forget()
        self.tab_settings_frame.pack_forget()

        if tab_name == "play":
            self.tab_play_frame.pack(fill="both", expand=True)
        elif tab_name == "mods":
            self.tab_mods_frame.pack(fill="both", expand=True)
        elif tab_name == "logs":
            self.tab_logs_frame.pack(fill="both", expand=True)
        elif tab_name == "settings":
            self.tab_settings_frame.pack(fill="both", expand=True)

    def setup_play_tab(self):
        cfg = THEMES[self.current_theme]
        self.tab_play_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")

        banner = ctk.CTkFrame(self.tab_play_frame, fg_color=cfg["card"], corner_radius=14, height=60)
        banner.pack(fill="x", pady=(0, 20))
        self.themed_cards.append(banner)

        self.lbl_user_status = ctk.CTkLabel(banner, text="Checking account...", font=ctk.CTkFont(size=14, weight="bold"), text_color="orange")
        self.lbl_user_status.pack(pady=15, padx=20, side="left")

        settings_bar = ctk.CTkFrame(self.tab_play_frame, fg_color=cfg["card"], corner_radius=14, height=70)
        settings_bar.pack(fill="x", pady=10)
        self.themed_cards.append(settings_bar)

        ctk.CTkLabel(settings_bar, text="Game Version:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=20)
        self.version_dropdown = ctk.CTkOptionMenu(settings_bar, values=["Loading..."], width=160, height=35, corner_radius=8, command=lambda _: self.save_settings())
        self.version_dropdown.pack(side="left", padx=10)

        saved_loader = self.settings_data.get("loader", "Vanilla")
        self.loader_var = ctk.StringVar(value=saved_loader)
        self.loader_switch = ctk.CTkSegmentedButton(settings_bar, values=["Vanilla", "Fabric", "Forge", "OptiFine"], variable=self.loader_var, command=lambda _: self.save_settings())
        self.loader_switch.pack(side="right", padx=20)

        ram_bar = ctk.CTkFrame(self.tab_play_frame, fg_color=cfg["card"], corner_radius=14, height=70)
        ram_bar.pack(fill="x", pady=10)
        self.themed_cards.append(ram_bar)

        self.ram_label = ctk.CTkLabel(ram_bar, text="Allocated RAM: 4 GB", font=ctk.CTkFont(size=13, weight="bold"))
        self.ram_label.pack(side="left", padx=20)
        
        saved_ram = self.settings_data.get("ram", 4)
        self.ram_slider = ctk.CTkSlider(ram_bar, from_=2, to=16, number_of_steps=14, command=self.on_ram_changed, width=320)
        self.ram_slider.set(saved_ram)
        self.ram_label.configure(text=f"Allocated RAM: {int(saved_ram)} GB")
        self.ram_slider.pack(side="right", padx=20)

        bottom_box = ctk.CTkFrame(self.tab_play_frame, fg_color="transparent")
        bottom_box.pack(fill="x", pady=(25, 0))

        self.btn_play = ctk.CTkButton(
            bottom_box, text="LAUNCH GAME (BLAZING FAST)", font=ctk.CTkFont(size=18, weight="bold"),
            height=50, width=320, corner_radius=14, fg_color=cfg["primary"], hover_color=cfg["hover"], command=self.launch_game_thread
        )
        self.btn_play.pack(pady=(0, 15))

        self.progress_bar = ctk.CTkProgressBar(bottom_box, width=450, height=8)
        self.progress_bar.set(0)
        self.progress_bar.pack()

    def on_ram_changed(self, val):
        self.update_ram_label(val)
        self.save_settings()

    def setup_mods_tab(self):
        self.tab_mods_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")

        top_bar = ctk.CTkFrame(self.tab_mods_frame, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 15))

        self.search_entry = ctk.CTkEntry(top_bar, placeholder_text="Search Modrinth mods (Sodium, Iris...)", width=380, height=38, corner_radius=10)
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<Return>", lambda e: self.search_modrinth())

        ctk.CTkButton(top_bar, text="Search", width=100, height=38, corner_radius=10, command=self.search_modrinth).pack(side="left")
        ctk.CTkButton(top_bar, text="📁 Mods Folder", width=120, height=38, corner_radius=10, fg_color="#333", hover_color="#444", command=lambda: os.startfile(MODS_DIR)).pack(side="right")

        self.mods_scroll = ctk.CTkScrollableFrame(self.tab_mods_frame, width=720, height=430, corner_radius=12)
        self.mods_scroll.pack(fill="both", expand=True)

        threading.Thread(target=self.search_modrinth, daemon=True).start()

    def setup_logs_tab(self):
        self.tab_logs_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")

        top_bar = ctk.CTkFrame(self.tab_logs_frame, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(top_bar, text="Live Console & Debug Logs", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(top_bar, text="Clear Logs", width=110, height=32, fg_color="#da3633", hover_color="#f85149", command=self.clear_logs).pack(side="right")

        self.log_textbox = ctk.CTkTextbox(self.tab_logs_frame, width=720, height=470, corner_radius=12, font=("Consolas", 12))
        self.log_textbox.pack(fill="both", expand=True)
        self.log_textbox.configure(state="disabled")

    def setup_settings_tab(self):
        cfg = THEMES[self.current_theme]
        self.tab_settings_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")

        card_acc = ctk.CTkFrame(self.tab_settings_frame, fg_color=cfg["card"], corner_radius=14)
        card_acc.pack(fill="x", pady=(0, 15), ipady=10)
        self.themed_cards.append(card_acc)

        ctk.CTkLabel(card_acc, text="Microsoft Account", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(12, 5))
        self.lbl_acc_details = ctk.CTkLabel(card_acc, text="Status: No active login", font=ctk.CTkFont(size=12), text_color="gray")
        self.lbl_acc_details.pack(pady=5)

        btn_row = ctk.CTkFrame(card_acc, fg_color="transparent")
        btn_row.pack(pady=12)
        ctk.CTkButton(btn_row, text="Login with Microsoft", width=200, height=38, corner_radius=10, command=self.start_microsoft_login).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="Logout", width=100, height=38, corner_radius=10, fg_color="#da3633", hover_color="#f85149", command=self.logout).pack(side="left", padx=10)

        card_theme = ctk.CTkFrame(self.tab_settings_frame, fg_color=cfg["card"], corner_radius=14)
        card_theme.pack(fill="x", pady=10, ipady=10)
        self.themed_cards.append(card_theme)

        ctk.CTkLabel(card_theme, text="Visual Style & Themes", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(12, 5))
        
        theme_row = ctk.CTkFrame(card_theme, fg_color="transparent")
        theme_row.pack(pady=10)
        ctk.CTkLabel(theme_row, text="Select Theme Color:", font=ctk.CTkFont(size=13)).pack(side="left", padx=20)
        
        self.theme_menu = ctk.CTkOptionMenu(theme_row, values=list(THEMES.keys()), command=self.change_theme, width=200, height=35, corner_radius=8)
        self.theme_menu.set(self.current_theme)
        self.theme_menu.pack(side="left", padx=20)

        ctk.CTkButton(self.tab_settings_frame, text="Open %appdata%\\VexLauncher", width=240, height=38, corner_radius=10, fg_color="#333", hover_color="#444", command=lambda: os.startfile(BASE_DIR)).pack(pady=15)

    def log_message(self, text):
        timestamp = time.strftime("[%H:%M:%S]")
        full_line = f"{timestamp} {text}\n"
        print(full_line, end="")
        try:
            self.after(0, lambda: self._append_log(full_line))
        except Exception:
            pass

    def _append_log(self, text):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", text)
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def clear_logs(self):
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    def set_status(self, text):
        self.log_message(f"Status: {text}")
        self.after(0, lambda: self.status_label.configure(text=text))

    def update_ram_label(self, val):
        self.ram_label.configure(text=f"Allocated RAM: {int(val)} GB")

    def update_account_ui(self):
        if self.account_data:
            name = self.account_data.get("name", "User")
            self.lbl_user_status.configure(text=f"Logged in as: {name} [MS]", text_color="#3fb950")
            self.lbl_acc_details.configure(text=f"Active Microsoft Account: {name}")
        else:
            self.lbl_user_status.configure(text="Not logged in! Go to 'Settings'", text_color="orange")
            self.lbl_acc_details.configure(text="Status: Account not found.")

    def load_versions_fast(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cached_ids = json.load(f)
                    if cached_ids:
                        self.versions_list = cached_ids
                        self.after(0, lambda: self.version_dropdown.configure(values=cached_ids))
                        saved_ver = self.settings_data.get("version", cached_ids[0])
                        if saved_ver in cached_ids:
                            self.after(0, lambda: self.version_dropdown.set(saved_ver))
                        self.log_message("Loaded version list instantly from local cache.")
            except Exception:
                pass

        try:
            self.log_message("Fetching fresh Minecraft version list...")
            versions = mclib.utils.get_version_list()
            all_ids = [v["id"] for v in versions if v["type"] == "release"]
            self.versions_list = all_ids
            self.after(0, lambda: self.version_dropdown.configure(values=all_ids))
            
            if all_ids:
                saved_ver = self.settings_data.get("version", all_ids[0])
                if saved_ver in all_ids:
                    self.after(0, lambda: self.version_dropdown.set(saved_ver))
                else:
                    self.after(0, lambda: self.version_dropdown.set(all_ids[0]))

            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(all_ids, f)

            self.log_message("Version list successfully updated & cached.")
        except Exception as e:
            self.log_message(f"Error fetching versions: {e}")

    def launch_game_thread(self):
        if not self.account_data:
            messagebox.showwarning("Login Required", "You must log in with your Microsoft account first!")
            self.switch_tab("settings")
            return

        self.save_settings()
        self.btn_play.configure(state="disabled")
        threading.Thread(target=self.launch_game, daemon=True).start()

    def launch_game(self):
        selected_version = self.version_dropdown.get()
        loader_choice = self.loader_var.get()
        ram_gb = int(self.ram_slider.get())

        try:
            launch_version = selected_version
            self.log_message(f"Preparing launch for version: {selected_version} ({loader_choice}), RAM: {ram_gb}GB")

            if loader_choice == "Fabric":
                versions_dir = os.path.join(BASE_DIR, "versions")
                matched = [v for v in os.listdir(versions_dir) if "fabric" in v.lower() and selected_version in v] if os.path.exists(versions_dir) else []
                if matched:
                    launch_version = matched[0]
                else:
                    self.set_status(f"Fetching Fabric {selected_version}...")
                    mclib.fabric.install_fabric(selected_version, BASE_DIR)
                    matched = [v for v in os.listdir(versions_dir) if "fabric" in v.lower() and selected_version in v]
                    if matched:
                        launch_version = matched[0]

            elif loader_choice == "Forge":
                versions_dir = os.path.join(BASE_DIR, "versions")
                matched = [v for v in os.listdir(versions_dir) if "forge" in v.lower() and selected_version in v] if os.path.exists(versions_dir) else []
                if matched:
                    launch_version = matched[0]
                else:
                    self.set_status(f"Fetching Forge {selected_version}...")
                    mclib.forge.install_forge_version(selected_version, BASE_DIR)
                    matched = [v for v in os.listdir(versions_dir) if "forge" in v.lower() and selected_version in v]
                    if matched:
                        launch_version = matched[0]

            elif loader_choice == "OptiFine":
                versions_dir = os.path.join(BASE_DIR, "versions")
                matched = [v for v in os.listdir(versions_dir) if "optifine" in v.lower() and selected_version in v] if os.path.exists(versions_dir) else []
                if matched:
                    launch_version = matched[0]
                else:
                    self.set_status(f"Fetching OptiFine {selected_version}...")
                    of_list = mclib.optifine.get_optifine_version_list(selected_version)
                    if of_list:
                        mclib.optifine.install_optifine(of_list[0]["fullName"], BASE_DIR)
                        matched = [v for v in os.listdir(versions_dir) if "optifine" in v.lower() and selected_version in v]
                        if matched:
                            launch_version = matched[0]

            else:
                vanilla_path = os.path.join(BASE_DIR, "versions", selected_version, f"{selected_version}.json")
                if not os.path.exists(vanilla_path):
                    self.set_status(f"Downloading Minecraft {selected_version}...")
                    mclib.install.install_minecraft_version(selected_version, BASE_DIR)

            options = {
                "username": self.account_data["name"],
                "uuid": self.account_data["id"],
                "token": self.account_data["access_token"],
                "userType": "msa",
                "clientToken": self.account_data.get("client_token", ""),
                "jvmArguments": [
                    f"-Xmx{ram_gb}G", "-Xms1G",
                    "-XX:+UseG1GC",
                    "-XX:+UnlockExperimentalVMOptions",
                    "-XX:G1NewSizePercent=40",
                    "-XX:G1ReservePercent=10",
                    "-XX:MaxGCPauseMillis=2",
                    "-XX:G1HeapRegionSize=16M",
                    "-XX:+UseStringDeduplication"
                ],
                "launcherName": "VexLauncher",
                "launcherVersion": "1.1",
            }

            self.set_status("Generating JVM command...")
            minecraft_command = mclib.command.get_minecraft_command(launch_version, BASE_DIR, options)

            self.log_message(f"Launching game process for account: {self.account_data['name']}")
            
            if os.name == 'nt':
                process = subprocess.Popen(
                    minecraft_command, 
                    cwd=BASE_DIR, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    creationflags=subprocess.HIGH_PRIORITY_CLASS | subprocess.DETACHED_PROCESS
                )
            else:
                process = subprocess.Popen(
                    minecraft_command, 
                    cwd=BASE_DIR, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True
                )

            def monitor_process():
                try:
                    for line in process.stdout:
                        if line:
                            self.log_message(f"[MC] {line.strip()}")
                except Exception:
                    pass

            threading.Thread(target=monitor_process, daemon=True).start()
            self.set_status("Minecraft launched successfully!")
        except Exception as e:
            err_msg = str(e)
            self.log_message(f"Critical launch error: {err_msg}")
            self.set_status("Launch error!")
            self.after(0, lambda msg=err_msg: messagebox.showerror("Error", f"An error occurred:\n{msg}"))
        finally:
            self.after(0, lambda: self.btn_play.configure(state="normal"))
            self.after(0, lambda: self.progress_bar.set(0))

    def search_modrinth(self):
        query = self.search_entry.get().strip()
        threading.Thread(target=self._fetch_modrinth_mods, args=(query,), daemon=True).start()

    def _fetch_modrinth_mods(self, query):
        self.log_message(f"Searching Modrinth for query: '{query}'")
        url = "https://api.modrinth.com/v2/search"
        params = {"query": query, "facets": '[["project_type:mod"]]', "limit": 30}
        headers = {"User-Agent": "VexLauncher/1.1"}

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            data = resp.json()
            hits = data.get("hits", [])
            self.after(0, lambda: self.display_mods(hits))
            self.log_message(f"Found {len(hits)} mods.")
        except Exception as e:
            self.log_message(f"Modrinth error: {e}")

    def display_mods(self, mods):
        cfg = THEMES[self.current_theme]
        for widget in self.mods_scroll.winfo_children():
            widget.destroy()

        for mod in mods:
            card = ctk.CTkFrame(self.mods_scroll, fg_color=cfg["card"], corner_radius=10)
            card.pack(fill="x", padx=5, pady=5)

            title = mod.get("title", "Mod")
            desc = mod.get("description", "")
            if len(desc) > 85:
                desc = desc[:82] + "..."
            downloads = mod.get("downloads", 0)
            project_id = mod.get("project_id")

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", padx=15, pady=10, fill="x", expand=True)

            ctk.CTkLabel(info_frame, text=f"{title}  (Downloads: {downloads:,})", font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(info_frame, text=desc, font=ctk.CTkFont(size=11), text_color="gray", anchor="w").pack(fill="x")

            ctk.CTkButton(
                card, text="Install", width=100, height=32, corner_radius=8,
                fg_color=cfg["primary"], hover_color=cfg["hover"],
                command=lambda pid=project_id, t=title: threading.Thread(
                    target=self.install_modrinth_mod, args=(pid, t), daemon=True
                ).start()
            ).pack(side="right", padx=15, pady=10)

    def install_modrinth_mod(self, project_id, title: str):
        selected_version = self.version_dropdown.get()
        self.log_message(f"Starting installation of mod '{title}' for version {selected_version}...")

        url = f"https://api.modrinth.com/v2/project/{project_id}/version"
        headers = {"User-Agent": "VexLauncher/1.2"}

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            versions = resp.json()

            target_version = None
            for v in versions:
                if selected_version in v.get("game_versions", []) and "fabric" in v.get("loaders", []):
                    target_version = v
                    break
            if not target_version and versions:
                target_version = versions[0]

            if not target_version:
                self.log_message(f"No compatible version found for mod '{title}'.")
                return

            file_info = target_version["files"][0]
            download_url = file_info["url"]
            filename = file_info["filename"]
            dest_path = os.path.join(MODS_DIR, filename)

            file_data = requests.get(download_url, headers=headers, timeout=20).content
            with open(dest_path, "wb") as f:
                f.write(file_data)

            self.log_message(f"Mod '{title}' successfully saved to mods folder!")
            self.after(0, lambda: messagebox.showinfo("Success", f"Mod '{title}' successfully installed!"))
        except Exception as e:
            err_msg = str(e)
            self.log_message(f"Mod installation error: {err_msg}")


if __name__ == "__main__":
    app = VexLauncherApp()
    app.mainloop()
