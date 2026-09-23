import os
import sys
import json
import subprocess
import shutil
import signal
from datetime import datetime
import threading
import time
import socket
import base64
import psutil
import urllib.request

IS_WINDOWS = sys.platform == "win32"

class AppConfig:
    if IS_WINDOWS:
        STEAMCMD_PATH = os.path.join("C:\\", "SteamCMD", "steamcmd.exe")
        SAVE_FILE_DIR = os.path.expandvars(r"%LocalAppData%\Icarus\Saved\PlayerData")
        WINE_PREFIX = []
    else:
        STEAMCMD_PATH = os.path.join("/", "config", "steamcmd", "steamcmd.sh")
        SAVE_FILE_DIR = "/saves"
        WINE_PREFIX = ["wine"]

class ServerManager:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))

        self.master_dir = os.path.join(self.app_dir, "Server_Master")
        self.config_file = os.path.join(self.app_dir, "host_configs.json")
        self.app_config_file = os.path.join(self.app_dir, "app_configs.json")
        self.backup_dir = os.path.join(self.app_dir, "Backups")
        self.host_configs_dir = os.path.join(self.app_dir, "Host_Configs")
        self.instances_dir = os.path.join(self.app_dir, "Server_Instances")
        self.dedicated_saves_dir = os.path.join(self.app_dir, "Dedicated_Server_Saves") if IS_WINDOWS else AppConfig.SAVE_FILE_DIR
        
        steamcmd_exe_name = "steamcmd.exe" if IS_WINDOWS else "steamcmd.sh"
        rel_steamcmd = os.path.abspath(os.path.join(self.app_dir, "..", "..", "..", steamcmd_exe_name))
        if os.path.exists(rel_steamcmd):
            self.steamcmd_path = rel_steamcmd
        else:
            self.steamcmd_path = AppConfig.STEAMCMD_PATH
        
        self.hosts = self.load_configs()
        self.app_settings = self.load_app_settings()
        self.active_processes = {}
        
        self.public_ip = "127.0.0.1"
        self.local_ip = self._get_local_ip()
        threading.Thread(target=self._fetch_public_ip, daemon=True).start()
        
        for name in self.hosts:
            # Ensure 'save_file' exists, providing a default if missing from loaded configs
            self.hosts[name].setdefault("save_file", "Unknown Save")
            self.hosts[name].setdefault("start_on_app_load", False)
            self.hosts[name].setdefault("settings", {})
            self.hosts[name].update({"status": "Offline", "uptime": "00:00:00", "last_saved": "Never", "cpu": "0%", "ram": "0MB"})

        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.host_configs_dir, exist_ok=True)
        os.makedirs(self.instances_dir, exist_ok=True)
        os.makedirs(self.dedicated_saves_dir, exist_ok=True)
        os.makedirs(self.master_dir, exist_ok=True)
        self.recover_active_processes()
        
        self.updating_hosts = set()
        self.update_lock = threading.Lock()
        threading.Thread(target=self.auto_update_loop, daemon=True).start()

    def _fetch_public_ip(self):
        try:
            req = urllib.request.Request('https://api.ipify.org', headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                self.public_ip = response.read().decode('utf-8').strip()
        except Exception:
            try: self.public_ip = socket.gethostbyname(socket.gethostname())
            except: pass

    def _get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # This doesn't actually connect, but it finds the primary network adapter
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()
        return local_ip

    def recover_active_processes(self):
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_name = p.info.get('name')
                if proc_name and "IcarusServer" in proc_name:
                    cmdline = p.info.get('cmdline') or []
                    for host_name, h in self.hosts.items():
                        port = str(h.get('settings', {}).get('port', 17778))
                        if any(f"-Port={port}" in arg for arg in cmdline):
                            self.active_processes[host_name] = p
                            h["status"] = "Running"
                            h["start_time"] = p.create_time()
                            threading.Thread(target=self.watchdog_loop, args=(host_name,), daemon=True).start()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

    def load_app_settings(self):
        if os.path.exists(self.app_config_file):
            with open(self.app_config_file, 'r') as f:
                try: return json.load(f)
                except: pass
        return {"appearance_mode": "Dark"}

    def save_app_settings(self):
        with open(self.app_config_file, 'w') as f:
            json.dump(self.app_settings, f, indent=4)

    def get_local_prospect_dir(self, steam_id):
        if steam_id == "Dedicated Server Saves":
            return self.dedicated_saves_dir
        return os.path.join(AppConfig.SAVE_FILE_DIR, steam_id, "Prospects")

    def get_system_stats(self):
        return f"{psutil.cpu_percent()}%", f"{psutil.virtual_memory().percent}%"

    def get_steam_users(self):
        base_path = AppConfig.SAVE_FILE_DIR
        users = ["Dedicated Server Saves"]
        if os.path.exists(base_path):
            users.extend([d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and d.isdigit()])
        return users

    def get_available_saves(self, steam_id):
        save_path = self.get_local_prospect_dir(steam_id)
        saves = []
        if os.path.exists(save_path):
            for file in os.listdir(save_path):
                if file.endswith(".json"):
                    saves.append(file.replace(".json", ""))
        return sorted(saves) if saves else ["No Saves Found"]

    def update_stats(self):
        for name, h in self.hosts.items():
            if h.get("status") in ["Running", "Saving..."] and name in self.active_processes:
                try:
                    p = self.active_processes[name]
                    if p.is_running():
                        h["cpu"] = f"{int(p.cpu_percent(interval=None) / psutil.cpu_count())}%"
                        h["ram"] = f"{int(p.memory_info().rss / 1024 / 1024)}MB"
                        h["uptime"] = time.strftime("%H:%M:%S", time.gmtime(int(time.time() - h.get("start_time", time.time()))))
                        
                        instance_dir = os.path.join(self.instances_dir, name)
                        save_dir = os.path.join(instance_dir, "Icarus", "Saved", "PlayerData", "DedicatedServer", "Prospects")
                        target_json = os.path.join(save_dir, f"{h['save_file']}.json")
                        if os.path.exists(target_json):
                            h["last_saved"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(target_json)))
                except (psutil.NoSuchProcess, psutil.AccessDenied): pass
            else: h.update({"uptime": "00:00:00", "cpu": "0%", "ram": "0MB"})

    def write_host_specific_configs(self, name):
        h = self.hosts[name]
        s = h['settings']
        conf_dir = os.path.join(self.host_configs_dir, name)
        os.makedirs(conf_dir, exist_ok=True)

        # ServerSettings.ini
        server_settings_content = (
            "[/Script/Icarus.DedicatedServerSettings]\n"
            f"SessionName={s.get('session_name', name)}\n"
            f"MaxPlayers={int(s.get('max_players', 8))}\n"
            "ResumeProspect=True\n"
            f"LoadProspect={h['save_file']}\n"
            f"JoinPassword={s.get('join_password', '')}\n"
            f"AdminPassword={s.get('admin_password', 'admin123')}\n"
            f"ShutdownIfNotJoinedFor={float(s.get('shutdown_timer', 300))}\n"
            f"ShutdownIfEmptyFor={float(s.get('shutdown_timer', 300))}\n"
            "CreateProspect=\n"
            f"LastProspectName={h['save_file']}\n"
            "AllowNonAdminsToLaunchProspects=True\n"
            "AllowNonAdminsToDeleteProspects=False\n"
            f"FiberFoliageRespawn={s.get('respawn_foliage', True)}\n"
            f"LargeStonesRespawn={s.get('respawn_rocks', True)}\n"
            f"GameSaveFrequency={float(s.get('save_freq', 60))}\n"
            "SaveGameOnExit=True\n\n"
            "[/Script/Icarus.IcarusServerSettings]\n"
            f"RespawnFrequencyMultiplier={float(s.get('respawn_freq', 1.0))}\n"
            f"bRespawnFoliage={s.get('respawn_foliage', True)}\n"
            f"bRespawnRocks={s.get('respawn_rocks', True)}\n\n"
        )
        with open(os.path.join(conf_dir, "ServerSettings.ini"), 'w', encoding='utf-8') as f:
            f.write(server_settings_content)

        # Engine.ini
        engine_ini_content = (
            "[/Script/OnlineSubsystemUtils.IpNetDriver]\n"
            f"NetServerMaxTickRate={int(s.get('tick_rate', 60))}\n"
            f"LanServerMaxTickRate={int(s.get('tick_rate', 60))}\n\n"
            "[SystemSettings]\n"
            f"gc.TimeBetweenPurgingPendingKillObjects={float(s.get('gc_interval', 60))}\n"
        )
        with open(os.path.join(conf_dir, "Engine.ini"), 'w', encoding='utf-8') as f:
            f.write(engine_ini_content)

    def link_host_config(self, name):
        instance_dir = os.path.join(self.instances_dir, name)
        server_config_parent_dir = os.path.join(instance_dir, "Icarus", "Saved", "Config")
        os.makedirs(server_config_parent_dir, exist_ok=True)
        
        junction_path = os.path.join(server_config_parent_dir, "WindowsServer")
        host_specific_config_path = os.path.join(self.host_configs_dir, name)

        if os.path.lexists(junction_path):
            try:
                if IS_WINDOWS:
                    os.rmdir(junction_path)
                else:
                    os.unlink(junction_path)
            except OSError:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                os.rename(junction_path, f"{junction_path}_Backup_{timestamp}")
        
        if IS_WINDOWS:
            subprocess.run(f'mklink /J "{junction_path}" "{host_specific_config_path}"', shell=True, check=True, capture_output=True)
        else:
            os.symlink(host_specific_config_path, junction_path)

    def get_launch_args(self, name, save_to_load):
        h = self.hosts[name]
        instance_dir = os.path.join(self.instances_dir, name)
        exe = os.path.join(instance_dir, "Icarus", "Binaries", "Win64", "IcarusServer-Win64-Shipping.exe")
        s = h['settings']

        args = [
            exe,
            "-Log",
            f"-SteamServerName={s.get('session_name', name)}",
            f"-Port={s.get('port', 17778)}",
            f"-QueryPort={s.get('query_port', 27016)}"
        ]

        # Standard performance optimizations
        args.extend(["-USEALLAVAILABLECORES", "-preventhibernation"])

        # Removed -nosteam: Icarus requires Steamworks for the LAN Server Browser to function.
        
        return args

    def verify_live_link(self, name):
        h = self.hosts.get(name)
        if not h: return
        steam_id = h.get('steam_id')
        if not steam_id: return
        
        instance_dir = os.path.join(self.instances_dir, name)
        local_prospect_dir = self.get_local_prospect_dir(steam_id)
        server_prospect_dir = os.path.join(instance_dir, "Icarus", "Saved", "PlayerData", "DedicatedServer", "Prospects")
        
        # Ensure local dir exists so junction doesn't silently break
        os.makedirs(local_prospect_dir, exist_ok=True)
        
        # Replicate PS1 logic: Check if it exists. If it's a real directory and not a junction, rename it.
        if os.path.lexists(server_prospect_dir):
            try:
                if IS_WINDOWS:
                    os.rmdir(server_prospect_dir) # Safe removal of junction
                else:
                    os.unlink(server_prospect_dir)
            except OSError:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                os.rename(server_prospect_dir, f"{server_prospect_dir}_Backup_{timestamp}")
        
        os.makedirs(os.path.dirname(server_prospect_dir), exist_ok=True)
        if IS_WINDOWS:
            subprocess.run(f'mklink /J "{server_prospect_dir}" "{local_prospect_dir}"', shell=True, capture_output=True)
        else:
            os.symlink(local_prospect_dir, server_prospect_dir)

    def setup_restore(self, name, backup_path, prospect_name):
        h = self.hosts[name]
        try:
            # Only create pre_restore backup if we aren't already in a restore session
            if 'restore_info' not in h:
                self.create_backup(name, pre_restore=True)
                
            steam_id = h['steam_id']
            local_prospect_dir = self.get_local_prospect_dir(steam_id)
            source_json = os.path.join(backup_path, f"{prospect_name}.json")
            if not os.path.exists(source_json):
                return False, f"Backup is incomplete. Could not find '{prospect_name}.json' in the backup."
            shutil.copy2(source_json, os.path.join(local_prospect_dir, f"{prospect_name}.json"))

            h['restore_info'] = {
                'is_restore': True,
                'original_save_name': prospect_name,
            }
            self.save_configs()
            return True, "Restore point staged successfully.\n\nPress 'Start' to launch the server with this restore point."
        except Exception as e:
            return False, f"Failed to prepare restore session: {e}"

    def add_firewall_rule(self, name, exe_path):
        rule_name_in = f"Icarus Virtual Host (In) - {name}"
        rule_name_out = f"Icarus Virtual Host (Out) - {name}"
        check_cmd = f'powershell -Command "Get-NetFirewallRule -DisplayName \'{rule_name_in}\' -ErrorAction SilentlyContinue"'
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        if not result.stdout.strip():
            # The rule does not exist, so we elevate and add both Inbound and Outbound
            ps_add = (f"New-NetFirewallRule -DisplayName '{rule_name_in}' -Direction Inbound -Program '{exe_path}' -Action Allow; "
                      f"New-NetFirewallRule -DisplayName '{rule_name_out}' -Direction Outbound -Program '{exe_path}' -Action Allow")
            b64_cmd = base64.b64encode(ps_add.encode('utf-16le')).decode('utf-8')
            
            elevate_cmd = f'powershell -Command "Start-Process powershell -ArgumentList \'-WindowStyle Hidden -EncodedCommand {b64_cmd}\' -Verb RunAs"'
            subprocess.run(elevate_cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)

    def launch_server(self, name):
        h = self.hosts[name]
        save_to_load = h['save_file']
        s = h['settings']

        target_port = int(s.get('port', 17778))
        target_query = int(s.get('query_port', 27016))

        # Check for port collisions with other running servers
        for active_name, active_proc in self.active_processes.items():
            if name == active_name or not active_proc.is_running(): continue
            active_h = self.hosts.get(active_name)
            if not active_h: continue
            
            active_s = active_h.get('settings', {})
            active_port = int(active_s.get('port', 17777))
            active_query = int(active_s.get('query_port', 27015))
            if target_port == active_port:
                return False, f"Port conflict:\n\nServer '{active_name}' is actively running on TCP Port {active_port}."
            if target_query == active_query:
                return False, f"Port conflict:\n\nServer '{active_name}' is actively running on UDP Port {active_query}."

        instance_dir = os.path.join(self.instances_dir, name)
        exe_check = os.path.join(instance_dir, "Icarus", "Binaries", "Win64", "IcarusServer-Win64-Shipping.exe")
        if not os.path.exists(exe_check):
            try:
                self.hosts[name].update({"status": "Cloning...", "auto_restart": False})
                shutil.copytree(self.master_dir, instance_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.log', 'Saved'))
                self.hosts[name]['status'] = "Cloned."
            except Exception as e:
                self.hosts[name]['status'] = "Clone Failed"
                return False, f"Failed to create server instance clone: {e}"

        # Exact PS1 Watchdog Loop Behavior: Backup immediately before launch
        self.create_backup(name)
        
        # Verify Live Link exactly like the PS1 setup block
        self.verify_live_link(name)

        # Write the latest configs and link them for this host
        self.write_host_specific_configs(name)
        self.link_host_config(name)

        self.save_configs()
        args = self.get_launch_args(name, save_to_load)
        exe = args[0]
        
        if not os.path.exists(exe):
            return False, f"Server executable not found at:\n{exe}\n\nPlease verify your server files in the Server_Master directory."
            
        if IS_WINDOWS:
            self.add_firewall_rule(name, exe)
            
        launch_cmd = AppConfig.WINE_PREFIX + args
        proc = subprocess.Popen(launch_cmd, cwd=os.path.dirname(exe), creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0)
        
        try:
            proc_obj = psutil.Process(proc.pid)
            if IS_WINDOWS:
                proc_obj.nice(psutil.HIGH_PRIORITY_CLASS)
            else:
                proc_obj.nice(-10) # High priority in Linux
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

        self.active_processes[name] = psutil.Process(proc.pid)
        self.hosts[name].update({"status": "Running", "start_time": time.time(), "auto_restart": True})
        connect_info = f"{self.public_ip}:{target_port}"
        threading.Thread(target=self.send_discord_notification, args=(name, f"✅ Server **{name}** is ONLINE.\n🔌 **Direct Connect:** `{connect_info}`")).start()
        threading.Thread(target=self.watchdog_loop, args=(name,), daemon=True).start()
        return True, "Launched"

    def watchdog_loop(self, name):
        last_player_count = 0
        query_port = int(self.hosts.get(name, {}).get('settings', {}).get('query_port', 27016))
        check_counter = 0

        while name in self.active_processes:
            proc = self.active_processes[name]
            try:
                if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                    self.hosts[name]["status"] = "Crashed"
                    self.active_processes.pop(name, None)
                    self.send_discord_notification(name, f"⚠️ Server **{name}** has CRASHED.")
                    if self.hosts[name].get("auto_restart"):
                        self.send_discord_notification(name, f"🔄 Server **{name}** is AUTO-RESTARTING...")
                        self.launch_server(name)
                    break
                
                check_counter += 1
                if check_counter >= 5:  # Check player count roughly every 10 seconds
                    current_players = self.get_player_count(query_port)
                    if current_players != -1:
                        if current_players < last_player_count:
                            self.send_discord_notification(name, f"💾 Player disconnected. Creating automated backup...")
                            self.create_backup(name)
                        last_player_count = current_players
                    check_counter = 0
            except psutil.NoSuchProcess:
                pass
            time.sleep(2)

    def stop_server(self, name, create_backup_on_stop=True):
        if name in self.active_processes:
            self.hosts[name]["auto_restart"] = False
            self.hosts[name]["status"] = "Stopping..."
            
            proc = self.active_processes.pop(name)
            try:
                if sys.platform == "win32":
                    os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
                else:
                    proc.terminate()
            except Exception:
                try: proc.terminate()
                except psutil.NoSuchProcess: pass
                
            try:
                proc.wait(timeout=20)
            except psutil.TimeoutExpired:
                try:
                    for child in proc.children(recursive=True):
                        child.kill()
                    proc.kill()
                    proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired): pass
            
            self.hosts[name]["status"] = "Offline"
            self.send_discord_notification(name, f"❌ Server **{name}** is OFFLINE.")
            
            if create_backup_on_stop:
                success, msg = self.create_backup(name)
                if not success:
                    return True, f"Server stopped, but backup failed: {msg}"
                return True, msg            
            return True, None
        return False, "Server not running or already stopped."

    def save_server(self, name):
        if self.hosts.get(name, {}).get('status') == "Running":
            self.hosts[name]['status'] = "Saving..."
            return True
        return False

    def get_player_count(self, query_port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2.0)
            # Send A2S_INFO Source Engine Query to check player count natively
            sock.sendto(b'\xFF\xFF\xFF\xFFTSource Engine Query\x00', ('127.0.0.1', query_port))
            data, _ = sock.recvfrom(2048)
            if data.startswith(b'\xff\xff\xff\xffI'):
                idx = 6
                idx = data.find(b'\x00', idx) + 1  # Skip Server Name
                idx = data.find(b'\x00', idx) + 1  # Skip Map
                idx = data.find(b'\x00', idx) + 1  # Skip Folder
                idx = data.find(b'\x00', idx) + 1  # Skip Game
                idx += 2  # Skip App ID
                return data[idx] # Player Count byte
        except Exception: pass
        return -1

    def get_local_build_id(self, install_dir):
        acf_path = os.path.join(install_dir, "steamapps", "appmanifest_2089300.acf")
        if os.path.exists(acf_path):
            with open(acf_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if '"buildid"' in line:
                        parts = line.split('"')
                        if len(parts) >= 4: return parts[3]
        return None

    def _run_silent_master_update(self):
        script_path = os.path.join(self.app_dir, "silent_master_update.txt")
        try:
            with open(script_path, "w") as f:
                f.write(f'force_install_dir "{self.master_dir}"\nlogin anonymous\n@sSteamCmdForcePlatformType windows\napp_update 2089300 validate\nquit\n')
            cmd = [self.steamcmd_path, "+@sSteamCmdForcePlatformType", "windows", "+runscript", script_path]
            if not IS_WINDOWS:
                cmd.insert(0, "bash")
            with self.update_lock:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except: pass
        finally:
            if os.path.exists(script_path): os.remove(script_path)

    def _run_silent_instance_update(self, name):
        instance_dir = os.path.join(self.instances_dir, name)
        script_path = os.path.join(self.app_dir, f"silent_update_{name}.txt")
        try:
            with open(script_path, "w") as f:
                f.write(f'force_install_dir "{instance_dir}"\nlogin anonymous\n@sSteamCmdForcePlatformType windows\napp_update 2089300 validate\nquit\n')
            cmd = [self.steamcmd_path, "+@sSteamCmdForcePlatformType", "windows", "+runscript", script_path]
            if not IS_WINDOWS:
                cmd.insert(0, "bash")
            with self.update_lock:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except: pass
        finally:
            if os.path.exists(script_path): os.remove(script_path)

    def auto_update_loop(self):
        while True:
            time.sleep(1800) # Check for an update every 30 minutes in the background
            
            self._run_silent_master_update()
            master_build_id = self.get_local_build_id(self.master_dir)
            if not master_build_id: continue
                
            for name, h in list(self.hosts.items()):
                instance_dir = os.path.join(self.instances_dir, name)
                inst_build_id = self.get_local_build_id(instance_dir)
                
                # Compare the instance's build ID against the master. If outdated, trigger isolated thread.
                if inst_build_id and inst_build_id != master_build_id:
                    if name not in self.updating_hosts:
                        self.updating_hosts.add(name)
                        threading.Thread(target=self._process_host_update, args=(name, h), daemon=True).start()

    def _process_host_update(self, name, h):
        try:
            is_running = name in self.active_processes
            if is_running:
                self.send_discord_notification(name, f"🔄 Update detected! Waiting for players to disconnect before applying...")
                query_port = int(h.get('settings', {}).get('query_port', 27016))
                
                while name in self.active_processes:
                    p_count = self.get_player_count(query_port)
                    if p_count == 0 or p_count == -1: break
                    time.sleep(60) # Wait and check player count again in 1 minute
                    
                if name in self.active_processes:
                    self.send_discord_notification(name, f"⚙️ Server empty. Applying update to **{name}**...")
                    self.stop_server(name, create_backup_on_stop=True)
                    while name in self.active_processes: time.sleep(2)
                    should_restart = True
                else:
                    should_restart = False # Server was manually stopped by user during waiting period
            else:
                should_restart = False
                
            self.hosts[name]["status"] = "Updating..."
            self._run_silent_instance_update(name)
            self.hosts[name]["status"] = "Offline"
            
            if should_restart:
                self.launch_server(name)
        finally:
            self.updating_hosts.discard(name)

    def update_master_files(self, progress_callback):
        if not os.path.exists(self.steamcmd_path): return False, "SteamCMD missing."
        
        # Pre-clone master to any new instances so SteamCMD only needs to do a fast delta validation
        master_exe = os.path.join(self.master_dir, "Icarus", "Binaries", "Win64", "IcarusServer-Win64-Shipping.exe")
        if os.path.exists(master_exe):
            for name in self.hosts:
                instance_dir = os.path.join(self.instances_dir, name)
                exe_path = os.path.join(instance_dir, "Icarus", "Binaries", "Win64", "IcarusServer-Win64-Shipping.exe")
                if not os.path.exists(exe_path):
                    progress_callback(f"Cloning base files to '{name}' before update... (This may take a moment)\n")
                    try: shutil.copytree(self.master_dir, instance_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.log', 'Saved'))
                    except Exception: pass

        script_path = os.path.join(self.app_dir, "update_script.txt")
        try:
            with open(script_path, "w") as f:
                f.write(f'force_install_dir "{self.master_dir}"\nlogin anonymous\n@sSteamCmdForcePlatformType windows\napp_update 2089300 validate\n')
                for name in self.hosts:
                    instance_dir = os.path.join(self.instances_dir, name)
                    f.write(f'force_install_dir "{instance_dir}"\napp_update 2089300 validate\n')
                f.write('quit\n')
            cmd = [self.steamcmd_path, "+@sSteamCmdForcePlatformType", "windows", "+runscript", script_path]
            if not IS_WINDOWS:
                cmd.insert(0, "bash")
            with self.update_lock:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                
                current_line = b""
                while True:
                    char = process.stdout.read(1)
                    if not char:
                        if current_line: progress_callback(current_line.decode('utf-8', errors='replace').strip())
                        break
                    if char in (b'\n', b'\r'):
                        if current_line:
                            text = current_line.decode('utf-8', errors='replace').strip()
                            current_line = b""
                            progress_callback(text)
                    else:
                        current_line += char
                
                process.wait()
        except Exception as e: return False, str(e)
        finally:
            if os.path.exists(script_path): os.remove(script_path)
        return True, "Verified"

    def create_backup(self, name, pre_restore=False):
        h = self.hosts.get(name)
        if not h: return False, "Host not found."

        try:
            prospect_name = h['save_file']
            instance_dir = os.path.join(self.instances_dir, name)

            # Exact PS1 Behavior: Target the Server's live-linked Prospects folder
            server_prospects_dir = os.path.join(instance_dir, "Icarus", "Saved", "PlayerData", "DedicatedServer", "Prospects")

            if not os.path.exists(server_prospects_dir):
                return False, f"Could not find server prospects directory at:\n{server_prospects_dir}"

            source_file = os.path.join(server_prospects_dir, f"{prospect_name}.json")
            if not os.path.exists(source_file):
                return False, f"Save file '{prospect_name}.json' not found."

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            
            if pre_restore:
                backup_folder_name = "pre_restore_backup"
            else:
                backup_folder_name = f"backup_{name}_{timestamp}"
                
            backup_dest_dir = os.path.join(self.backup_dir, prospect_name, backup_folder_name)
            
            # Only backup the specific save file, not the entire directory
            os.makedirs(backup_dest_dir, exist_ok=True)
            shutil.copy2(source_file, os.path.join(backup_dest_dir, f"{prospect_name}.json"))

            return True, f"Backup of '{prospect_name}' created as:\n{backup_folder_name}"
        except Exception as e:
            return False, f"Backup failed: {e}"

    def get_backed_up_saves(self):
        if not os.path.exists(self.backup_dir): return []
        return sorted([d for d in os.listdir(self.backup_dir) if os.path.isdir(os.path.join(self.backup_dir, d))])

    def get_backup_timestamps(self, save_file):
        save_backup_dir = os.path.join(self.backup_dir, save_file)
        if not os.path.exists(save_backup_dir): return []
        return sorted([d for d in os.listdir(save_backup_dir) if os.path.isdir(os.path.join(save_backup_dir, d)) and d != "pre_restore_backup"], reverse=True)

    def handle_restore_shutdown(self, name, action, new_name=None):
        h = self.hosts.get(name)
        if not h or 'restore_info' not in h:
            return False, "Not a restore session or host not found."

        restore_info = h['restore_info']
        original_save_name = restore_info['original_save_name']
        
        steam_id = h['steam_id']
        local_prospect_dir = self.get_local_prospect_dir(steam_id)
        
        current_json_path = os.path.join(local_prospect_dir, f"{original_save_name}.json")
        pre_restore_backup_path = os.path.join(self.backup_dir, original_save_name, "pre_restore_backup", f"{original_save_name}.json")
        pre_restore_dir = os.path.join(self.backup_dir, original_save_name, "pre_restore_backup")

        try:
            if action == 'overwrite':
                if os.path.exists(pre_restore_backup_path):
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    new_backup_name = f"{original_save_name}_Original_Pre_Restore_{timestamp}"
                    new_backup_dir = os.path.join(self.backup_dir, original_save_name, new_backup_name)
                    os.rename(pre_restore_dir, new_backup_dir)
                msg = f"Successfully overwrote '{original_save_name}.json' with session progress."
            else:
                if action == 'save_as':
                    if not new_name or not new_name.strip(): return False, "New name cannot be empty."
                    dest_json_path = os.path.join(local_prospect_dir, f"{new_name}.json")
                    if os.path.exists(dest_json_path): return False, "A save with that name already exists."
                    
                    try:
                        # Open the save file, update the internal ID to match the new filename, and write it
                        with open(current_json_path, 'r', encoding='utf-8-sig') as f:
                            save_data = json.load(f)
                        if "ProspectID" in save_data:
                            save_data["ProspectID"] = new_name
                        with open(dest_json_path, 'w', encoding='utf-8') as f:
                            json.dump(save_data, f)
                    except Exception:
                        # Fallback to a standard copy if JSON parsing fails for any reason
                        shutil.copy2(current_json_path, dest_json_path)
                    msg = f"Session progress saved as new prospect '{new_name}.json'."
                elif action == 'discard':
                    msg = "Changes from restore session have been discarded."
                else:
                    return False, f"Unknown action: {action}"

                # Both save_as and discard revert the live save and delete the temp safety backup
                if os.path.exists(pre_restore_backup_path):
                    shutil.copy2(pre_restore_backup_path, current_json_path)
                if os.path.exists(pre_restore_dir):
                    shutil.rmtree(pre_restore_dir)

            del self.hosts[name]['restore_info']
            self.save_configs()
            return True, msg
        except Exception as e:
            return False, str(e)

    def send_discord_notification(self, name, message):
        webhook_url = self.hosts[name].get('settings', {}).get('discord_webhook', "")
        if not webhook_url: return
        data = json.dumps({"content": f"**[IDSM]** {message}"}).encode('utf-8')
        req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as r: pass
        except: pass

    def load_configs(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                try: return json.load(f)
                except: return {}
        return {}

    def save_configs(self):
        with open(self.config_file, 'w') as f: json.dump(self.hosts, f, indent=4)

    def create_host_slot(self, name, save_file_name, steam_id):
        if name in self.hosts: return False, "Host already exists."
        try:
            next_port = 17778
            existing_ports = []
            existing_queries = []
            if self.hosts:
                for host_data in self.hosts.values():
                    try: existing_ports.append(int(host_data.get('settings', {}).get('port', 17778)))
                    except ValueError: pass
                    try: existing_queries.append(int(host_data.get('settings', {}).get('query_port', 27016)))
                    except ValueError: pass
                if existing_ports:
                    max_existing = max(existing_ports)
                    if max_existing >= 17778: next_port = max_existing + 1
            
            next_query = 27016
            if existing_queries:
                max_query = max(existing_queries)
                if max_query >= 27016: next_query = max_query + 1
            
            self.hosts[name] = {
                "save_file": save_file_name, "steam_id": steam_id, "status": "Offline", "uptime": "00:00:00", "last_saved": "Never",
                "start_on_app_load": False,
                "settings": { "session_name": name, "join_password": "", "admin_password": "admin123", "port": next_port, "query_port": next_query, "max_players": 8, "save_freq": 60, "tick_rate": 60, "gc_interval": 60, "shutdown_timer": 300, "respawn_foliage": True, "respawn_rocks": True, "is_public": True, "respawn_freq": 1.0, "discord_webhook": "" }
            }
            self.write_host_specific_configs(name)
            self.save_configs()
            self.verify_live_link(name)
            backup_success, backup_msg = self.create_backup(name)
            if backup_success:
                return True, "Success"
            else:
                return True, f"Host created, but initial backup failed:\n{backup_msg}"
        except Exception as e: return False, str(e)

    def update_host_name(self, old_name, new_settings):
        new_name = new_settings['session_name']
        
        # If name changes, move the config directory
        if old_name != new_name and os.path.exists(os.path.join(self.host_configs_dir, old_name)):
            os.rename(os.path.join(self.host_configs_dir, old_name), os.path.join(self.host_configs_dir, new_name))
        
        if old_name == new_name: 
            self.hosts[old_name]['settings'].update(new_settings)
            self.write_host_specific_configs(old_name)
            self.save_configs(); return old_name
            
        self.hosts[new_name] = self.hosts.pop(old_name)
        self.hosts[new_name]['settings'].update(new_settings)
        if old_name in self.active_processes:
            self.active_processes[new_name] = self.active_processes.pop(old_name)
        
        self.write_host_specific_configs(new_name)
        self.save_configs(); return new_name

    def delete_host(self, name):
        if name in self.hosts:
            if name in self.active_processes:
                proc = self.active_processes.pop(name)
                try:
                    if proc.is_running():
                        for child in proc.children(recursive=True): child.kill()
                        proc.kill()
                        proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired): pass

            del self.hosts[name]
            self.save_configs()

            # Clean up the host's config directory
            host_conf_dir = os.path.join(self.host_configs_dir, name)
            if os.path.exists(host_conf_dir):
                shutil.rmtree(host_conf_dir)

            # Clean up the instance directory
            instance_dir = os.path.join(self.instances_dir, name)
            if os.path.exists(instance_dir):
                shutil.rmtree(instance_dir)

            return True
        return False

    def toggle_windows_startup(self, enable):
        if not IS_WINDOWS: return False, "Windows startup toggle is only supported on Windows."
        
        startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        bat_path = os.path.join(startup_dir, "IDSM_Startup.bat")
        try:
            if enable:
                exe_path = f'"{sys.executable}"' if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                with open(bat_path, "w") as f: f.write(f'@echo off\ncd /d "{self.app_dir}"\nstart "" {exe_path}\n')
                return True, "Windows startup enabled successfully."
            else:
                if os.path.exists(bat_path):
                    os.remove(bat_path)
                return True, "Windows startup disabled successfully."
        except Exception as e:
            return False, f"Failed to modify Windows startup: {e}"

    def is_windows_startup_enabled(self):
        if not IS_WINDOWS: return False
        
        startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        bat_path = os.path.join(startup_dir, "IDSM_Startup.bat")
        return os.path.exists(bat_path)