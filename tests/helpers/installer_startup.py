"""Exercise real startup refusal before any workspace or settings are opened."""

import sys

import gaming_buddy.app as app_module
from gaming_buddy.installer_guard import hold_installer_guard


def unexpected_workspace():
    if "--after-install" in sys.argv:
        print("WORKSPACE_ALLOWED", flush=True)
        raise SystemExit(0)
    raise AssertionError("Startup opened the workspace while Setup was running")


app_module.hold_installer_guard = lambda **kwargs: hold_installer_guard(
    sys.argv[1], sys.argv[2], **kwargs,
)
app_module.ensure_data_dirs = unexpected_workspace
app_module.QMessageBox.warning = lambda _parent, _title, message: print(message, flush=True)
if "--after-install" in sys.argv:
    print("BOOT", flush=True)
raise SystemExit(app_module.main())
