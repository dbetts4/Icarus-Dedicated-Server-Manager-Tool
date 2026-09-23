import customtkinter as ctk
import platform
import signal
from manager_engine import ServerManager
from tkinter import messagebox
import os, time, threading, sys, queue

IS_WINDOWS = platform.system() == "Windows"

class ConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent, host_name, current_settings, save_callback):
        super().__init__(parent); self.title(f"Config: {host_name}"); self.geometry("650x850")
        self.transient(parent)
        self.save_callback, self.host_name = save_callback, host_name
        self.after(10, self.lift); self.after(10, self.focus_force)
        self.tabview = ctk.CTkTabview(self); self.tabview.pack(padx=10, pady=10, fill="both", expand=True)
        self.tabview.add("Network"); self.tabview.add("Gameplay"); self.tabview.add("Advanced"); self.tabview.add("Discord")
        tn, tg, ta, td = self.tabview.tab("Network"), self.tabview.tab("Gameplay"), self.tabview.tab("Advanced"), self.tabview.tab("Discord")
        self.e_sn = self.create_input(tn, "Session Name:", current_settings.get('session_name'))
        self.e_jp = self.create_input(tn, "Join Password:", current_settings.get('join_password'))
        self.e_ap = self.create_input(tn, "Admin Password:", current_settings.get('admin_password'))
        self.e_po = self.create_input(tn, "Game Port (UDP):", current_settings.get('port', 17778))
        self.e_upo = self.create_input(tn, "Query Port (UDP):", current_settings.get('query_port', 27016))
        self.sw_pub = self.create_switch(tn, "Public Server", current_settings.get('is_public', True), "Show in browser.")
        self.sw_fo = self.create_switch(tg, "Foliage Respawn", current_settings.get('respawn_foliage'), "Plants and bushes regrow.")
        self.sw_ro = self.create_switch(tg, "Stone Respawn", current_settings.get('respawn_rocks'), "Rocks and ores regrow.")
        self.s_rf = self.create_slider_with_input(tg, "Respawn Multiplier", 0.1, 5.0, current_settings.get('respawn_freq', 1.0), "x", 1.0, "Regrowth speed multiplier.")
        self.s_sf = self.create_slider_with_input(ta, "Save Frequency", 1, 300, current_settings.get('save_freq', 60), "min", 60, "Minutes between world auto-saves.")
        self.s_tk = self.create_slider_with_input(ta, "Server Tick Rate", 30, 120, current_settings.get('tick_rate', 60), "hz", 60, "Logic cycles per second.")
        self.s_gc = self.create_slider_with_input(ta, "Garbage Collection", 30, 600, current_settings.get('gc_interval', 60), "sec", 60, "Cleanup frequency for unused RAM.")
        self.s_id = self.create_slider_with_input(ta, "Idle Shutdown", 0, 36000, current_settings.get('shutdown_timer', 300), "sec", 300, "Time before shutdown. 0 = disabled.")
        perf_frame = ctk.CTkFrame(ta, fg_color="gray20"); perf_frame.pack(fill="x", padx=10, pady=20)
        ctk.CTkLabel(perf_frame, text="💻 Performance Standard Guide", font=("Arial", 12, "bold")).pack(pady=5)
        ctk.CTkLabel(perf_frame, text="Standard: 60hz Tick / 60s GC (Balanced)\nHigh: 120hz Tick / 30s GC (Precision)\nLow: 30hz Tick / 300s GC (Old PCs)", font=("Arial", 10)).pack(pady=5)
        self.e_disc = self.create_input(td, "Webhook URL:", current_settings.get('discord_webhook', ""))
        ctk.CTkButton(self, text="Save Config", command=self.apply).pack(pady=15)
    def create_input(self, p, l, d):
        f = ctk.CTkFrame(p, fg_color="transparent"); f.pack(fill="x", pady=2)
        ctk.CTkLabel(f, text=l, width=150, anchor="w").pack(side="left"); e = ctk.CTkEntry(f); e.insert(0, str(d)); e.pack(side="right", fill="x", expand=True); return e
    def create_switch(self, p, t, d, desc):
        f = ctk.CTkFrame(p, fg_color="transparent"); f.pack(fill="x", pady=5, padx=10)
        sw = ctk.CTkSwitch(f, text=t); sw.pack(anchor="w"); (sw.select() if d else None)
        ctk.CTkLabel(f, text=desc, font=("Arial", 10), text_color="gray").pack(anchor="w", padx=35); return sw
    def create_slider_with_input(self, p, title, mi, ma, current, unit, default, desc):
        f = ctk.CTkFrame(p, fg_color="transparent"); f.pack(fill="x", pady=10, padx=10)
        h = ctk.CTkFrame(f, fg_color="transparent"); h.pack(fill="x")
        ctk.CTkLabel(h, text=f"{title} ({mi}-{ma} {unit})", font=("Arial", 12, "bold")).pack(side="left")
        ent = ctk.CTkEntry(h, width=70); ent.insert(0, str(current)); ent.pack(side="right")
        sld = ctk.CTkSlider(f, from_=mi, to=ma, number_of_steps=100); sld.set(float(current)); sld.pack(fill="x", pady=5)
        def validate(e=None):
            try:
                v = float(ent.get())
                if v < mi or v > ma:
                    messagebox.showwarning("Out of Range", f"{title} must be between {mi} and {ma}.\n\nResetting to default: {default}"); ent.delete(0,'end'); ent.insert(0,str(default)); sld.set(default)
                else: sld.set(v)
            except: pass
        sld.configure(command=lambda v: [ent.delete(0,'end'), ent.insert(0,str(round(float(v),2)))])
        ent.bind("<Return>", validate); ent.bind("<FocusOut>", validate)
        ctk.CTkLabel(f, text=desc, font=("Arial", 10), text_color="gray").pack(anchor="w", padx=10); return ent
    def apply(self):
        try:
            d = {"session_name": self.e_sn.get(), "join_password": self.e_jp.get(), "admin_password": self.e_ap.get(), "port": int(self.e_po.get()), "query_port": int(self.e_upo.get()), "is_public": bool(self.sw_pub.get()), "save_freq": float(self.s_sf.get()), "tick_rate": int(float(self.s_tk.get())), "gc_interval": int(float(self.s_gc.get())), "shutdown_timer": int(float(self.s_id.get())), "respawn_foliage": bool(self.sw_fo.get()), "respawn_rocks": bool(self.sw_ro.get()), "respawn_freq": float(self.s_rf.get()), "discord_webhook": self.e_disc.get()}
            self.save_callback(self.host_name, d); self.destroy()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please ensure Game Port, Query Port, and numeric fields contain valid numbers.")

class IcarusApp(ctk.CTk):
    def __init__(self):
        if not IS_WINDOWS and not os.environ.get('DISPLAY'):
            # Headless GUI prep for Docker/Linux NoVNC environments
            os.environ['DISPLAY'] = ':0'
            
        super().__init__(); self.title("IDSM"); self.geometry("1700x650")
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, self.handle_sigterm)
            
        self.manager = ServerManager()
        ctk.set_appearance_mode(self.manager.app_settings.get("appearance_mode", "Dark"))

        self.build_ui()
        self.tick_stats()
        self.run_master_update(initial=True)

    def run_master_update(self, initial=False):
        if getattr(self, '_is_updating', False):
            return
        self._is_updating = True

        self.overlay = ctk.CTkFrame(self, fg_color=("white", "gray10")); self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.over_textbox = ctk.CTkTextbox(self.overlay, font=("Courier New", 12))
        self.over_textbox.pack(pady=(20, 10), padx=20, fill="both", expand=True)
        self.over_textbox.configure(state="disabled")

        self.progress_bar = ctk.CTkProgressBar(self.overlay, mode="indeterminate")
        self.progress_bar.pack(pady=(0, 20), padx=20, fill="x")
        self.progress_bar.start()

        self.startup_first_line_processed = False

        self.progress_queue = queue.Queue()

        def process_queue():
            if not hasattr(self, 'overlay') or not self.overlay.winfo_exists(): return
            lines = []
            while True:
                try: lines.append(self.progress_queue.get_nowait())
                except queue.Empty: break
            if lines:
                self.over_textbox.configure(state="normal")
                for text in lines:
                    if not text or "-- type 'quit' to exit --" in text: continue
                    is_progress = "progress:" in text.lower()
                    if getattr(self, '_last_was_progress', False) and is_progress:
                        self.over_textbox.delete("end-2l linestart", "end-1c")
                        
                    if is_progress:
                        try:
                            pct_str = text.split("progress:")[1].split("(")[0].strip()
                            self.progress_bar.stop()
                            self.progress_bar.configure(mode="determinate")
                            self.progress_bar.set(float(pct_str) / 100.0)
                        except Exception: pass

                    if initial:
                        if not self.startup_first_line_processed and "Steam Console Client" in text:
                            self.over_textbox.insert("end", f"Watchdog: {text}\n")
                            self.over_textbox.insert("end", "DS Watchdog: Checking for updates...\n\n")
                            self.startup_first_line_processed = True
                        else:
                            self.over_textbox.insert("end", f"Watchdog: {text}\n")
                    else:
                        self.over_textbox.insert("end", f"{text}\n")
                    self._last_was_progress = is_progress
                self.over_textbox.see("end")
                self.over_textbox.configure(state="disabled")
            self.after(50, process_queue)

        self.after(50, process_queue)

        def on_complete(success, msg):
            self._is_updating = False
            if hasattr(self, 'overlay') and self.overlay: self.overlay.destroy()
            if not success:
                messagebox.showerror("Update Error", f"Master Update Failed:\n{msg}\n\nPlease ensure SteamCMD is installed correctly.")
            elif initial:
                delay = 0
                for n, d in self.manager.hosts.items():
                    if d.get('start_on_app_load', False):
                        self.after(delay, lambda name=n: self.launch_server_flow(name))
                        delay += 5000

        def _update_thread():
            success, msg = self.manager.update_master_files(self.progress_queue.put)
            self.after(0, lambda: on_complete(success, msg))

        threading.Thread(target=_update_thread, daemon=True).start()

    def on_closing(self):
        busy_statuses = ["Running", "Stopping...", "Saving..."]
        if any(h['status'] in busy_statuses for h in self.manager.hosts.values()): messagebox.showwarning("Servers Active", "Please wait for all servers to finish stopping before closing the tool.")
        else: self.destroy()

    def handle_sigterm(self, signum, frame):
        for name, h in self.manager.hosts.items():
            if h['status'] in ["Running", "Saving..."]:
                self.manager.stop_server(name, create_backup_on_stop=True)
        # Wait up to 30 seconds for all to stop
        for _ in range(30):
            if not any(h['status'] in ["Running", "Stopping...", "Saving..."] for h in self.manager.hosts.values()):
                break
            time.sleep(1)
        self.destroy()
    def build_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=160); self.sidebar.pack(side="left", fill="y")
        ctk.CTkLabel(self.sidebar, text="IDSM", font=("Arial", 18, "bold")).pack(pady=15)
        
        ctk.CTkLabel(self.sidebar, text="Steam User:", font=("Arial", 12)).pack(pady=(10, 0))
        users = self.manager.get_steam_users()
        display_users = users if users else ["No Users Found"]
        self.steam_user_cb = ctk.CTkOptionMenu(self.sidebar, values=display_users)
        self.steam_user_cb.pack(pady=5, padx=10)
        if users:
            self.steam_user_cb.set(users[0])
        else:
            self.steam_user_cb.set("No Users Found")
            self.steam_user_cb.configure(state="disabled")

        ctk.CTkButton(self.sidebar, text="+ New Host", command=self.add_host_1).pack(pady=10, padx=10)
        ctk.CTkButton(self.sidebar, text="⚙ App Settings", command=lambda: AppSettingsWindow(self)).pack(pady=10, padx=10)
        ctk.CTkButton(self.sidebar, text="📂 Open Saves", command=self.open_saves_dir).pack(pady=10, padx=10)
        self.footer = ctk.CTkFrame(self, height=40, fg_color="gray15"); self.footer.pack(side="bottom", fill="x")
        self.sys_lbl = ctk.CTkLabel(self.footer, text="System: CPU 0% | RAM 0%", font=("Arial", 12)); self.sys_lbl.pack(pady=5)
        self.scroll = ctk.CTkScrollableFrame(self, label_text="Instances"); self.scroll.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        self.refresh_hosts()
    def tick_stats(self):
        self.manager.update_stats(); c_p, r_p = self.manager.get_system_stats()
        self.sys_lbl.configure(text=f"Global System Usage -> CPU: {c_p} | RAM: {r_p}")
        if hasattr(self, 'scroll'):
            for card in self.scroll.winfo_children():
                name = card.host_name; d = self.manager.hosts[name]
                status = d.get('status')
                st_color = {"Running": "#2ecc71", "Stopping...": "#f39c12", "Crashed": "#e74c3c", "Saving...": "#3498db"}.get(status, "gray")
                card.stat_lbl.configure(text=f"Status: {d.get('status')} ({d.get('uptime')})", text_color=st_color)
                card.res_lbl.configure(text=f"CPU: {d.get('cpu')} | RAM: {d.get('ram')}")
                card.save_lbl.configure(text=f"Saved: {d.get('last_saved')}")
                is_restore = d.get('restore_info', {}).get('is_restore', False)
                if is_restore:
                    world_text = f"World: {d['save_file']} (Restored)"
                    card.world_lbl.configure(text=world_text, text_color="#e74c3c")
                else:
                    card.world_lbl.configure(text=f"World: {d['save_file']}", text_color="#e67e22")
                is_busy = status in ["Running", "Stopping...", "Saving..."]
                card.start_btn.configure(state="disabled" if is_busy else "normal")
                card.del_btn.configure(state="disabled" if is_busy else "normal")
                card.restore_btn.configure(state="disabled" if is_busy else "normal")
                card.config_btn.configure(state="disabled" if is_busy else "normal")
                card.stop_btn.configure(state="normal" if status == "Running" else "disabled")
                card.autostart_sw.configure(state="disabled" if status == "Running" else "normal")
        self.after(1000, self.tick_stats)
    def open_saves_dir(self):
        sid = self.steam_user_cb.get()
        if not IS_WINDOWS:
            messagebox.showinfo("Linux/Docker", "Save directory is mapped via Docker volume (e.g. /serverdata/saves)")
            return
        if not sid: return
        path = self.manager.get_local_prospect_dir(sid)
        if os.path.exists(path): os.startfile(path)
        else: messagebox.showinfo("Not Found", "Saves directory does not exist.")
    def refresh_hosts(self):
        for w in self.scroll.winfo_children(): w.destroy()
        for n, d in self.manager.hosts.items(): self.create_card(n, d)
    def create_card(self, n, d):
        c = ctk.CTkFrame(self.scroll); c.pack(fill="x", pady=2, padx=2); c.host_name = n
        ctk.CTkLabel(c, text=n, font=("Arial", 12, "bold"), width=120, anchor="w").pack(side="left", padx=10)
        c.stat_lbl = ctk.CTkLabel(c, text="Status: Offline", width=180, anchor="w"); c.stat_lbl.pack(side="left")
        c.res_lbl = ctk.CTkLabel(c, text="CPU: 0% | RAM: 0MB", width=140, text_color="#3498db", anchor="w"); c.res_lbl.pack(side="left")
        c.save_lbl = ctk.CTkLabel(c, text="Saved: Never", width=160, text_color="gray", anchor="w"); c.save_lbl.pack(side="left")
        c.world_lbl = ctk.CTkLabel(c, text=f"World: {d['save_file']}", text_color="#e67e22", width=200, anchor="w")
        c.world_lbl.pack(side="left", padx=5)
        s = d.get('settings', {})
        c.port_lbl = ctk.CTkLabel(c, text=f"Ports (UDP): {s.get('port', 17778)}/{s.get('query_port', 27016)}", width=160, anchor="w", text_color="gray"); c.port_lbl.pack(side="left")
        c.copy_ip_btn = ctk.CTkButton(c, text="📋 Copy IP", width=60, fg_color="gray30", command=lambda host=n: self.copy_ip(host)); c.copy_ip_btn.pack(side="left", padx=5)
        c.autostart_var = ctk.BooleanVar(value=d.get('start_on_app_load', False))
        c.autostart_sw = ctk.CTkSwitch(c, text="Auto-Start", variable=c.autostart_var, width=100, command=lambda host=n, var=c.autostart_var: self.toggle_autostart(host, var))
        c.autostart_sw.pack(side="left", padx=5)
        c.del_btn = ctk.CTkButton(c, text="🗑", width=30, fg_color="#e74c3c", command=lambda: self.confirm_del(n)); c.del_btn.pack(side="right", padx=2)
        c.restore_btn = ctk.CTkButton(c, text="Restore", width=75, fg_color="#9b59b6", command=lambda: self.restore_flow(n)); c.restore_btn.pack(side="right", padx=2)
        c.stop_btn = ctk.CTkButton(c, text="🛑 Stop", width=60, fg_color="#e67e22", command=lambda: self.stop_flow(n)); c.stop_btn.pack(side="right", padx=2)
        c.start_btn = ctk.CTkButton(c, text="▶ Start", width=60, fg_color="#2ecc71", command=lambda: self.launch_server_flow(n)); c.start_btn.pack(side="right", padx=2)
        c.config_btn = ctk.CTkButton(c, text="⚙ Config", width=75, command=lambda: ConfigWindow(self, n, s, self.update_cfg)); c.config_btn.pack(side="right", padx=2)
    def stop_flow(self, n):
        for card in self.scroll.winfo_children():
            if card.host_name == n:
                card.stop_btn.configure(state="disabled")
                break
        threading.Thread(target=self._delayed_stop, args=(n,), daemon=True).start()

    def _delayed_stop(self, n):
        if not self.manager.save_server(n): return
        
        is_restore = self.manager.hosts[n].get('restore_info', {}).get('is_restore', False)
        # Wait in the background for the 20s graceful exit / save event
        stop_success, stop_msg = self.manager.stop_server(n, create_backup_on_stop=not is_restore)
        
        def final_stop():
            if stop_success:
                if stop_msg:
                    if "failed" in stop_msg.lower() or "warning" in stop_msg.lower():
                        messagebox.showwarning("Stop Complete", stop_msg)
                    else:
                        messagebox.showinfo("Stop Complete", stop_msg)
                
                if is_restore:
                    RestoreOptionsWindow(self, n)
            elif self.manager.hosts[n]['status'] != "Offline":
                messagebox.showerror("Error", f"Could not stop server {n}. {stop_msg}")
        self.after(0, final_stop)

    def copy_ip(self, host_name):
        try:
            port = self.manager.hosts[host_name].get('settings', {}).get('port', 17778)
            ip_str = f"{self.manager.public_ip}:{port}"
            self.clipboard_clear()
            self.clipboard_append(ip_str)
            messagebox.showinfo("Copied", f"Copied to clipboard:\n{ip_str}")
        except Exception: pass

    def toggle_autostart(self, host, var):
        self.manager.hosts[host]['start_on_app_load'] = var.get()
        self.manager.save_configs()
    def update_cfg(self, n, d): self.manager.update_host_name(n, d); self.refresh_hosts()
    def add_host_1(self):
        sid = self.steam_user_cb.get()
        if not sid or sid == "No Users Found":
            messagebox.showerror("No Steam Data", "No local Icarus save data found.\n\nPlease run the game normally at least once on this PC to generate save data.")
            return
        saves = self.manager.get_available_saves(sid)
        if not saves or saves == ["No Saves Found"]:
            if sid == "Dedicated Server Saves":
                messagebox.showerror("No Saves Found", f"No prospects found in the central directory.\n\nPlease place your .json save files in:\n{self.manager.dedicated_saves_dir}")
            else:
                messagebox.showerror("No Saves Found", "No local prospects found for this user.\n\nPlease create a prospect in-game first.")
            return
        name = ctk.CTkInputDialog(text="Name:", title="New Host").get_input()
        if name: SaveSelectorWindow(self, name, saves, lambda n, s: self.add_host_2(n, s, sid))
    def add_host_2(self, n, s, sid):
        success, msg = self.manager.create_host_slot(n, s, sid)
        if success:
            self.refresh_hosts()
            if msg != "Success":
                messagebox.showwarning("Host Creation Warning", msg)
            # Trigger the update routine to clone and push updates to the new host
            self.run_master_update(initial=False)
        else:
            messagebox.showerror("Error", f"Failed to create host: {msg}")
    def confirm_del(self, n):
        if messagebox.askyesno("Delete Host", f"Are you sure you want to delete host '{n}'?\nThis will delete the server's directory and cannot be undone.", icon='warning'):
            if self.manager.delete_host(n):
                self.refresh_hosts()
            else:
                messagebox.showerror("Error", f"Failed to delete host '{n}'.\nThe server might be running or its files could be in use.")

    def launch_server_flow(self, name):
        success, msg = self.manager.launch_server(name)
        if not success:
            messagebox.showerror("Launch Error", msg)
        self.refresh_hosts()

    def restore_flow(self, name):
        backups = self.manager.get_backed_up_saves()
        if not backups:
            messagebox.showinfo("No Backups", f"No backups found.\n\nBackups are created automatically when the server stops, or manually inside:\n{self.manager.backup_dir}")
            return
        BackupRestoreWindow(self, name)

class BackupRestoreWindow(ctk.CTkToplevel):
    def __init__(self, parent, host_name):
        super().__init__(parent); self.title(f"Restore Backup for {host_name}"); self.geometry("400x400")
        self.transient(parent)
        self.manager, self.parent_app, self.host_name = parent.manager, parent, host_name
        self.after(10, self.lift); self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.save_file = self.manager.hosts[host_name]['save_file']
        ctk.CTkLabel(self, text=f"Select Restore Point for '{self.save_file}'", font=("Arial", 14, "bold")).pack(pady=10)
        ctk.CTkButton(self, text="📂 Open Backups Folder", command=self.open_backups_dir).pack(pady=(0, 5))
        self.backup_list = ctk.CTkScrollableFrame(self); self.backup_list.pack(fill="both", expand=True, padx=10, pady=5)
        self.timestamp_var = ctk.StringVar()
        self.populate_timestamps()
        ctk.CTkButton(self, text="Restore", command=self.confirm).pack(pady=10)
    def populate_timestamps(self):
        for widget in self.backup_list.winfo_children(): widget.destroy()
        timestamps = self.manager.get_backup_timestamps(self.save_file)
        if not timestamps: ctk.CTkLabel(self.backup_list, text="No restore points found.").pack()
        else:
            for ts in timestamps:
                row_frame = ctk.CTkFrame(self.backup_list, fg_color="transparent")
                row_frame.pack(fill="x", pady=2)
                ctk.CTkRadioButton(row_frame, text=ts, variable=self.timestamp_var, value=ts).pack(side="left", padx=5)
                ctk.CTkButton(row_frame, text="🗑", width=30, fg_color="#e74c3c", command=lambda t=ts: self.delete_backup(t)).pack(side="right", padx=5)
            if self.timestamp_var.get() not in timestamps:
                self.timestamp_var.set(timestamps[0])
    def delete_backup(self, timestamp):
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the restore point:\n{timestamp}?"):
            import shutil
            backup_path = os.path.join(self.manager.backup_dir, self.save_file, timestamp)
            try:
                shutil.rmtree(backup_path)
                self.populate_timestamps()
            except Exception as e: messagebox.showerror("Error", f"Could not delete backup:\n{e}")
    def open_backups_dir(self):
        if not IS_WINDOWS:
            messagebox.showinfo("Linux/Docker", "Backups directory is mapped via Docker volume.")
            return
        path = os.path.join(self.manager.backup_dir, self.save_file)
        if os.path.exists(path): os.startfile(path)
        else: messagebox.showinfo("Not Found", "Backups directory does not exist yet.")
    def confirm(self):
        timestamp = self.timestamp_var.get()
        if not timestamp: messagebox.showwarning("Incomplete Selection", "Please select a restore point."); return
        save_file = self.save_file

        if messagebox.askyesno("Confirm Restore", f"Are you sure you want to load restore point '{timestamp}' for '{save_file}'?\n\nYour current local save will be temporarily overwritten, and you can confirm changes after the next session stops."):
            backup_path = os.path.join(self.manager.backup_dir, save_file, timestamp)
            success, msg = self.manager.setup_restore(self.host_name, backup_path, save_file)
            if success: messagebox.showinfo("Restore Staged", msg)
            else: messagebox.showerror("Restore Error", msg)
            self.parent_app.refresh_hosts(); self.destroy()

class SaveSelectorWindow(ctk.CTkToplevel):
    def __init__(self, parent, host_name, saves, callback):
        super().__init__(parent); self.title("Select World"); self.geometry("350x200")
        self.transient(parent)
        self.callback, self.host_name = callback, host_name; self.after(10, self.lift)
        ctk.CTkLabel(self, text=f"World for '{host_name}':").pack(pady=10)
        self.combo = ctk.CTkComboBox(self, values=saves, width=200); self.combo.pack(pady=10); self.combo.set(saves[0] if saves else ""); ctk.CTkButton(self, text="Finish Setup", command=self.confirm).pack(pady=15)
    def confirm(self): self.callback(self.host_name, self.combo.get()); self.destroy()

class RestoreOptionsWindow(ctk.CTkToplevel):
    def __init__(self, parent, host_name):
        super().__init__(parent); self.title("Restore Session Finished"); self.geometry("450x180")
        self.transient(parent)
        self.manager, self.host_name, self.parent_app = parent.manager, host_name, parent
        self.after(10, self.lift); self.protocol("WM_DELETE_WINDOW", self.discard)
        ctk.CTkLabel(self, text=f"Session for '{host_name}' has ended.", font=("Arial", 14, "bold")).pack(pady=10)
        ctk.CTkLabel(self, text="What would you like to do with the progress from this session?").pack()
        btn_frame = ctk.CTkFrame(self, fg_color="transparent"); btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Overwrite Original", command=self.overwrite).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Save as New...", command=self.save_as).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Discard Changes", fg_color="gray30", command=self.discard).pack(side="left", padx=5)
    def handle_result(self, success, msg):
        if success: messagebox.showinfo("Success", msg)
        else: messagebox.showerror("Error", msg)
        self.parent_app.refresh_hosts(); self.destroy()
    def overwrite(self):
        if messagebox.askyesno("Confirm Overwrite", "This will permanently keep the progress from this session, overwriting your original save state.\n\nA backup of the original state has been saved.\n\nContinue?", icon='warning'):
            overwrite_success, overwrite_msg = self.manager.handle_restore_shutdown(self.host_name, 'overwrite')
            self.handle_result(overwrite_success, overwrite_msg)
    def save_as(self):
        new_name = ctk.CTkInputDialog(text="Enter new save name:", title="Save As").get_input()
        if new_name: self.handle_result(*self.manager.handle_restore_shutdown(self.host_name, 'save_as', new_name)) # No backup is created for "save as"
    def discard(self): self.handle_result(*self.manager.handle_restore_shutdown(self.host_name, 'discard'))

class AppSettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent); self.title("App Settings"); self.geometry("300x160")
        self.transient(parent)
        self.manager = parent.manager
        self.after(10, self.lift); self.after(10, self.focus_force)
        self.startup_btn = ctk.CTkButton(self, text="", command=self.toggle_startup)
        self.startup_btn.pack(pady=(30, 10), padx=30)
        self.update_startup_button()
        
        self.theme_var = ctk.StringVar(value=self.manager.app_settings.get("appearance_mode", "Dark"))
        theme_sw = ctk.CTkSwitch(self, text="Light Mode", variable=self.theme_var, onvalue="Light", offvalue="Dark", command=self.toggle_theme)
        theme_sw.pack(pady=10, padx=30, anchor="w")

    def update_startup_button(self):
        if self.manager.is_windows_startup_enabled():
            self.startup_btn.configure(text="Disable Startup on Boot")
        else:
            self.startup_btn.configure(text="Enable Startup on Boot")

    def toggle_startup(self):
        is_enabled = self.manager.is_windows_startup_enabled()
        success, msg = self.manager.toggle_windows_startup(not is_enabled)
        if success: messagebox.showinfo("Success", msg)
        else: messagebox.showerror("Error", msg)
        self.update_startup_button()

    def toggle_theme(self):
        theme = self.theme_var.get()
        ctk.set_appearance_mode(theme)
        self.manager.app_settings["appearance_mode"] = theme
        self.manager.save_app_settings()

if __name__ == "__main__": IcarusApp().mainloop()