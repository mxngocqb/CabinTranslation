#!/usr/bin/env bash
# Install CabinTranslation on an Android device (Qualcomm QCS8550 tested) and put the models in place.
#   bash install.sh [adb-serial] [path-to-models-on-host]
# Models are copied to /sdcard/CabinTranslation/models. If they already sit in /data/local/tmp/cabin/models
# on the device (edge/tools/make_device_bundle.py --push), they are copied on-device instead.
set -euo pipefail
cd "$(dirname "$0")"
S=${1:-10.5.14.32:5555}; A="adb -s $S"
APK=${APK:-dist/CabinTranslation.apk}
$A install -r -g "$APK"
$A shell appops set vn.cabin.translate MANAGE_EXTERNAL_STORAGE allow
# meeting-tablet stand: the accelerometer reports the wrong orientation -> pin the natural landscape rotation
$A shell settings put system accelerometer_rotation 0
$A shell settings put system user_rotation 0
$A shell mkdir -p /sdcard/CabinTranslation/models
if $A shell ls /data/local/tmp/cabin/models/gemma-4-E2B-it-gpu.litertlm >/dev/null 2>&1; then
  $A shell cp -r /data/local/tmp/cabin/models/. /sdcard/CabinTranslation/models/
elif [ -n "${2:-}" ]; then
  $A push "$2/." /sdcard/CabinTranslation/models/
fi
$A shell am start -n vn.cabin.translate/.MainActivity
echo "Installed. First start loads the models (~20 s)."
