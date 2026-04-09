I am happy to present this Icarus Dedicated Server Management Tool that I have built on the architecture of my previous tool IcarusDS v2.0 but turning it into a fully functional app on Windows with a tonne of features that I will go over in the guide. This app continues to use the SteamCMD platform with the addition of python to create a very user friendly interface. No major actions are required to upgrade to this app if you are coming from any of my previous guides or are already using the SteamCMD platform.

Background

For those who are unaware about the benefits of using a dedicated server, it seems counter-intuitive to run two separate programs to do the job of one, but for a resource-heavy game like Icarus, the "Dedicated-on-Same-PC" approach is actually a massive optimization. When you host from within the game client, your CPU is trying to do two massive jobs inside a single process. Rendering output to your GPU and calculating all the physics and effect on every building piece, bench and material you craft, gather and obtain. By moving the world logic to a Dedicated Server, you create a second process. Your specific hardware results will vary, however this generally improves performance across the board.

My 2.0 guide was robust and did the job and I still used it through the testing of this app but there were a few issues that I wanted to iron out and improve on. Mainly the issues were user inputted saving intervals and performance profiles that weren’t being applied properly, and I was growing frustrated with the amount of clutter on my desktop. I also wanted to address multiple hosts as I am in a situation where I host a world for a group I play with and then I will host other maps when I play with my partner locally or solo.

The multi-host function is a gamer-changer feature to include in this app. I originally was trying to make a virtual host function however i had a number of issues trying to get the multiple config files to apply properly and I had issues with the live link. So i opted for a much more robust method of essentially just copying the important files into a ServerMaster folder that gets generated on app first run, duplicates on new host creations and continues to maintain updates as they are provided. With this function, you are able to create an unlimited (limited based on your resources) number of Hosts. I have protocols in place to prevent multiple hosts with same ports to run at the same time and many others to prevent accidental conflicts. Each new host will be ~10Gb.

My previous tool had a live link feature that created a link between the games local save files and the Dedicated Servers save directory. This worked great and I kept this feature however I added in a backup and restore feature that puts you in control of your backups and allows you to restore a game to a previous save with several protocols in place to prevent accidental deletion or overwriting of your original save files (more in the AppGuide). If you plan to use this app on a computer with without any Steam users logged on the computer you plan to host your servers on you are able to point the app to read the save files from within the IDS folder. The live link logic still applies to save files placed within the IDS directory.

The updating routine is also still very much a part of this app, but it’s handled during app startup now not server startup. However, the updates do need to be applied to each host as they startup. This is just a copy routine from the main SteamCMD to the active host. This update routine will happen on every app startup and whenever there is a new update. I have logic in place to handle how the app applies the updates based on if the Host is active or not. If any connection errors are encountered due to an update, restarting the app will apply any new updates. This update logic isn't fully tested as it is hard to lineup the app with game updates, but I have a bunch of logic hardcoded in to hopefully prevent updated related connection issues and I have worked through the issues that I have experienced.

The plan was to post this app and then enjoy it, maybe deal with some troubleshooting or bugs but I will be working on turning this app into a container to work in Docker (with WINE). I do not have an ETA on when to expect this but it will come because that is the route I want this app to go. This app will still be available and I will still provide support for it because the container version is built off the app. With that said I am always open to feature suggestions to further improve this app/container. Feel free to reach out via Reddit for any troubleshooting, bug reporting or suggestions.

Disclaimers

•	I have noticed a performance improvement with this guide mostly because I know the performance profiles are being applied and I have tested out hosting a server on the same PC I play on. This will vary based on your PC and which settings you select but its definitely a noticeable improvement on my previous tool.

•	Port Forwarding is done on your own accord and risk and IS required to play online with others. This app makes selecting your ports simple and has some logic built in for default ports which I would recommend sticking to (more in the AppGuide).

•	I am not responsible for any lost data. It is your own responsibility to back up your data even though this is quite low risk. This app does a really good job of backing up your save files but it is reading and overwriting your local save files.

•	This is not a world generator. If you don't have a save file you need to generate one in the game first.

•	I have tested this app thoroughly. That does not mean that this app may be without bugs. I have tested it on a secondary computer with success as well. Still, user experience may vary from mine, but if there are any bugs reach out with as much detail as you can and I will help troubleshoot.


Features

•	App based simple Graphical User Interface for managing Server(s)

•	Multi-Hosting capabilities

•	Watchdog for server stability and updates

•	Save routines hardcoded with options to change the save frequency and a backup and restore feature

•	Multiple server settings to customize including performance options and in game options

•	Resource monitoring per server and for PC

•	Windows startup and app startup options for automatic server starts



Installation Guide


If you are coming from a previous guide of mine or already have SteamCDM installed you can skip ahead to Phase 3.

Phase 1: Prerequisites

Download SteamCMD from https://developer.valvesoftware.com/wiki/SteamCMD

Extract it to a folder named C:\SteamCMD (or wherever you want to put it but this is RECOMMENDED. If you do want a different installation directory please note the next steps will require you to change the directory to match what directory you choose. The app is hardcoded to work from the Icarus Dedicated Server (IDS) folder.

Run steamcmd.exe once to let it update and install, then close it when done.


Phase 2: Install the Server

Open a terminal in your C:\SteamCMD folder (or your directory of choice and edit the command below to match!).

Run this command to download the Icarus Server files:

.\steamcmd.exe +force_install_dir "C:\SteamCMD\steamapps\common\Icarus Dedicated Server" +login anonymous +app_update 2089300 validate +quit

Crucial: Navigate to the server folder (C:\SteamCMD\steamapps\common\Icarus Dedicated Server\Icarus\Binaries\Win64) and run IcarusServer-Win64-Shipping.exe (the application name may vary but it will be the only .exe there) once manually. Let it run (should take 10 seconds but has been known to run then close or not even show anything at all. If folders are generated in this folder then you may proceed), then close it.


Phase 3: Install the IDSM app

Download this repository as a ZIP (Click the green Code button > Download ZIP).

Extract the app (IDSM.exe) into your IDS folder:

C:\SteamCMD\steamapps\common\Icarus Dedicated Server\

First Run

Please note that depending on your antivirus you may run into issues on the first run. I recommend placing an exception with your anti-virus software for the entire SteamCMD folder. First run may also take a little bit longer than normal as an update will likely occur on the SteamCMD platform. Depending on your security settings you may be prompt to allow each server to run for the first time. AFTER the first run you can create a desktop shortcut to access this app from your desktop. Open the AppGuide for directions on all the features within the app.
