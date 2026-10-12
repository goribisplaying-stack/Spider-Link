[app]
title = Spider Link
package.name = spiderlink
package.domain = org.spiderlink
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3==3.12.7,hostpython3==3.12.7,kivy==2.3.0,paho-mqtt,pycryptodome
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 33
android.minapi = 26
android.ndk = 27b
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/27.3.13750724
android.archs = arm64-v8a
android.allow_backup = True
android.debug_artifact = apk
android.add_compile_flags = -Wno-incompatible-function-pointer-types
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
