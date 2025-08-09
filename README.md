# E2iPlayer Plugin for Enigma2 (Python 3)
<img src="https://github.com/oe-mirrors/e2iplayer/blob/python3/IPTVPlayer/icons/iptvlogohd.png">

## Github status
[![Build](https://github.com/oe-mirrors/e2iplayer/actions/workflows/buildbot.yml/badge.svg)](https://github.com/oe-mirrors/oe-mirrors/e2iplayer/workflows/buildbot.yml)
[![Lint Status](https://github.com/oe-mirrors/e2iplayer/actions/workflows/pylint.yml/badge.svg)](https://github.com/oe-mirrors/e2iplayer/actions)
[![Ruff Status](https://github.com/oe-mirrors/e2iplayer/actions/workflows/ruff.yml/badge.svg)](https://github.com/oe-mirrors/e2iplayer/actions)
[![Build Status](https://github.com/oe-mirrors/e2iplayer/actions/workflows/compile.yml/badge.svg)](https://github.com/oe-mirrors/e2iplayer/actions)
## SonarCloud status
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=oe-mirrors_e2iplayer&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=oe-mirrors_e2iplayer)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=oe-mirrors_e2iplayer&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=oe-mirrors_e2iplayer)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=oe-mirrors_e2iplayer&metric=bugs)](https://sonarcloud.io/summary/new_code?id=oe-mirrors_e2iplayer)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=oe-mirrors_e2iplayer&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=oe-mirrors_e2iplayer)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=oe-mirrors_e2iplayer&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=oe-mirrors_e2iplayer)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=oe-mirrors_e2iplayer&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=oe-mirrors_e2iplayer)


---

### 📦 Overview

The E2iPlayer Enigma2 (E2) Plugin is a platform that offers various livestreams and add-ons from all over the world it
includes Movies, TV series, Catoons, Anime, Music, Sport, Live Streams, Documentries, Science and Content for various languages.

---


### 📜 License [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
This plugin is released under GPLv3. See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.html#license-text) for full details.

---

### 🚀 Features
- 🎥 **YouTube Player Support**
- 🖥️ **Responsive UI**  
  Supports different screen resolutions (Full HD and HD) with custom skins.
- 🔍 **Browse M3U Playlists**
- 📺 **Media Player**
- 📁 **Favorites lists**

---

### 🙏 Credits & Forkinfos
👨‍💻 Author:

- Created by **SamSamSam**

Thanks to SamSamSam for the original version of this program! (https://gitlab.com/e2i/e2iplayer) The original public version from SamSamSam is Closedsource now and only available for acquaintances and family

This is a mirror of https://gitlab.com/zadmario/e2iplayer
with additions from https://gitlab.com/maxbambi/e2iplayer, https://github.com/Blindspot76/e2iPlayer and https://github.com/Belfagor2005/e2player

including Python3 preparations and general optimizations by jbleyel

---

### ⚙️ Requirements
- Enigma2 STB (Dreambox, Vu+, Zgemma, etc.)  
- Active internet connection  
- Python ≥ 3.0

---

### 📂 Installation
To install the plugin manually connect to your enigma2 device via SSH/Telnet, (eg. `ssh root@boxip`), then use Install script for Telnet installation
```bash
wget -q "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/refs/heads/python3/e2iplayer_install.sh" -O - | /bin/sh
```

---

### 📌 Notes

- ⚠️ The plugin **does use external extensions** or complicated dependencies on most images the e2ideps are on the Feeds 

---

### 🧪 Debug & Log
You can activate Logs and choose the path in preferences. If errors or malfunctions occur, please send this file for support.  

```
/hdd/iptv.dbg
/tmp/iptv.dbg
/home/root/logs/iptv.dbg
```

---

### 🤝 Contributing & Contact
For questions or feedback, feel free and please open an issue or contribute with a Pull Request!

Pull requests are very welcome for:
- Feature enhancements
- Translations
- Integration improvements
- Bugfixes
- new Hosts

Please fork the repository, create a feature branch, and submit a Pull Request.

---

### ℹ️ WIKI
See the [Wiki](https://github.com/oe-mirrors/e2iplayer/wiki) for more information
