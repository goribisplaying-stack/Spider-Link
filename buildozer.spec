[app]
title = Spider Link
package.name = spiderlink
package.domain = org.spiderlink
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3==3.11,kivy==2.3.0,paho-mqtt,pycryptodome
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25.2.9519653
android.sdk_path = /root/android-sdk
android.ndk_path = /root/android-sdk/ndk/25.2.9519653
android.archs = arm64-v8a
android.allow_backup = True
android.debug_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
