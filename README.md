# repository.ziggotv
Repository for Ziggo NL.
Developed for educational purposes.

## Features
This repository contains currently only one addon: plugin.video.ziggotv.

## Requirements
You need a Kodi installation with version v20(Nexus) or higher. 
If you want to watch channels in full HD you need a powerful processor. I use a Raspberry Pi 4. On a Raspberry Pi 3B you will have to set full-HD to off in the settings of the plugin.
You can also limit the maximal allowed resolution of the InputStream Adaptive Addon.

## Download and installation
Download repository [here](https://ziggotv.github.io/ziggotv/repository.ziggotv/repository.ziggotv-1.0.0.zip)

Instructions [here](https://ziggotv.github.io)

## development info
The config.json file contains the information used to build the actual repository.
It contains a section called 'locations-devel' which is not used but will be renamed during development.
The 'addons' section contains the locations of the addons which will be included in the repository.
This can be a local folder, zipfile or remote git-repository. See section 'addon-example'.


