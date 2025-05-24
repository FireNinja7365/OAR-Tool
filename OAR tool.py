import hashlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import shutil
import vdf
import winreg
import sys
from pathlib import Path
from typing import Dict, Optional
import logging
from dataclasses import dataclass


@dataclass
class AccountInfo:
    steam3_id: str
    steam64_id: str
    userdata_path: str
    persona_name: str


class DebugConsole(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Debug Console")
        self.geometry("600x400")
        self.old_stdout = sys.stdout

        self._setup_icon()
        self._setup_ui()
        self._redirect_stdout()

    def _setup_icon(self):
        try:
            icon_path = Path(__file__).parent / "Script Files" / "custom_icon.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except Exception as e:
            logging.warning(f"Failed to load icon for debug console: {e}")

    def _setup_ui(self):
        self.console_output = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, width=80, height=20, state=tk.DISABLED
        )
        self.console_output.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(
            button_frame, text="Clear Console", command=self.clear_console
        ).pack(side=tk.RIGHT, padx=5)

    def _redirect_stdout(self):
        sys.stdout = self

        console_handler = logging.StreamHandler(self)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))

        logging.getLogger().addHandler(console_handler)
        self.console_handler = console_handler

    def write(self, text):
        self.console_output.config(state=tk.NORMAL)
        self.console_output.insert(tk.END, text)
        self.console_output.see(tk.END)
        self.console_output.config(state=tk.DISABLED)
        self.old_stdout.write(text)

    def flush(self):
        pass

    def clear_console(self):
        self.console_output.config(state=tk.NORMAL)
        self.console_output.delete(1.0, tk.END)
        self.console_output.config(state=tk.DISABLED)

    def on_close(self):
        sys.stdout = self.old_stdout

        if hasattr(self, 'console_handler'):
            logging.getLogger().removeHandler(self.console_handler)

        self.destroy()


class SteamManager:

    GAME_ID = "2551020"
    REGISTRY_PATHS = [
        "SOFTWARE\\WOW6432Node\\Valve\\Steam",
        "SOFTWARE\\Valve\\Steam"
    ]

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

        login_file = Path(self.steam_path) / "config" / "loginusers.vdf"

        if not login_file.exists():
            raise FileNotFoundError(f"Login users file not found: {login_file}")

        try:
            with open(login_file, "r", encoding="utf-8") as f:
                users_data = vdf.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse loginusers.vdf: {e}")

        accounts = {}
        if "users" in users_data:
            for steam_id64, user_data in users_data["users"].items():
                account_name = user_data.get("PersonaName", "Unknown")
                steam3_id = str(int(steam_id64) & 0xFFFFFFFF)
                userdata_path = Path(self.steam_path) / "userdata" / steam3_id / self.GAME_ID / "remote"

                accounts[account_name] = AccountInfo(
                    steam3_id=steam3_id,
                    steam64_id=steam_id64,
                    userdata_path=str(userdata_path),
                    persona_name=account_name
                )

        return accounts

    def ensure_game_directories(self, steam3_id: str) -> str:

        if not self.steam_path:
            raise ValueError("Steam path not available")

        remote_path = Path(self.steam_path) / "userdata" / steam3_id / self.GAME_ID / "remote"
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
                print(f"Backup created: {backup_folder}")
            except Exception as e:
                print(f"Failed to create backup: {e}")


class SaveFileManager:

    SAVE_TYPES = ["Cash", "Level", "InventoryItems", "Maps"]

    def __init__(self, script_files_dir: Path):
        self.script_files_dir = script_files_dir

    def generate_save_filenames(self, steam64_id: str, remote_dir: str) -> Dict[str, str]:

        return {
            f"{save_type}Save": os.path.join(
                remote_dir,
                hashlib.md5(f"{steam64_id}{save_type}".encode()).hexdigest() + ".sav"
            )
            for save_type in self.SAVE_TYPES
        }

    def apply_save_modification(self, file_type: str, steam64_id: str,
                               remote_dir: str, duplicate_file: Optional[str] = None,
                               old_key: Optional[bytes] = None, new_key: Optional[bytes] = None):
        script_path = self.script_files_dir / f"{file_type}.sav"

        if not script_path.exists():
            raise FileNotFoundError(f"Script file not found: {script_path}")

        with open(script_path, "rb") as file:
            contents = file.read()

        contents = contents.replace(b"my_stupid_user_id", steam64_id.encode())

        if old_key is not None and new_key is not None:
            contents = contents.replace(old_key, new_key)

        files_to_write = [Path(remote_dir) / f"{steam64_id}{file_type}.sav"]
        if duplicate_file and Path(duplicate_file).parent.exists():
            files_to_write.append(Path(duplicate_file))

        for file_path in files_to_write:
            self._write_save_file(file_path, contents)

    def _write_save_file(self, file_path: Path, contents: bytes):
        try:
            with open(file_path, "wb") as file:
                file.write(contents)
            print(f"Save file written: {file_path}")
        except Exception as e:
            print(f"Failed to write save file {file_path}: {e}")
            raise


class OARTool:

    def __init__(self):
        self.steam_manager = SteamManager()
        self.script_files_dir = Path(__file__).parent / "Script Files"
        self.save_manager = SaveFileManager(self.script_files_dir)

        self.account_data: Dict[str, AccountInfo] = {}
        self.duplicate_files: Dict[str, str] = {}
        self.remote_directory: Optional[str] = None
        self.is_advanced_mode = False
        self.debug_console: Optional[DebugConsole] = None

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self._setup_window()
        self._initialize_app()

    def _setup_window(self):
        self.window = tk.Tk()
        self.window.resizable(False, False)
        self.window.title("OAR Tool v3.1")
        self.window.geometry("300x225")
        self.main_frame = None

        self._setup_icon()
        self._create_menu_bar()

    def _setup_icon(self):
        try:
            icon_path = self.script_files_dir / "custom_icon.ico"
            if icon_path.exists():
                self.window.iconbitmap(str(icon_path))
        except Exception as e:
            logging.warning(f"Failed to load icon: {e}")

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
        menubar = tk.Menu(self.window)
        self.window.config(menu=menubar)

        mode_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Mode", menu=mode_menu)
        mode_menu.add_command(label="Normal Mode", command=lambda: self.set_mode(False))
        mode_menu.add_command(label="Advanced Mode", command=lambda: self.set_mode(True))

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="Debug Console", command=self._show_debug_console)

    def _show_debug_console(self):
        if self.debug_console is None or not self.debug_console.winfo_exists():
            self.debug_console = DebugConsole(self.window)
            self.debug_console.protocol("WM_DELETE_WINDOW", self.debug_console.on_close)
        else:
            self.debug_console.lift()

        print("Debug console opened")
        print(f"Steam path: {self.steam_manager.steam_path}")
        print(f"Advanced mode: {self.is_advanced_mode}")

    def set_mode(self, advanced: bool):
        if self.is_advanced_mode != advanced:
            mode_name = "Advanced" if advanced else "Normal"
            logging.info(f"Application mode changed to {mode_name}")
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
        messagebox.showinfo(
            "About OAR Tool",
            "OAR Tool v3.1\n\nMade By FireNinja\n\nhttps://github.com/FireNinja7365/OAR-Tool",
        )

    def _clear_window(self):
        if self.main_frame:
            self.main_frame.destroy()
        self.main_frame = ttk.Frame(self.window, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def show_selection_screen(self):
        self._clear_window()

        ttk.Label(
            self.main_frame,
            text="Select your Steam account:",
            font=("Arial", 12, "bold"),
        ).pack(pady=(0, 10))

        self._create_scrollable_account_list()

    def _create_scrollable_account_list(self):
        container_frame = ttk.Frame(self.main_frame)
        container_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(container_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        def configure_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas_width = canvas.winfo_width()
            frame_width = scrollable_frame.winfo_reqwidth()

            if frame_width < canvas_width:
                x_offset = (canvas_width - frame_width) // 2
            else:
                x_offset = 0

            canvas.coords(canvas_window, x_offset, 0)

        scrollable_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", configure_scroll_region)

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="n")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            if canvas.canvasy(0) > 0 or canvas.canvasy(canvas.winfo_height()) < scrollable_frame.winfo_reqheight():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        self._load_accounts(scrollable_frame)

        self.window.update_idletasks()
        configure_scroll_region()

    def show_advanced_screen(self):
        self._clear_window()
        self.window.geometry("500x350")

        ttk.Label(
            self.main_frame, text="Advanced Mode", font=("Arial", 14, "bold")
        ).pack(pady=10)

        id_frame = ttk.Frame(self.main_frame)
        id_frame.pack(fill=tk.X, pady=5)
        ttk.Label(id_frame, text="Steam64 ID:").pack(side=tk.LEFT, padx=5)
        self.steam_id_var = tk.StringVar()
        ttk.Entry(id_frame, textvariable=self.steam_id_var, width=30).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )

        dir_frame = ttk.Frame(self.main_frame)
        dir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dir_frame, text="Save Directory:").pack(side=tk.LEFT, padx=5)
        self.save_dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.save_dir_var, width=30).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(
            dir_frame, text="Browse...", command=self._browse_save_directory
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Label(
            self.main_frame,
            text="In advanced mode, you can manually specify your Steam64 ID\nand the location of your save files.",
            justify=tk.CENTER,
        ).pack(pady=10)

        ttk.Label(
            self.main_frame,
            text="Warning: Only use if you know what you're doing!",
            foreground="red",
            font=("Arial", 10, "bold"),
        ).pack(pady=10)

        ttk.Button(
            self.main_frame,
            text="Continue to Edit",
            command=self._process_advanced_selection,
        ).pack(fill=tk.X, expand=True, padx=5, pady=10)

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

        if not steam64_id:
            messagebox.showerror("Error", "Steam64 ID cannot be empty")
            return

        if not save_dir or not Path(save_dir).is_dir():
            messagebox.showerror("Error", "Invalid save directory")
            return

        self.remote_directory = save_dir
        self.duplicate_files = self.save_manager.generate_save_filenames(steam64_id, save_dir)

        self.show_edit_screen(steam64_id)

    def show_edit_screen(self, steam64_id: str):
        self._clear_window()
        self.window.geometry("300x225")

        form_vars = {
            'cash': tk.IntVar(),
            'level': tk.IntVar(),
            'edit_cash': tk.BooleanVar(),
            'edit_level': tk.BooleanVar(),
            'edit_items': tk.BooleanVar(),
            'edit_maps': tk.BooleanVar(),
        }

        ttk.Label(self.main_frame, text="Made By FireNinja").pack()

        ttk.Checkbutton(
            self.main_frame, text="Unlock Items & Cosmetics",
            variable=form_vars['edit_items']
        ).pack(anchor="w")

        ttk.Checkbutton(
            self.main_frame, text="Unlock Maps",
            variable=form_vars['edit_maps']
        ).pack(anchor="w")

        ttk.Checkbutton(
            self.main_frame, text="Edit Cash:",
            variable=form_vars['edit_cash']
        ).pack(anchor="w")
        ttk.Entry(self.main_frame, textvariable=form_vars['cash']).pack(fill="x")

        ttk.Checkbutton(
            self.main_frame, text="Edit Level:",
            variable=form_vars['edit_level']
        ).pack(anchor="w")
        ttk.Entry(self.main_frame, textvariable=form_vars['level']).pack(fill="x")

        ttk.Label(self.main_frame, text="").pack()

        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(fill="x", expand=True)

        ttk.Button(buttons_frame, text="Back", command=self._go_back).pack(
            side="left", fill="x", expand=True, padx=2
        )

        ttk.Button(
            buttons_frame,
            text="Apply",
            command=lambda: self._apply_changes(form_vars, steam64_id),
        ).pack(side="left", fill="x", expand=True, padx=2)

    def _go_back(self):
        if self.is_advanced_mode:
            self.show_advanced_screen()
        else:
            self.show_selection_screen()

    def _load_accounts(self, parent_frame):
        if not self.steam_manager.steam_path:
            ttk.Label(
                parent_frame, text="Steam installation not found!", foreground="red"
            ).pack()
            return

        try:
            self.account_data = self.steam_manager.load_accounts()

            for account_name in self.account_data:
                ttk.Button(
                    parent_frame,
                    text=account_name,
                    command=lambda name=account_name: self._select_account(name),
                    width=25
                ).pack(pady=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Steam accounts: {e}")
            print(f"Failed to load accounts: {e}")

    def _select_account(self, account_name: str):
        account_info = self.account_data.get(account_name)
        if not account_info:
            messagebox.showerror("Error", "Could not find account data")
            return

        try:
            self.remote_directory = self.steam_manager.ensure_game_directories(account_info.steam3_id)

            print(f"Account selected: {account_name}")
            print(f"Account folder: {account_info.steam3_id}")
            print(f"Account ID: {account_info.steam64_id}")

            backup_root = Path(__file__).parent / "OAR backup"
            backup_root.mkdir(exist_ok=True)
            self.steam_manager.create_backup(account_info.steam3_id, backup_root)

            self.duplicate_files = self.save_manager.generate_save_filenames(
                account_info.steam64_id, self.remote_directory
            )

            self.show_edit_screen(account_info.steam64_id)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to select account: {e}")
            print(f"Account selection failed: {e}")

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

        print(f"Applying changes for Steam64 ID: {steam64_id}")
        changes_made = False

        try:
            modifications = [
                ('edit_cash', 'cash', 'Cash', b"my_stupid_cash_id"),
                ('edit_level', 'level', 'Level', b"my_stupid_level_id"),
                ('edit_items', None, 'InventoryItems', None),
                ('edit_maps', None, 'Maps', None),
            ]

            for edit_var, value_var, file_type, old_key in modifications:
                if form_vars[edit_var].get():
                    new_key = None

                    if value_var:
                        value = form_vars[value_var].get()
                        if not self._validate_number_input(value):
                            return
                        new_key = value.to_bytes(4, byteorder="little", signed=True)
                        print(f"Editing {file_type.lower()} to: {value}")
                    else:
                        print(f"Unlocking {file_type.lower()}")

                    self.save_manager.apply_save_modification(
                        file_type, steam64_id, self.remote_directory,
                        self.duplicate_files.get(f"{file_type}Save"),
                        old_key, new_key
                    )
                    changes_made = True

            if changes_made:
                print("Changes applied successfully!")
                messagebox.showinfo("Success", "Changes applied successfully!")
            else:
                print("No changes were made")
                messagebox.showinfo(
                    "Nothing Changed",
                    "No changes were made!\nMaybe try selecting something?",
                )

        except Exception as e:
            error_msg = f"Failed to apply changes: {e}"
            print(error_msg)
            messagebox.showerror("Error", error_msg)

    def run(self):
        self.window.mainloop()


def main():
    try:
        app = OARTool()
        app.run()
    except Exception as e:
        print(f"Application failed to start: {e}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {e}")


if __name__ == "__main__":
    main()
