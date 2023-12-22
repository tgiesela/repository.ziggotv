# plugin.video.ziggotg
plugin to watch Ziggo-NL in kodi

## Structure
The main project folder is named `repository.ziggotv` which will be installed as a repository in Kodi.
Subfolder `plugin.video.ziggotv` contains the actual plugin. In pycharm I set this as the source folder for development.
All folders starting with `script.module.` are copies of the libraries used  by `aiohttp`.

## Features
First of all a subscription to Ziggo is required. Without that the plugin will not work.
You can watch the channels available in your subscription.
Also, some folders with Series and Movies are created. Items not available will be marked red.
Finally a EPG is presented from which you can select a event in the past or simply switch to a channel.

## Options
By default, the plugin will only process license requests. If you want, all requests sent by Input Stream Adaptive (ISA) can be sent to the proxy.
This allows the plugin to insert the streaming token, which is required for streaming a channel. The streaming token will be refreshed every minute.
If you do not use the proxy, the streaming token remains unchanged. Eventually the streaming may stop.



