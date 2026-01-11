import hashlib
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import shutil
import vdf
import winreg
import sys
from pathlib import Path
from typing import Dict, Optional, List
import logging
from dataclasses import dataclass


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


@dataclass
class AccountInfo:
    steam3_id: str
    steam64_id: Optional[str]
    userdata_path: str
    persona_name: str


class CTkMenu(ctk.CTkToplevel):
    def __init__(self, parent, button, options: List[tuple]):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(fg_color="#2b2b2b")

        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()

        button_width = 140
        button_height = 30
        padding = 1

        total_width = button_width + (padding * 2)
        total_height = (button_height * len(options)) + (padding * 2 * len(options))

        self.geometry(f"{total_width }x{total_height }+{x }+{y }")

        inner_frame = ctk.CTkFrame(
            self,
            fg_color="#2b2b2b",
            border_width=1,
            border_color="#3b3b3b",
            corner_radius=0,
            width=total_width,
            height=total_height,
        )
        inner_frame.pack(fill="both", expand=True)

        for text, command in options:
            btn = ctk.CTkButton(
                inner_frame,
                text=text,
                command=lambda c=command: self._execute(c),
                width=button_width,
                height=button_height,
                fg_color="transparent",
                hover_color="#383838",
                anchor="w",
                corner_radius=0,
            )
            btn.pack(fill="x", padx=padding, pady=padding)

        self.bind("<FocusOut>", lambda e: self.destroy())
        self.after(10, self.focus_set)

    def _execute(self, command):
        self.destroy()
        command()


class DebugConsole(ctk.CTkToplevel):
    def __init__(self, parent, log_history: List[str]):
        super().__init__(parent)
        self.title("Debug Console")
        self.geometry("1100x620")

        self._setup_icon()
        self._setup_ui()
        self._populate_history(log_history)
        self._attach_as_handler()

    def _setup_icon(self):
        try:
            icon_path = Path(__file__).parent / "Script Files" / "custom_icon.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except Exception as e:
            logging.warning(f"Failed to load icon for debug console: {e }")

    def _setup_ui(self):
        self.console_output = ctk.CTkTextbox(self, activate_scrollbars=True)
        self.console_output.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

    def _populate_history(self, log_history: List[str]):
        self.console_output.configure(state="normal")
        if log_history:
            self.console_output.insert(tk.END, "\n".join(log_history) + "\n")
        self.console_output.see(tk.END)
        self.console_output.configure(state="disabled")

    def _attach_as_handler(self):
        self.console_handler = logging.StreamHandler(self)
        self.console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(self.console_handler)

    def write(self, text):
        if self.winfo_exists():
            self.console_output.configure(state="normal")
            self.console_output.insert(tk.END, text)
            self.console_output.see(tk.END)
            self.console_output.configure(state="disabled")

    def flush(self):
        pass

    def on_close(self):
        if hasattr(self, "console_handler"):
            logging.getLogger().removeHandler(self.console_handler)
        self.destroy()


class SteamManager:
    GAME_ID = "2551020"
    REGISTRY_PATHS = ["SOFTWARE\\WOW6432Node\\Valve\\Steam", "SOFTWARE\\Valve\\Steam"]

    def __init__(self):
        self.steam_path = self._find_steam_path()

    def _find_steam_path(self) -> Optional[str]:
        for path in self.REGISTRY_PATHS:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as hkey:
                    return winreg.QueryValueEx(hkey, "InstallPath")[0]
            except (WindowsError, FileNotFoundError):
                continue
        return None

    def load_accounts(self) -> Dict[str, AccountInfo]:
        if not self.steam_path:
            raise FileNotFoundError("Steam installation not found")

        accounts = {}
        known_steam3_ids = set()

        login_file = Path(self.steam_path) / "config" / "loginusers.vdf"
        if login_file.exists():
            try:
                with open(login_file, "r", encoding="utf-8") as f:
                    users_data = vdf.load(f)
                if "users" in users_data:
                    for steam_id64, user_data in users_data["users"].items():
                        account_name = user_data.get("PersonaName", "Unknown")
                        steam3_id = str(int(steam_id64) & 0xFFFFFFFF)
                        userdata_path = (
                            Path(self.steam_path)
                            / "userdata"
                            / steam3_id
                            / self.GAME_ID
                            / "remote"
                        )

                        accounts[account_name] = AccountInfo(
                            steam3_id=steam3_id,
                            steam64_id=steam_id64,
                            userdata_path=str(userdata_path),
                            persona_name=account_name,
                        )
                        known_steam3_ids.add(steam3_id)
            except Exception as e:
                logging.warning(f"Could not parse loginusers.vdf: {e }")

        userdata_root = Path(self.steam_path) / "userdata"
        if userdata_root.exists() and userdata_root.is_dir():
            for item in userdata_root.iterdir():
                if item.is_dir() and item.name.isdigit():
                    steam3_id = item.name
                    if steam3_id not in known_steam3_ids:
                        account_name = f"Unknown Account {steam3_id }"
                        userdata_path = item / self.GAME_ID / "remote"

                        accounts[account_name] = AccountInfo(
                            steam3_id=steam3_id,
                            steam64_id=None,
                            userdata_path=str(userdata_path),
                            persona_name=account_name,
                        )

        if not accounts:
            raise FileNotFoundError(
                "No Steam accounts found in loginusers.vdf or userdata folder."
            )

        return accounts

    def ensure_game_directories(self, steam3_id: str) -> str:
        if not self.steam_path:
            raise ValueError("Steam path not available")
        remote_path = (
            Path(self.steam_path) / "userdata" / steam3_id / self.GAME_ID / "remote"
        )
        remote_path.mkdir(parents=True, exist_ok=True)
        return str(remote_path)

    def create_backup(self, steam3_id: str, backup_root: Path):
        if not self.steam_path:
            return
        backup_folder = backup_root / steam3_id
        backup_source = Path(self.steam_path) / "userdata" / steam3_id / self.GAME_ID
        if backup_source.exists() and not backup_folder.exists():
            try:
                shutil.copytree(backup_source, backup_folder)
                logging.info(f"Backup created: {backup_folder }")
            except Exception as e:
                logging.error(f"Failed to create backup: {e }")


class SaveFileManager:
    SAVE_TYPES = ["Cash", "Level", "InventoryItems", "Maps"]

    def __init__(self, script_files_dir: Path):
        self.script_files_dir = script_files_dir

    def generate_save_filenames(
        self, steam64_id: str, remote_dir: str
    ) -> Dict[str, str]:
        return {
            f"{save_type }Save": os.path.join(
                remote_dir,
                hashlib.md5(f"{steam64_id }{save_type }".encode()).hexdigest() + ".sav",
            )
            for save_type in self.SAVE_TYPES
        }

    def apply_save_modification(
        self,
        file_type: str,
        steam64_id: str,
        remote_dir: str,
        duplicate_file: Optional[str] = None,
        old_key: Optional[bytes] = None,
        new_key: Optional[bytes] = None,
    ):
        script_path = self.script_files_dir / f"{file_type }.sav"
        if not script_path.exists():
            raise FileNotFoundError(f"Script file not found: {script_path }")

        with open(script_path, "rb") as file:
            contents = file.read()

        contents = contents.replace(b"my_stupid_user_id", steam64_id.encode())
        if old_key is not None and new_key is not None:
            contents = contents.replace(old_key, new_key)

        files_to_write = [Path(remote_dir) / f"{steam64_id }{file_type }.sav"]
        if duplicate_file and Path(duplicate_file).parent.exists():
            files_to_write.append(Path(duplicate_file))

        for file_path in files_to_write:
            self._write_save_file(file_path, contents)

    def _write_save_file(self, file_path: Path, contents: bytes):
        try:
            with open(file_path, "wb") as file:
                file.write(contents)
            logging.info(f"Save file written: {file_path }")
        except Exception as e:
            logging.error(f"Failed to write save file {file_path }: {e }")
            raise


class OARTool:
    def __init__(self):
        self.log_history: List[str] = []
        self._setup_logging()

        self.steam_manager = SteamManager()
        logging.info(f"Steam path: {self .steam_manager .steam_path }")
        self.script_files_dir = Path(__file__).parent / "Script Files"
        self.save_manager = SaveFileManager(self.script_files_dir)

        self.account_data: Dict[str, AccountInfo] = {}
        self.duplicate_files: Dict[str, str] = {}
        self.remote_directory: Optional[str] = None
        self.is_advanced_mode = False
        self.debug_console: Optional[DebugConsole] = None

        self._setup_window()
        self._initialize_app()

    def _setup_logging(self):
        class ListHandler(logging.Handler):
            def __init__(self, log_list):
                super().__init__()
                self.log_list = log_list

            def emit(self, record):
                self.log_list.append(self.format(record))

        log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        list_log_handler = ListHandler(self.log_history)
        list_log_handler.setFormatter(log_formatter)
        root_logger.addHandler(list_log_handler)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(log_formatter)
        root_logger.addHandler(stream_handler)

        logging.info("OAR Tool logging initialized.")

    def _setup_window(self):
        self.window = ctk.CTk()
        self.window.resizable(False, False)
        self.window.title("OAR Tool 3.4")
        self.window.geometry("300x250")

        self.main_frame = None
        self.menu_frame = None

        self._setup_icon()
        self._create_menu_bar()

    def _setup_icon(self):
        try:
            icon_path = self.script_files_dir / "custom_icon.ico"
            if icon_path.exists():
                self.window.iconbitmap(str(icon_path))
        except Exception as e:
            logging.warning(f"Failed to load icon: {e }")

    def _initialize_app(self):
        if not self.steam_manager.steam_path:
            messagebox.showinfo(
                "Steam Not Found",
                "Steam could not be automatically detected. Use advanced mode to continue.",
            )
            self.set_mode(True)
        else:
            self.show_selection_screen()

    def _create_menu_bar(self):
        self.menu_frame = ctk.CTkFrame(
            self.window, fg_color=("#202020", "#202020"), height=24
        )
        self.menu_frame.pack(fill="x", side="top")
        self.menu_frame.pack_propagate(False)

        mode_button = ctk.CTkButton(
            self.menu_frame,
            text="Mode",
            command=lambda: self._show_mode_menu(mode_button),
            width=60,
            height=24,
            fg_color=("#202020", "#202020"),
            hover_color=("#383838", "#383838"),
            corner_radius=0,
        )
        mode_button.pack(side="left")

        help_button = ctk.CTkButton(
            self.menu_frame,
            text="Help",
            command=lambda: self._show_help_menu(help_button),
            width=60,
            height=24,
            fg_color=("#202020", "#202020"),
            hover_color=("#383838", "#383838"),
            corner_radius=0,
        )
        help_button.pack(side="left")

    def _show_mode_menu(self, button):
        options = [
            ("Normal Mode", lambda: self.set_mode(False)),
            ("Advanced Mode", lambda: self.set_mode(True)),
        ]
        CTkMenu(self.window, button, options)

    def _show_help_menu(self, button):
        options = [
            ("About", self._show_about),
            ("Debug Console", self._show_debug_console),
        ]
        CTkMenu(self.window, button, options)

    def _show_debug_console(self):
        if self.debug_console is None or not self.debug_console.winfo_exists():
            self.debug_console = DebugConsole(self.window, self.log_history)
            self.debug_console.protocol("WM_DELETE_WINDOW", self.debug_console.on_close)
        else:
            self.debug_console.lift()

    def set_mode(self, advanced: bool):
        if self.is_advanced_mode != advanced:
            mode_name = "Advanced" if advanced else "Normal"
            logging.info(f"Application mode changed to {mode_name }")
            self.is_advanced_mode = advanced

        if advanced:
            self.show_advanced_screen()
        elif self.steam_manager.steam_path:
            self.show_selection_screen()
        else:
            messagebox.showerror(
                "Error", "Steam installation not found! You must use Advanced Mode."
            )
            self.show_advanced_screen()

    def _show_about(self):
        about_window = ctk.CTkToplevel(self.window)
        about_window.title("About OAR Tool")
        about_window.geometry("400x230")
        about_window.resizable(False, False)

        try:
            icon_path = self.script_files_dir / "custom_icon.ico"
            if icon_path.exists():
                about_window.after(200, lambda: about_window.iconbitmap(str(icon_path)))
        except Exception:
            pass

        content_frame = ctk.CTkFrame(about_window, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(content_frame, text="OAR Tool", font=("Arial", 24, "bold")).pack(
            pady=(5, 2)
        )

        ctk.CTkLabel(
            content_frame, text="Version 3.4", font=("Arial", 12), text_color="gray"
        ).pack(pady=(0, 15))

        ctk.CTkLabel(
            content_frame,
            text="Made By FireNinja7365\nHarbour map added by BaselAshraf81",
            font=("Arial", 14),
        ).pack(pady=3)

        github_label = ctk.CTkLabel(
            content_frame,
            text="https://github.com/FireNinja7365/OAR-Tool",
            font=("Arial", 11),
            text_color="#3b8ed0",
            cursor="hand2",
        )
        github_label.pack(pady=8)

        def open_github(event):
            import webbrowser

            webbrowser.open("https://github.com/FireNinja7365/OAR-Tool")

        github_label.bind("<Button-1>", open_github)

        ctk.CTkButton(
            content_frame,
            text="Close",
            command=about_window.destroy,
            width=120,
            height=32,
        ).pack(pady=(15, 0))

    def _clear_window(self):
        if self.main_frame:
            self.main_frame.destroy()
        self.main_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def show_selection_screen(self):
        self._clear_window()
        self.window.geometry("300x250")

        ctk.CTkLabel(
            self.main_frame,
            text="Select your Steam account:",
            font=("Arial", 12, "bold"),
        ).pack(pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        self._load_accounts(scroll)

    def _load_accounts(self, parent_frame):
        if not self.steam_manager.steam_path:
            ctk.CTkLabel(
                parent_frame, text="Steam installation not found!", text_color="red"
            ).pack()
            return

        try:
            self.account_data = self.steam_manager.load_accounts()

            for account_name in sorted(self.account_data.keys()):
                ctk.CTkButton(
                    parent_frame,
                    text=account_name,
                    command=lambda name=account_name: self._select_account(name),
                ).pack(pady=5, fill="x")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Steam accounts: {e }")
            logging.error(f"Failed to load accounts: {e }")

    def show_advanced_screen(self, prefill_save_dir: Optional[str] = None):
        self._clear_window()
        self.window.geometry("500x375")

        ctk.CTkLabel(
            self.main_frame, text="Advanced Mode", font=("Arial", 14, "bold")
        ).pack(pady=10)

        if prefill_save_dir:
            ctk.CTkLabel(
                self.main_frame,
                text="Account not in login file. Please enter the Steam64 ID.",
                text_color="#3b8ed0",
            ).pack(pady=(0, 10))

        ctk.CTkLabel(self.main_frame, text="Steam64 ID:").pack(anchor="w", padx=20)
        self.steam_id_var = tk.StringVar()
        ctk.CTkEntry(self.main_frame, textvariable=self.steam_id_var).pack(
            fill="x", padx=20, pady=(0, 10)
        )

        ctk.CTkLabel(self.main_frame, text="Save Directory:").pack(anchor="w", padx=20)
        df = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        df.pack(fill="x", padx=20)
        self.save_dir_var = tk.StringVar(value=prefill_save_dir or "")
        ctk.CTkEntry(df, textvariable=self.save_dir_var).pack(
            side="left", fill="x", expand=True
        )
        ctk.CTkButton(
            df, text="Browse...", width=80, command=self._browse_save_directory
        ).pack(side="right", padx=(5, 0))

        ctk.CTkLabel(
            self.main_frame,
            text="In advanced mode, you can manually specify your Steam64 ID\nand the location of your save files.",
            justify=tk.CENTER,
        ).pack(pady=10)

        ctk.CTkLabel(
            self.main_frame,
            text="Warning: Only use if you know what you're doing!",
            text_color="red",
            font=("Arial", 10, "bold"),
        ).pack(pady=10)

        ctk.CTkButton(
            self.main_frame,
            text="Continue to Edit",
            command=self._process_advanced_selection,
        ).pack(fill="x", padx=20)

    def _browse_save_directory(self):
        directory = filedialog.askdirectory(
            title="Select Directory Containing Save Files",
            initialdir=self.steam_manager.steam_path or "/",
        )
        if directory:
            self.save_dir_var.set(directory)

    def _process_advanced_selection(self):
        steam64_id = self.steam_id_var.get().strip()
        save_dir = self.save_dir_var.get().strip()

        if not steam64_id or not steam64_id.isdigit():
            messagebox.showerror("Error", "Steam64 ID must be a valid number.")
            return

        if not save_dir or not Path(save_dir).is_dir():
            messagebox.showerror("Error", "Invalid save directory")
            return

        self.remote_directory = save_dir
        self.duplicate_files = self.save_manager.generate_save_filenames(
            steam64_id, save_dir
        )

        self.show_edit_screen(steam64_id)

    def show_edit_screen(self, steam64_id: str):
        self._clear_window()
        self.window.geometry("300x250")

        form_vars = {
            "cash": tk.IntVar(),
            "level": tk.IntVar(),
            "edit_cash": tk.BooleanVar(),
            "edit_level": tk.BooleanVar(),
            "edit_items": tk.BooleanVar(),
            "edit_maps": tk.BooleanVar(),
        }

        ctk.CTkLabel(
            self.main_frame, text="Made By FireNinja7365", font=("Arial", 10)
        ).pack()

        ctk.CTkCheckBox(
            self.main_frame,
            text="Unlock Items & Cosmetics",
            variable=form_vars["edit_items"],
        ).pack(anchor="w", padx=10, pady=2)

        ctk.CTkCheckBox(
            self.main_frame, text="Unlock Maps", variable=form_vars["edit_maps"]
        ).pack(anchor="w", padx=10, pady=2)

        f_cash = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_cash.pack(fill="x", padx=10, pady=2)
        ctk.CTkCheckBox(
            f_cash, text="Edit Cash:", variable=form_vars["edit_cash"]
        ).pack(side="left")
        ctk.CTkEntry(f_cash, textvariable=form_vars["cash"], width=100).pack(
            side="right"
        )

        f_lvl = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_lvl.pack(fill="x", padx=10, pady=2)
        ctk.CTkCheckBox(
            f_lvl, text="Edit Level:", variable=form_vars["edit_level"]
        ).pack(side="left")
        ctk.CTkEntry(f_lvl, textvariable=form_vars["level"], width=100).pack(
            side="right"
        )

        btn_f = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_f.pack(fill="x", side="bottom", pady=5)

        ctk.CTkButton(
            btn_f, text="Back", fg_color="#4a4a4a", command=self._go_back
        ).pack(side="left", fill="x", expand=True, padx=2)

        ctk.CTkButton(
            btn_f,
            text="Apply",
            command=lambda: self._apply_changes(form_vars, steam64_id),
        ).pack(side="right", fill="x", expand=True, padx=2)

    def _go_back(self):
        self.show_selection_screen()

    def _select_account(self, account_name: str):
        account_info = self.account_data.get(account_name)
        if not account_info:
            messagebox.showerror("Error", "Could not find account data")
            return

        try:
            if account_info.steam64_id is None:
                logging.warning(f"Unknown account selected: {account_name }")
                logging.info("Redirecting to Advanced Mode with pre-filled path.")
                self.steam_manager.ensure_game_directories(account_info.steam3_id)
                self.set_mode(True)
                self.show_advanced_screen(prefill_save_dir=account_info.userdata_path)
                return

            self.remote_directory = self.steam_manager.ensure_game_directories(
                account_info.steam3_id
            )

            logging.info(f"Account selected: {account_name }")
            logging.info(f"Account folder: {account_info .steam3_id }")
            logging.info(f"Account ID: {account_info .steam64_id }")

            backup_root = Path(__file__).parent / "OAR backup"
            backup_root.mkdir(exist_ok=True)
            self.steam_manager.create_backup(account_info.steam3_id, backup_root)

            self.duplicate_files = self.save_manager.generate_save_filenames(
                account_info.steam64_id, self.remote_directory
            )

            self.show_edit_screen(account_info.steam64_id)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to select account: {e }")
            logging.error(f"Account selection failed: {e }")

    def _validate_number_input(self, value: int) -> bool:
        if not (-2147483648 <= value <= 2147483647):
            messagebox.showinfo(
                "Information",
                "Invalid Value! Must be between -2,147,483,648 and 2,147,483,647",
            )
            return False
        return True

    def _apply_changes(self, form_vars: Dict[str, tk.Variable], steam64_id: str):
        if not self.remote_directory:
            messagebox.showerror("Error", "No save directory available")
            return

        logging.info(f"Applying changes for Steam64 ID: {steam64_id }")
        changes_made = False

        try:
            modifications = [
                ("edit_cash", "cash", "Cash", b"my_stupid_cash_id"),
                ("edit_level", "level", "Level", b"my_stupid_level_id"),
                ("edit_items", None, "InventoryItems", None),
                ("edit_maps", None, "Maps", None),
            ]

            for edit_var, value_var, file_type, old_key in modifications:
                if form_vars[edit_var].get():
                    new_key = None

                    if value_var:
                        value = form_vars[value_var].get()
                        if not self._validate_number_input(value):
                            return
                        new_key = value.to_bytes(4, byteorder="little", signed=True)
                        logging.info(f"Editing {file_type .lower ()} to: {value }")
                    else:
                        logging.info(f"Unlocking {file_type .lower ()}")

                    self.save_manager.apply_save_modification(
                        file_type,
                        steam64_id,
                        self.remote_directory,
                        self.duplicate_files.get(f"{file_type }Save"),
                        old_key,
                        new_key,
                    )
                    changes_made = True

            if changes_made:
                logging.info("Changes applied successfully!")
                messagebox.showinfo("Success", "Changes applied successfully!")
            else:
                logging.info("No changes were made")
                messagebox.showinfo(
                    "Nothing Changed",
                    "No changes were made!\nMaybe try selecting something?",
                )

        except Exception as e:
            error_msg = f"Failed to apply changes: {e }"
            logging.error(error_msg)
            messagebox.showerror("Error", error_msg)

    def run(self):
        self.window.mainloop()


def main():
    try:
        app = OARTool()
        app.run()
    except Exception as e:
        logging.critical(f"Application failed to start: {e }", exc_info=True)
        messagebox.showerror("Fatal Error", f"Application failed to start: {e }")


if __name__ == "__main__":
    main()
