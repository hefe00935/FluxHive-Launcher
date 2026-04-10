version https://git-lfs.github.com/spec/v1
oid sha256:9fa49a0417a0a2ac799df4e820d4391ba43a3624c942e42c5f55e4792bed12d6
size 61

pyinstaller --noconfirm --onedir --windowed --name "FluxHive" --contents-directory "internal_data" --add-data "config;config" --add-data "feather;feather" --add-data "feather-loader;feather-loader" --add-data "game_data;game_data" --add-data "jdk-21;jdk-21" --add-data "libraries;libraries" --add-data "processedMods;processedMods" --add-data "utils;utils" "main.py"