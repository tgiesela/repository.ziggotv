# plugin.video.ziggotg
plugin to watch Ziggo-NL in kodi

## Known problems
The proxy is currently only used for license request. In this case the first x-streaming-token 
obtained is used. Refresh of streaming-token should also be possible, but this is not 
working properly. Kodi crashes unexpectedly during the processing (memory access).
The proxy is currently hard-coded disabled in 'build_url' in addon.py.

