# Install, upgrade and reinstall

Run the Gaming Buddy installer for your Windows account. Setup uses the existing
per-user installation and retains the previous shortcut choices. On the Ready page it
shows **Install**, **Upgrade**, or **Reinstall**, together with the installed and target
versions. The final action button uses the same operation name.

- **Install:** no existing registered or versioned copy was found.
- **Upgrade:** the installer is newer than the detected installation.
- **Reinstall:** the versions match. Program/runtime files are refreshed, including
  removal of stale runtime files. Saved cards, images, layouts and settings are kept.

Versions are compared numerically, so 1.10.0 is newer than 1.9.0. Setup checks both
Windows registry views and the existing executable, using the highest verified version.
A newer detected version blocks installation before program files are changed. An
unreadable or invalid existing version also blocks replacement. If the installation
metadata is damaged, uninstall while keeping your data, then reinstall a suitable build.

These safeguards apply to installers built with the maintenance checks. An older
installer downloaded before these checks were implemented is not retroactively changed.
Use the current installer and verify its identity and SHA-256 before running it.

## Close the running application

Choose **Quit** from Gaming Buddy's tray menu and wait for the application to finish
saving and exit. Closing its main window can leave it running in the tray. Setup and
Uninstall ask you to close it; they do not force termination. Retry after it has exited.
Silent installation/uninstallation also refuses to continue while the application mutex
is present. Quit the app first, then retry your silent command.

Before installation, Setup rechecks the version and running-app state. It also checks
access to existing program/runtime files without writing to them. A locked file,
inaccessible folder, or runtime reparse point stops replacement before stale-file cleanup.
If this occurs, close the app, check folder access, and retry. Older application builds
without the new mutex are covered by the existing-file check, but cooperative startup
exclusion requires the updated application as well as the updated installer.

Opening the updated app manually while Setup is active shows a message before its
workspace is opened. The optional **Launch Gaming Buddy** action waits briefly for Setup
to finish instead. If Setup does not finish within 15 seconds, launch the app again after
closing the installer. The internal `--after-install` argument only waits; it does not
bypass the installation check.

## Data and recovery

Installation and upgrade do not move or delete the per-user workspace. During an
interactive uninstall, choose **No** when asked whether to delete saved data to retain
it for a future installation. Silent uninstall also keeps data by default. Explicit
purging remains a separate destructive choice.

The preflight checks protect against known version/running-file conflicts; they do not
promise transactional rollback of every program file after a power failure or disk error.
After an interrupted installation, finish closing the app and rerun the same or newer
installer. Keep workspace backups before testing unfamiliar development builds.

The native installer tests use the production maintenance logic with unique test
identities and small, versioned fixture programs. They verify installation operations
and retention of real SQLite cards/settings/captures without installing or removing the
user's actual Gaming Buddy. They are not clean-Windows or installed real-app UI acceptance.
