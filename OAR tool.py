import hashlib
import tkinter as tk
from tkinter import ttk, messagebox
import os
import shutil
import vdf
import winreg

class OARTool:
    def __init__(self):
        self.steam_path = self.get_steam_path()
        if not self.steam_path:
            messagebox.showerror("Error", "Steam installation not found!")
            return
            
        self.account_data = {}
        self.GAME_ID = "2551020"
        self.duplicate_files = {}
        self.window = None
        self.main_frame = None

    def setup_window(self):
        self.window = tk.Tk()
        self.window.resizable(False, False)
        
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Script Files", "custom_icon.ico")
            if os.path.exists(icon_path):
                self.window.iconbitmap(icon_path)
        except Exception as e:
            print(f"Failed to load icon: {str(e)}")

        self.window.title("OAR Tool v2.7")
        self.show_selection_screen()

    def clear_window(self):
        if self.main_frame:
            self.main_frame.destroy()
        self.main_frame = ttk.Frame(self.window, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def show_selection_screen(self):
        self.clear_window()
        self.window.geometry("300x200")
        
        ttk.Label(self.main_frame, text="Select your Steam account:", font=('Arial', 12, 'bold')).pack()
        
        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(fill=tk.BOTH, expand=True)
        
        self.load_accounts(buttons_frame)
        
        base_height = 80
        per_button_height = 35
        num_accounts = len(self.account_data)
        total_height = base_height + (per_button_height * num_accounts)
        window_height = max(200, min(total_height, 800))
        self.window.geometry(f"300x{window_height}")

    def show_edit_screen(self, steam64_id, script_files_directory):
        self.clear_window()
        self.window.geometry("300x225")
        
        cash = tk.IntVar()
        level = tk.IntVar()
        edit_cash = tk.BooleanVar()
        edit_level = tk.BooleanVar()
        edit_items = tk.BooleanVar()
        edit_maps = tk.BooleanVar()
        
        ttk.Label(self.main_frame, text="Made By FireNinja").pack()
        
        ttk.Checkbutton(self.main_frame, text="Unlock Items & Cosmetics", variable=edit_items).pack(anchor="w")
        ttk.Checkbutton(self.main_frame, text="Unlock Maps", variable=edit_maps).pack(anchor="w")
        
        ttk.Checkbutton(self.main_frame, text="Edit Cash:", variable=edit_cash).pack(anchor="w")
        ttk.Entry(self.main_frame, textvariable=cash).pack(fill="x")
        
        ttk.Checkbutton(self.main_frame, text="Edit Level:", variable=edit_level).pack(anchor="w")
        ttk.Entry(self.main_frame, textvariable=level).pack(fill="x")
        
        ttk.Label(self.main_frame, text="").pack()
        
        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(fill="x", expand=True)
        
        back_button = ttk.Button(
            buttons_frame,
            text="Back",
            command=self.show_selection_screen
        )
        back_button.pack(side="left", fill="x", expand=True, padx=2)
        
        apply_button = ttk.Button(
            buttons_frame,
            text="Apply",
            command=lambda: self.apply_changes(
                edit_cash, edit_level, edit_items, edit_maps,
                cash, level, steam64_id, script_files_directory
            )
        )
        apply_button.pack(side="left", fill="x", expand=True, padx=2)

    def get_steam_path(self):
        try:
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\Valve\\Steam")
            steam_path = winreg.QueryValueEx(hkey, "InstallPath")[0]
            winreg.CloseKey(hkey)
            return steam_path
        except WindowsError:
            try:
                hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Valve\\Steam")
                steam_path = winreg.QueryValueEx(hkey, "InstallPath")[0]
                winreg.CloseKey(hkey)
                return steam_path
            except WindowsError:
                return None

    def load_accounts(self, buttons_frame):
        login_file = os.path.join(self.steam_path, 'config', 'loginusers.vdf')
        
        try:
            with open(login_file, 'r', encoding='utf-8') as f:
                users_data = vdf.load(f)
                
            if 'users' in users_data:
                for steam_id64, user_data in users_data['users'].items():
                    account_name = user_data.get('PersonaName', 'Unknown')
                    steam3_id = str(int(steam_id64) & 0xFFFFFFFF)
                    userdata_path = os.path.join(self.steam_path, 'userdata', str(steam3_id), self.GAME_ID, 'remote')
                    self.account_data[account_name] = {
                        'steam3_id': steam3_id,
                        'steam64_id': steam_id64,
                        'userdata_path': userdata_path
                    }
                    
                    btn = ttk.Button(
                        buttons_frame,
                        text=f"{account_name}",
                        command=lambda name=account_name: self.select_account(name)
                    )
                    btn.pack(fill=tk.X, pady=5)
                        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Steam accounts: {str(e)}")
    
    def select_account(self, account_name):
        account_info = self.account_data.get(account_name)
        if not account_info:
            messagebox.showerror("Error", "Could not find account data")
            return

        steam3_id = account_info['steam3_id']
        self.remote_directory = self.ensure_directories_exist(steam3_id)
        steam64_id = account_info['steam64_id']
        print(f"Account selected: {account_name}")
        print(f"Account folder: {steam3_id}")
        print(f"Account ID: {steam64_id}")

        run_from_directory = os.path.dirname(os.path.abspath(__file__))
        script_files_directory = os.path.join(run_from_directory, "Script Files")
        oar_backup_folder = os.path.join(run_from_directory, "OAR backup")
        user_backup_folder = os.path.join(oar_backup_folder, str(steam3_id))

        if not os.path.exists(oar_backup_folder):
            os.makedirs(oar_backup_folder)

        backup_source = os.path.join(self.steam_path, 'userdata', str(steam3_id), self.GAME_ID)
        if os.path.exists(backup_source) and not os.path.exists(user_backup_folder):
            shutil.copytree(backup_source, user_backup_folder)
        
        self.find_duplicate_names(self.remote_directory, steam64_id)
        self.show_edit_screen(steam64_id, script_files_directory)

    def ensure_directories_exist(self, steam3_id):
        base_path = os.path.join(self.steam_path, 'userdata', str(steam3_id), self.GAME_ID)
        remote_path = os.path.join(base_path, 'remote')
        
        os.makedirs(remote_path, exist_ok=True)
        
        return remote_path

    def adjust_window_size(self):
        base_height = 80
        per_button_height = 35
        num_accounts = len(self.account_data)
        
        total_height = base_height + (per_button_height * num_accounts)
        
        min_height = 200
        max_height = 800
        window_height = max(min_height, min(total_height, max_height))
        
        self.window.geometry(f"400x{window_height}")

    def find_duplicate_names(self, directory, steam64_id):
        self.duplicate_files = {
            "CashSave": os.path.join(directory, hashlib.md5(f"{steam64_id}Cash".encode()).hexdigest() + ".sav"),
            "LevelSave": os.path.join(directory, hashlib.md5(f"{steam64_id}Level".encode()).hexdigest() + ".sav"),
            "InventoryItemsSave": os.path.join(directory, hashlib.md5(f"{steam64_id}InventoryItems".encode()).hexdigest() + ".sav"),
            "MapsSave": os.path.join(directory, hashlib.md5(f"{steam64_id}Maps".encode()).hexdigest() + ".sav")
        }

    def validate_number_input(self, input_str, widget_name):
        input_str = input_str.strip()
        if input_str == "":
            messagebox.showinfo("Information", "Invalid Value! Can Not Be Blank")
            return False

        try:
            entry_int = int(input_str)
            if entry_int < -2147483648 or entry_int > 2147483648:
                messagebox.showinfo("Information", "Invalid Value! Must Be Between -2,147,483,648 and 2,147,483,648")
                return False
            return True
        except ValueError:
            messagebox.showinfo("Information", f"Invalid Value! '{input_str}' Must Be A Number")
            return False

    def advanced_edit(self, script_files_directory, file_ext, steam64_id, old_key_binary, new_key_binary, duplicate_file):
        scr_path = os.path.join(script_files_directory, file_ext)
        dst_path = os.path.join(self.remote_directory, f"{steam64_id}{file_ext}")
        
        with open(scr_path, "rb") as file:
            contents = file.read()

        contents = contents.replace(b"my_stupid_user_id", steam64_id.encode())

        if old_key_binary is not None:
            contents = contents.replace(old_key_binary, new_key_binary)

        with open(dst_path, "wb") as file:
            print(f"Write contents to {dst_path}")
            file.write(contents)

        if duplicate_file is not None:
            with open(duplicate_file, "wb") as file:
                print(f"Write contents to {duplicate_file}")
                file.write(contents)

    def apply_changes(self, edit_cash, edit_level, edit_items, edit_maps, cash, level, steam64_id, script_files_directory):
        if edit_cash.get():
            cash_duplicate = self.duplicate_files.get("CashSave")
            self.advanced_edit(script_files_directory, "Cash.sav", steam64_id, b"my_stupid_cash_id", 
                             cash.get().to_bytes(4, byteorder="little", signed=True), cash_duplicate)

        if edit_level.get():
            level_duplicate = self.duplicate_files.get("LevelSave")
            self.advanced_edit(script_files_directory, "Level.sav", steam64_id, b"my_stupid_level_id",
                             level.get().to_bytes(4, byteorder="little", signed=True), level_duplicate)

        if edit_items.get():
            item_duplicate = self.duplicate_files.get("InventoryItemsSave")
            self.advanced_edit(script_files_directory, "InventoryItems.sav", steam64_id, None, None, item_duplicate)

        if edit_maps.get():
            maps_duplicate = self.duplicate_files.get("MapsSave")
            self.advanced_edit(script_files_directory, "Maps.sav", steam64_id, None, None, maps_duplicate)

        if edit_cash.get() or edit_level.get() or edit_items.get() or edit_maps.get():
            messagebox.showinfo("Success", "Changes applied successfully!")
        else:
            messagebox.showinfo("Nothing Changed", "No changes were made!\nMaybe try selecting something?")

    def run(self):
        self.setup_window()
        self.window.mainloop()

if __name__ == "__main__":
    app = OARTool()
    app.run()