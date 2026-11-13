#!/bin/bash
# pacmanPackageInstaller.sh
# Usage: pkexec pacmanPackageInstaller.sh [-y|--yankrepos] <pkg1> <pkg2> ...

SYNC_REPOS=false
PACKAGES=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yankrepos)
            SYNC_REPOS=true
            shift
            ;;
        *)
            PACKAGES+=("$1")
            shift
            ;;
    esac
done

if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root. Use: pkexec $0 <packages>" >&2
    exit 1
fi

if ! command -v pacman &> /dev/null; then
    echo "pacman is not available. This script requires Arch Linux or pacman-based system." >&2
    exit 1
fi

if [ "${#PACKAGES[@]}" -eq 0 ]; then
    echo "No packages specified. Usage: pkexec $0 [-y|--yankrepos] <pkg1> <pkg2> ..." >&2
    exit 1
fi

export TOTAL_PACKAGES=${#PACKAGES[@]}
export FAILED_PACKAGES=""
export SUCCESS_COUNT=0

echo "==> Starting pacman package installation for $TOTAL_PACKAGES packages..."

if [ "$SYNC_REPOS" = true ]; then
    echo "==> Syncing package databases..."
    if ! pacman -Sy &>/dev/null; then
        echo "[ERROR] Failed to sync package databases. Check pacman status." >&2
        exit 1
    fi
fi

progress_char="*"
package_index=1

for pkg in "${PACKAGES[@]}"; do
    echo -e "\n==> Installing package $package_index/$TOTAL_PACKAGES: $pkg"
    if pacman -S --noconfirm --needed "$pkg" 2>&1 | while IFS= read -r line; do
        printf "%s" "$progress_char"
        if [[ "$line" == *"error"* || "$line" == *"failed"* || "$line" == *"not found"* ]]; then
            echo -e "\n$line" >&2
        fi
    done; then
        echo -e "\n[OK] $pkg installed successfully."
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo -e "\n[ERROR] Failed to install $pkg" >&2
        FAILED_PACKAGES="${FAILED_PACKAGES}${package_index}"
    fi
    package_index=$((package_index + 1))
done

if [ -z "$FAILED_PACKAGES" ]; then
    echo -e "\n==> All $TOTAL_PACKAGES pacman packages installed successfully!"
    exit 0
else
    echo -e "\n==> Partial or complete failure ($SUCCESS_COUNT/$TOTAL_PACKAGES installed)."
    exit 1
fi

