import sys

import xbmc
import xbmcaddon
import xbmcgui
from xbmcgui import Action, Control

from resources.lib.ProgramEvent import ProgramEventGrid
from resources.lib.globals import G
from resources.lib.webcalls import LoginSession


class EpgWindowXml(xbmcgui.WindowXML):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, args[0], args[1])

    def __init__(self, xmlFilename: str, scriptPath: str, my_addon: xbmcaddon.Addon):
        super().__init__(xmlFilename, scriptPath)
        self.initDone = False
        self.grid = None
        self.currentFocusedNode = None
        self.epgDatetime = None  # date in local timezone
        self.epgEndDatetime = None  # last date in local timezone
        self.addon = my_addon
        self.session = LoginSession(my_addon)
        self.channels = self.session.get_channels()
        self.mediafolder = self.addon.getAddonInfo('path') + 'resources/skins/Default/media/'

    # Private methods

    # Callbacks

    def show(self) -> None:
        super().show()

    def onControl(self, control: Control) -> None:
        self.grid.onControl(control)

    def onFocus(self, controlId: int) -> None:
        self.grid.onFocus(controlId)

    def onClick(self, controlId: int) -> None:
        self.grid.onClick(controlId)

    def onInit(self):
        if self.initDone:
            return
        self.grid = ProgramEventGrid(self,
                                     channels=self.channels,
                                     mediaFolder=self.mediafolder,
                                     session=self.session,
                                     addon=self.addon)
        self.grid.build()
        self.grid.show()
        self.initDone = True

    def onAction(self, action: Action) -> None:
        if action.getId() == G.ACTION_STOP:
            self.close()
        self.grid.onAction(action)


REMOTE_DEBUG = False
if __name__ == '__main__':
    # if REMOTE_DEBUG:
    #     try:
    #         sys.path.append('E:\Eclipse IDE\eclipse\plugins\org.python.pydev.core_10.2.1.202307021217\pysrc')
    #         import pydevd
    #
    #         pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
    #     except:
    #         sys.stderr.write("Error: " + "You must add org.python.pydev.debug.pysrc to your PYTHONPATH")
    #         sys.stderr.write("Error: " + "Debug not available")
    addonid = sys.argv[1]
    addon = xbmcaddon.Addon(addonid)
    xbmc.executebuiltin('Dialog.Close(busydialog)', True)
    window = EpgWindowXml('screen-epg.xml', addon.getAddonInfo('path'), addon)
    window.doModal()
