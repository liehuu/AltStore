#!/usr/bin/env python3
"""Work around SwiftPM no longer expanding `**` in headerSearchPath.

Runs inside a checkout of altstoreio/AltStore (after submodules are fetched).

`Dependencies/AltSign/Package.swift` declares, for the CAltSign target:

    .headerSearchPath("AltSign/**")

Older SwiftPM expanded the `**` glob; current SwiftPM passes the literal string
through to clang, which does not expand it either. The result is that
`AltSign/Model/Apple API` (note the space) never reaches the header search
path, and the build dies with:

    Dependencies/AltSign/AltSign/Signing/ALTSigner.mm:10:9:
        fatal error: 'ALTAppID.h' file not found
    Dependencies/AltSign/AltSign/Model/ALTApplication.h:16:9:
        fatal error: 'ALTDevice.h' file not found

Replace the glob with the concrete directories that actually hold headers.
"""

import pathlib
import sys


PACKAGE = pathlib.Path("Dependencies/AltSign/Package.swift")

OLD = '                .headerSearchPath("AltSign/**"),'
NEW = (
    '                .headerSearchPath("AltSign"),\n'
    '                .headerSearchPath("AltSign/Model"),\n'
    '                .headerSearchPath("AltSign/Model/Apple API"),\n'
    '                .headerSearchPath("AltSign/include"),\n'
    '                .headerSearchPath("AltSign/include/AltSign"),'
)


def main():
    if not PACKAGE.exists():
        print("PATCH FAILED: Dependencies/AltSign not checked out (submodule missing?)", file=sys.stderr)
        return 1

    source = PACKAGE.read_text(encoding="utf-8")

    if NEW in source:
        print("Package.swift: already patched")
        return 0

    if OLD not in source:
        if "AltSign/**" in source:
            print("PATCH FAILED: 'AltSign/**' present but indentation changed - update the pattern", file=sys.stderr)
        else:
            print("Package.swift: glob not found (upstream may have fixed it)")
        return 0 if "AltSign/**" not in source else 1

    PACKAGE.write_text(source.replace(OLD, NEW), encoding="utf-8")
    print("Package.swift: replaced 'AltSign/**' glob with explicit header search paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
