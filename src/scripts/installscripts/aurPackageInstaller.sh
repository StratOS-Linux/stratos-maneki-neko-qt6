#!/bin/bash
# aurPackageInstaller.sh
# Usage: aurPackageInstaller.sh <pkg1> <pkg2> ...
# This script installs built AUR packages as root using pacman -U.

if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use pkexec)." >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    echo "No packages specified. Usage: $0 <pkg1> <pkg2> ..." >&2
    exit 2
fi

export YAY_BUILDDIR="/tmp/yay-bin"

for pkg in "$@"; do
    PKGDIR="$YAY_BUILDDIR/$pkg"

    if [ -d "$PKGDIR" ]; then
        progress_char2="#"
        echo -e "\n==> Installing $pkg..."
        PKGFILE=$(ls "$PKGDIR"/*.pkg.tar.* "$YAY_BUILDDIR"/*.pkg.tar.* 2>/dev/null | head -n1)
        if [ -f "$PKGFILE" ]; then
            pacman -U --noconfirm "$PKGFILE" 2>&1 | while IFS= read -r line; do
                printf "%s" "$progress_char2"
                if [[ "$line" == *"error"* || "$line" == *"failed"* ]]; then
                    echo -e "\n$line" >&2
                fi
            done
            status=${PIPESTATUS[0]}
            if [ $status -ne 0 ]; then
                echo -e "\n[ERROR] Failed to install $pkg" >&2
                exit $status
            fi
            echo -e "\n[OK] $pkg installed successfully."
        else
            echo -e "\n[ERROR] No built package file found for $pkg!" >&2
            exit 4
        fi
    else
        echo -e "\n[ERROR] Build directory for $pkg not found!" >&2
        exit 3
    fi
done

echo -e "\nAll requested AUR packages installed."
exit 0

