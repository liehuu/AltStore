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
import re
import sys


PACKAGE = pathlib.Path("Dependencies/AltSign/Package.swift")

# Indentation differs between upstream branches, so match on the glob itself.
GLOB = re.compile(r'^([ \t]*)\.headerSearchPath\("AltSign/\*\*"\),', re.MULTILINE)
PATHS = [
    "AltSign",
    "AltSign/Model",
    "AltSign/Model/Apple API",
    "AltSign/include",
    "AltSign/include/AltSign",
]


def _expand(match):
    indent = match.group(1)
    return "\n".join(f'{indent}.headerSearchPath("{path}"),' for path in PATHS)


def main():
    if not PACKAGE.exists():
        print("PATCH FAILED: Dependencies/AltSign not checked out (submodule missing?)", file=sys.stderr)
        return 1

    source = PACKAGE.read_text(encoding="utf-8")

    if "AltSign/**" not in source:
        if "AltSign/Model/Apple API" in source:
            print("Package.swift: already patched")
        else:
            print("Package.swift: glob not found (upstream may have fixed it)")
        return 0

    patched, count = GLOB.subn(_expand, source)
    if count == 0:
        print("PATCH FAILED: found 'AltSign/**' but could not match the call site", file=sys.stderr)
        return 1

    PACKAGE.write_text(patched, encoding="utf-8")
    print(f"Package.swift: replaced {count} 'AltSign/**' glob(s) with explicit header search paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
