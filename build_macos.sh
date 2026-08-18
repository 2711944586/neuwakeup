#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

BUILD_VENV="$PROJECT_ROOT/.build-venv"
BUILD_PYTHON="$BUILD_VENV/bin/python"
DIST_DIRECTORY="$PROJECT_ROOT/dist"
WORK_DIRECTORY="$PROJECT_ROOT/build"
APP_PATH="$DIST_DIRECTORY/NEU-WakeUP.app"
PACKAGE_SUFFIX="${NEU_PACKAGE_SUFFIX:-$(uname -m)}"

if [[ ! -x "$BUILD_PYTHON" ]]; then
    python3 -m venv "$BUILD_VENV"
fi

"$BUILD_PYTHON" -m pip install --upgrade pip
"$BUILD_PYTHON" -m pip install --upgrade -r requirements.txt "pyinstaller>=6.14"

rm -rf "$WORK_DIRECTORY" "$APP_PATH" "$PROJECT_ROOT/NEU-WakeUP.spec"

PYINSTALLER_ARGS=(
    --noconfirm
    --clean
    --onedir
    --windowed
    --name "NEU-WakeUP"
    --osx-bundle-identifier "io.github.neuwakeup.desktop"
    --hidden-import qrcode.image.pil
    --hidden-import PIL.ImageTk
    --distpath "$DIST_DIRECTORY"
    --workpath "$WORK_DIRECTORY"
)

if [[ -n "${MACOS_CODESIGN_IDENTITY:-}" ]]; then
    PYINSTALLER_ARGS+=(--codesign-identity "$MACOS_CODESIGN_IDENTITY")
fi

"$BUILD_PYTHON" -m PyInstaller "${PYINSTALLER_ARGS[@]}" neuwakeup.py

if [[ ! -d "$APP_PATH" ]]; then
    echo "macOS app build failed: $APP_PATH was not created" >&2
    exit 1
fi

APP_EXECUTABLE="$APP_PATH/Contents/MacOS/NEU-WakeUP"
if [[ ! -x "$APP_EXECUTABLE" ]]; then
    echo "macOS app validation failed: $APP_EXECUTABLE is missing" >&2
    exit 1
fi

"$APP_EXECUTABLE" --self-check
"$APP_EXECUTABLE" --version
codesign --verify --deep --strict "$APP_PATH"

ZIP_PATH="$DIST_DIRECTORY/NEU-WakeUP-macos-${PACKAGE_SUFFIX}.zip"
DMG_PATH="$DIST_DIRECTORY/NEU-WakeUP-macos-${PACKAGE_SUFFIX}.dmg"
CHECKSUM_PATH="$DIST_DIRECTORY/NEU-WakeUP-macos-${PACKAGE_SUFFIX}.sha256"
DMG_STAGING="$WORK_DIRECTORY/dmg"

create_packages() {
    rm -f "$ZIP_PATH" "$DMG_PATH" "$CHECKSUM_PATH"
    rm -rf "$DMG_STAGING"

    ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
    mkdir -p "$DMG_STAGING"
    ditto "$APP_PATH" "$DMG_STAGING/NEU-WakeUP.app"
    ln -s /Applications "$DMG_STAGING/Applications"
    hdiutil create -volname "NEU WakeUP" -srcfolder "$DMG_STAGING" -ov -format UDZO "$DMG_PATH" >/dev/null
}

create_packages

if [[ -n "${APPLE_ID:-}${APPLE_TEAM_ID:-}${APPLE_APP_PASSWORD:-}" ]]; then
    : "${MACOS_CODESIGN_IDENTITY:?MACOS_CODESIGN_IDENTITY is required for notarization}"
    : "${APPLE_ID:?APPLE_ID is required for notarization}"
    : "${APPLE_TEAM_ID:?APPLE_TEAM_ID is required for notarization}"
    : "${APPLE_APP_PASSWORD:?APPLE_APP_PASSWORD is required for notarization}"

    xcrun notarytool submit "$ZIP_PATH" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APPLE_APP_PASSWORD" \
        --wait
    xcrun stapler staple "$APP_PATH"
    create_packages
    xcrun notarytool submit "$DMG_PATH" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APPLE_APP_PASSWORD" \
        --wait
    xcrun stapler staple "$DMG_PATH"
    spctl --assess --type execute --verbose=4 "$APP_PATH"
fi

(
    cd "$DIST_DIRECTORY"
    shasum -a 256 "$(basename "$ZIP_PATH")" "$(basename "$DMG_PATH")"
) > "$CHECKSUM_PATH"

echo "构建完成："
echo "  $APP_PATH"
echo "  $ZIP_PATH"
echo "  $DMG_PATH"
echo "  $CHECKSUM_PATH"
