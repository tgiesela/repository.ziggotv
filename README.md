# plugin.video.ziggotv
Kodi plugin to watch Ziggo NL.
Developed for educational purposes.

## Features
First of all a subscription to Ziggo-NL is required. Without that the plugin will not work.
You can watch the channels available in your subscription. Channels are sorted by logical channel number.
An EPG is presented from which you can select an event in the past or simply switch to a channel.
Also, some folders with Series and Movies are created. Items which are not available to you or required a payment will be marked red.

Channels and other items which cannot be played due to missing entitlements will be marked red.

## Requirements
You need a Kodi installation with version v20(Nexus) or higher. 
If you want to watch channels in full HD you need a powerful processor. I use a Raspberry Pi 4. On a Raspberry Pi 3B you will have to set full-HD to off in the settings of the plugin.
You can also limit the maximal allowed resolution of the InputStream Adaptive Addon.

## Options
By default, the plugin proxy will only process license requests. If you want, all requests sent by Input Stream Adaptive (ISA) can be sent to the proxy.
This allows the plugin to insert the streaming token, which is required for streaming a channel. The streaming token will be refreshed every minute.
If you do not use the proxy, the streaming token remains unchanged. Eventually the streaming may stop.

## development info
The project title is `repository.ziggotv` which will be installed as a repository in Kodi.
The folder `plugin.video.ziggotv` contains the actual plugin. In Pycharm I set this as the source folder for development.
I created a version using aiohttp, but finally left that path due to the many dependencies I needed. Although it works, it is no longer maintained, although I decided to keep it  as reference (folder `aiohttp-version`) for future developmenent.
kodiAll folders starting with `script.module.` are copies of the libraries used  by `aiohttp`.


