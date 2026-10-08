# SaveHarbor user guide

## Find the right save folder

Save locations are chosen by each game's developer and can vary by title, launcher, and Windows account. Common places include:

- `%USERPROFILE%\Documents\My Games\<Game>`
- `%USERPROFILE%\Saved Games\<Game>`
- `%APPDATA%\<Publisher>\<Game>`
- `%LOCALAPPDATA%\<Publisher>\<Game>`
- A `userdata` or `remote` directory inside a Steam library for games that use Steam Cloud.

These are examples, not universal paths. Check the game's documentation or search for its save location before creating a profile. Choose the folder that contains the save files, not the whole Documents or AppData directory.

## Create a profile and snapshot

1. Start SaveHarbor and click **Add save folder**.
2. Select the game's save folder and give the profile a recognizable name.
3. Select the profile and click **Create snapshot**.
4. The history shows the timestamp, file count, uncompressed size, and the beginning of the archive SHA-256.

Snapshots are stored under `%LOCALAPPDATA%\SaveHarbor\backups\<profile>\`. Use **Backup folder** to open the location. You can copy a `.saveharbor.zip` to another disk; its manifest travels with it.

## Compare and verify

- Select two history rows with Ctrl-click or Shift-click, then choose **Compare two snapshots**. The older and newer snapshots are compared by relative path and SHA-256.
- Select one row and choose **Verify SHA-256** to read each archived file and compare it with the manifest.
- Double-click a history row to run the same verification.

## Restore

1. Close the game and its launcher if they may write to the save folder.
2. Select one snapshot and click **Restore selected**.
3. Confirm the action. SaveHarbor first creates a snapshot of the current save folder as a safety copy.
4. Files from the selected snapshot are overlaid into the profile folder. Matching paths are replaced; paths absent from the snapshot are not deleted.

If you need the exact historical folder state, make a copy of the current folder first, or restore into an empty folder and inspect it before moving anything into the game's save location.

## Command line

```powershell
saveharbor backup "C:\path\to\save-folder" "My Game"
saveharbor verify "C:\path\to\snapshot.saveharbor.zip"
```

The command prints the file count, byte size, and full SHA-256 of the generated or verified archive.

## Privacy and recovery

All operations are local. SaveHarbor has no network feature and never deletes the original save folder during a restore. A checksum is an integrity check, not a malware scan. For important saves, keep a copy of the backup on another physical drive.
