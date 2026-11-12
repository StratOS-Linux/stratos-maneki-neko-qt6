#!/bin/bash
# flatpakPackageInstaller.sh
# Usage: flatpakPackageInstaller.sh <pkg1> <pkg2> ...

if [ "$#" -eq 0 ]; then
    echo "No packages specified. Usage: $0 <pkg1> <pkg2> ..." >&2
    exit 1
fi

if ! command -v flatpak &> /dev/null; then
    echo "flatpak is not available. Please install flatpak first." >&2
    exit 1
fi

export TOTAL_PACKAGES=$#
export FAILED_PACKAGES=""
export SUCCESS_COUNT=0
export PACKAGES=("$@")

if [ "$EUID" -eq 0 ]; then
    INSTALL_SCOPE="--system"
    SCOPE_DESC="system-wide"
    echo "==> Running with root privileges - installing flatpaks system-wide..."
else
    INSTALL_SCOPE="--user"
    SCOPE_DESC="user-only"
    echo "==> Running as user - installing flatpaks for current user only..."
fi

echo "==> Starting flatpak package installation for $TOTAL_PACKAGES packages ($SCOPE_DESC)..."

progress_char="*"
package_index=1

for pkg in "${PACKAGES[@]}"; do
    echo -e "\n==> Installing package $package_index/$TOTAL_PACKAGES: $pkg ($SCOPE_DESC)"
    if flatpak install flathub $INSTALL_SCOPE --noninteractive --assumeyes "$pkg" 2>&1 | while IFS= read -r line; do
        printf "%s" "$progress_char"
        if [[ "$line" == *"error"* || "$line" == *"failed"* || "$line" == *"not found"* || "$line" == *"Error"* ]]; then
            echo -e "\n$line" >&2
        fi
    done; then
        echo -e "\n[OK] $pkg installed successfully ($SCOPE_DESC)."
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo -e "\n[ERROR] Failed to install $pkg ($SCOPE_DESC)" >&2
        FAILED_PACKAGES="${FAILED_PACKAGES}${package_index}"
    fi
    package_index=$((package_index + 1))
done

if [ -z "$FAILED_PACKAGES" ]; then
    echo -e "\n==> All $TOTAL_PACKAGES flatpak packages installed successfully ($SCOPE_DESC)!"
    exit 0
else
    echo -e "\n==> Partial or complete failure ($SUCCESS_COUNT/$TOTAL_PACKAGES installed)."
    exit 1
fi

