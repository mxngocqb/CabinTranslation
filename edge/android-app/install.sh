#!/usr/bin/env bash
# Install the CabinTranslation Android app and put the models in place (tested: QCS8550 tablet, Galaxy S25 Ultra).
#   bash edge/android-app/install.sh [adb-serial]        (default: the only connected adb device)
# Models go to /sdcard/CabinTranslation/models. If they are already in /data/local/tmp/cabin/models on the device
# (edge/tools/make_device_bundle.py --push), they are copied on the device; otherwise they are pushed from the host
# (repo models/ + ~/edge/models/gemma-4-E2B-it-gpu.litertlm, ~2.9 GB). Files already present are skipped.
set -euo pipefail
cd "$(dirname "$0")"
S=${1:-$(adb devices | awk 'NR>1 && $2=="device" {print $1}' | head -1)}
[ -n "$S" ] || { echo "no adb device connected"; exit 1; }
echo "device: $S ($(adb -s "$S" shell getprop ro.product.model | tr -d '\r'), SoC $(adb -s "$S" shell getprop ro.soc.model | tr -d '\r'))"
A="adb -s $S"
APK=${APK:-dist/CabinTranslation.apk}
$A install -r -g "$APK"
$A shell appops set vn.cabin.translate MANAGE_EXTERNAL_STORAGE allow
$A shell mkdir -p /sdcard/CabinTranslation/models
if $A shell ls /data/local/tmp/cabin/models/gemma-4-E2B-it-gpu.litertlm >/dev/null 2>&1; then
  $A shell cp -r /data/local/tmp/cabin/models/. /sdcard/CabinTranslation/models/
else
  ( cd ../.. && python edge/tools/make_device_bundle.py --target android --serial "$S" --push --models-only \
      --models-dir /sdcard/CabinTranslation/models )
fi
$A shell am force-stop vn.cabin.translate
$A shell am start -n vn.cabin.translate/.MainActivity
echo "Installed. First start loads the models (~20-25 s)."
