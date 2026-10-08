SaveHarbor Pro Scheduler — v1.0.0
==================================

This is an optional automation pack for the free SaveHarbor app. It creates a daily Windows Task Scheduler job, keeps a configurable number of snapshots, and verifies the newest archive before retention removes older archives.

REQUIREMENTS
- Windows 10/11
- Python 3.11+ with SaveHarbor installed from its source folder: python -m pip install .
- The free app source/release: https://github.com/GhosTnever-lkm/saveharbor/releases
- The computer must be awake and your Windows user must be signed in for the task to run.

SETUP
1. Download and extract the SaveHarbor source/release ZIP. In that folder, open PowerShell and run: python -m pip install .
2. Extract this Pro ZIP to a permanent folder, for example %USERPROFILE%\Tools\SaveHarbor-Pro. Do not run the task from a temporary Downloads extraction.
3. Copy profiles.example.json to profiles.json.
4. Edit Python to point to the same python.exe used to install SaveHarbor. Edit each profile's Name and Folder. KeepLast must be between 2 and 365.
5. In File Explorer, open this folder. Right-click Register-SaveHarborTask.ps1 and choose Run with PowerShell, or open PowerShell in the folder and run:
   .\Register-SaveHarborTask.ps1 -At '03:00'
   The task runs as your current user with limited privileges; it does not request administrator access.
6. Open Task Scheduler, find "SaveHarbor Pro Daily Backups", then choose Run. Inspect %LOCALAPPDATA%\SaveHarbor\Pro\logs for the result.

MANUAL RUN
   .\Run-SaveHarborBackups.ps1
   .\Run-SaveHarborBackups.ps1 -ConfigPath 'D:\Backups\profiles.json'

SAFETY AND LIMITS
- The runner creates a snapshot, verifies every file against the SHA-256 manifest, and only then applies retention to that profile's own *.saveharbor.zip files.
- KeepLast is clamped to 2–365 so the automation never removes all recovery points.
- Retention deletion is limited to that profile's archive directory inside %LOCALAPPDATA%\SaveHarbor\backups.
- The task only runs while your user is signed in. It will start when the computer becomes available after the scheduled time.
- Close a game before backup or restore so it cannot write while the snapshot is being created.
- Logs include profile names and folder paths and remain on this PC in %LOCALAPPDATA%\SaveHarbor\Pro\logs.
- No data is uploaded. This pack does not include cloud sync or encryption.

To remove the scheduled task, open Task Scheduler, right-click its name, and choose Delete. Your snapshots and logs are kept.
