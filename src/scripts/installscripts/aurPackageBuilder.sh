#!/bin/bash
# aurPackageBuilder.sh
# Usage: aurPackageBuilder.sh <pkg1> <pkg2> ...
# This script fetches PKGBUILD and builds AUR packages as non-root user.

if ! command -v yay &> /dev/null; then
    echo "yay AUR helper is not installed. Aborting." >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    echo "No packages specified. Usage: $0 <pkg1> <pkg2> ..." >&2
    exit 2
fi

export ERROR_COUNT=0
export YAY_BUILDDIR="/tmp/yay-bin"
mkdir -p "$YAY_BUILDDIR"

declare -a FAILED_PACKAGES=()
declare -a SUCCESS_PACKAGES=()

for pkg in "$@"; do
    echo -e "\n==> Preparing $pkg from AUR..."
    progress_char1="*"
    PKGDIR="$YAY_BUILDDIR"
    mkdir -p "$PKGDIR"
    (cd "$PKGDIR" && yay -G "$pkg" 2>&1 | while IFS= read -r line; do
        printf "%s" "$progress_char1"
        if [[ "$line" == *"error"* || "$line" == *"failed"* ]]; then
            echo -e "\n$line" >&2
        fi
    done)
    if [ ! -f "$PKGDIR/$pkg/PKGBUILD" ]; then
        echo -e "[ERROR] Failed to fetch PKGBUILD for $pkg" >&2
        FAILED_PACKAGES+=("$pkg")
        ERROR_COUNT=$((ERROR_COUNT + 1))
        continue
    fi
    (cd "$PKGDIR" && makepkg --dir "$PKGDIR/$pkg" --noconfirm --needed --skippgpcheck 2>&1 | while IFS= read -r line; do
        printf "%s" "$progress_char1"
        if [[ "$line" == *"error"* || "$line" == *"failed"* ]]; then
            echo -e "\n$line" >&2
        fi
    done)
    status=${PIPESTATUS[0]}
    PKGFILE=$(ls "$PKGDIR/$pkg"/*.pkg.tar.* "$PKGDIR"/*.pkg.tar.* 2>/dev/null | head -n1)
    if [ $status -ne 0 ] || [ ! -f "$PKGFILE" ]; then
        echo -e "[ERROR] Failed to build $pkg" >&2
        FAILED_PACKAGES+=("$pkg")
        ERROR_COUNT=$((ERROR_COUNT + 1))
        continue
    fi
    echo -e "[OK] $pkg built successfully."
    SUCCESS_PACKAGES+=("$pkg")
done

echo -e "\nAll requested AUR packages processed with Errors encountered: $ERROR_COUNT"
echo "BUILD_SUMMARY_START"
echo "SUCCESS_COUNT:${#SUCCESS_PACKAGES[@]}"
echo "FAILED_COUNT:${#FAILED_PACKAGES[@]}"

if [ ${#SUCCESS_PACKAGES[@]} -gt 0 ]; then
    echo "SUCCESS_PACKAGES:${SUCCESS_PACKAGES[*]}"
fi

if [ ${#FAILED_PACKAGES[@]} -gt 0 ]; then
    echo "FAILED_PACKAGES:${FAILED_PACKAGES[*]}"
fi
echo "BUILD_SUMMARY_END"

if [ $ERROR_COUNT -gt 0 ]; then
    exit 1
fi

exit 0

