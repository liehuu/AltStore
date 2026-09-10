#!/usr/bin/env python3
"""Stop AltStore's App Intent from shadowing the legacy SiriKit "Refresh All Apps".

Runs inside a checkout of altstoreio/AltStore.

Problem
-------
AltStore ships two independent "Refresh All Apps" actions:

1. the legacy SiriKit intent `RefreshAllIntent`
   (`AltStore/Intents/Legacy/Intents.intentdefinition`, `INIntentsSupported` in
   Info.plist, handled by `IntentHandler` via `AppDelegate.application(_:handlerFor:)`).
   This is what every AltStore before 2.0 used, and it works on iOS 17.0/17.1.
2. the App Intent `RefreshAllAppsIntent` (added in 2.0), which declares
   `CustomIntentMigratedAppIntent` with `intentClassName = "RefreshAllIntent"`.

That conformance makes the App Intent *take over* the SiriKit intent's identity.
The AppIntents metadata extractor then stamps the action with
`introducedVersion = 17.2`, so on iOS 17.0/17.1 the action resolves to the App
Intent, is unavailable, and the working SiriKit intent is shadowed. Users see:

    "Refresh All Apps" is not supported on iPhone

Lowering the metadata version alone (possible by patching the .ipa) makes the
action start, but it then fails at runtime with "an internal error occurred" —
on iOS 17.0.x the App Intent execution path does not complete the refresh.

Fix
---
Drop the migration conformance so the two actions stay independent:

  - iOS < 17.2  -> App Intent unavailable, Shortcuts falls back to the
                   SiriKit `RefreshAllIntent` (pre-2.0 behaviour) and refresh works.
  - iOS >= 17.2 -> App Intent is used, auto-shortcut resolves to it as before.

Shortcuts already created against `RefreshAllIntent` keep working: they now
resolve back to the SiriKit handler instead of the unavailable App Intent.
"""

import pathlib
import sys


INTENT_PATH = pathlib.Path("AltStore/Intents/App Intents/RefreshAllAppsIntent.swift")
SHORTCUTS_PATH = pathlib.Path("AltStore/Intents/App Intents/AppShortcuts.swift")

OLD_DECL = (
    "struct RefreshAllAppsIntent: AppIntent, CustomIntentMigratedAppIntent, "
    "PredictableIntent, ProgressReportingIntent, ForegroundContinuableIntent"
)
NEW_DECL = (
    "struct RefreshAllAppsIntent: AppIntent, "
    "PredictableIntent, ProgressReportingIntent, ForegroundContinuableIntent"
)

OLD_SHORTCUTS_HEAD = """    public static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: RefreshAllAppsIntent(),"""

NEW_SHORTCUTS_HEAD = """    public static var appShortcuts: [AppShortcut] {
        // Below iOS 17.2 the App Intent is not available, so don't register an
        // auto-shortcut tile that would immediately be reported as unsupported.
        // Shortcuts falls back to the legacy SiriKit `RefreshAllIntent` there.
        guard #available(iOS 17.2, *) else { return [] }

        return [
        AppShortcut(intent: RefreshAllAppsIntent(),"""

OLD_SHORTCUTS_TAIL = """                    shortTitle: "Refresh All Apps",
                    systemImageName: "arrow.triangle.2.circlepath")
    }"""

NEW_SHORTCUTS_TAIL = """                    shortTitle: "Refresh All Apps",
                    systemImageName: "arrow.triangle.2.circlepath")]
    }"""


def fail(message):
    print("PATCH FAILED: " + message, file=sys.stderr)
    sys.exit(1)


def main():
    for path in (INTENT_PATH, SHORTCUTS_PATH):
        if not path.exists():
            fail(f"{path} not found - upstream layout changed?")

    source = INTENT_PATH.read_text(encoding="utf-8")

    if OLD_DECL not in source:
        # Already patched, or upstream renamed things - either way, verify the
        # dangerous tokens are gone rather than blindly continuing.
        if "CustomIntentMigratedAppIntent" in source or "intentClassName" in source:
            fail("declaration not found but CustomIntentMigratedAppIntent/intentClassName still present")
        print("RefreshAllAppsIntent.swift: already patched")
    else:
        source = source.replace(OLD_DECL, NEW_DECL)

        before = source
        source = source.replace('    static let intentClassName = "RefreshAllIntent"\n\n', "")
        source = source.replace('    static let intentClassName = "RefreshAllIntent"\n', "")
        if source == before:
            fail("intentClassName not found after replacing the declaration")

        INTENT_PATH.write_text(source, encoding="utf-8")
        print("RefreshAllAppsIntent.swift: dropped CustomIntentMigratedAppIntent + intentClassName")

    shortcuts = SHORTCUTS_PATH.read_text(encoding="utf-8")

    if "guard #available(iOS 17.2, *) else { return [] }" in shortcuts:
        print("AppShortcuts.swift: already patched")
    else:
        if OLD_SHORTCUTS_HEAD not in shortcuts:
            fail("AppShortcuts.swift: appShortcuts head not found")
        if OLD_SHORTCUTS_TAIL not in shortcuts:
            fail("AppShortcuts.swift: appShortcuts tail not found")

        shortcuts = shortcuts.replace(OLD_SHORTCUTS_HEAD, NEW_SHORTCUTS_HEAD)
        shortcuts = shortcuts.replace(OLD_SHORTCUTS_TAIL, NEW_SHORTCUTS_TAIL)
        SHORTCUTS_PATH.write_text(shortcuts, encoding="utf-8")
        print("AppShortcuts.swift: appShortcuts returns [] below iOS 17.2")

    # Final assertion: the shadowing tokens must be gone.
    final = INTENT_PATH.read_text(encoding="utf-8")
    if "CustomIntentMigratedAppIntent" in final or "intentClassName" in final:
        fail("shadowing tokens still present after patching")
    print("OK: App Intent no longer claims the legacy SiriKit intent.")


if __name__ == "__main__":
    main()
