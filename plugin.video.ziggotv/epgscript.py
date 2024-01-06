import sys

import xbmc
import xbmcaddon
import xbmcgui
from xbmcgui import Action, Control

from resources.lib.Channel import ChannelList
from resources.lib.ProgramEvent import ProgramEventGrid
from resources.lib.globals import G
from resources.lib.utils import ProxyHelper
from resources.lib.webcalls import LoginSession


class EpgWindowXml(xbmcgui.WindowXML):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, args[0], args[1])

    def __init__(self, xmlFilename: str, scriptPath: str, my_addon: xbmcaddon.Addon):
        super().__init__(xmlFilename, scriptPath)
        self.initDone = False
        self.grid: ProgramEventGrid = None
        self.currentFocusedNode = None
        self.epgDatetime = None  # date in local timezone
        self.epgEndDatetime = None  # last date in local timezone
        self.addon = my_addon
        self.helper = ProxyHelper(my_addon)
        self.channels = None
        self.__initialize_session()
        self.channelList = ChannelList(self.channels, self.entitlements)
        self.channelList.entitledOnly = my_addon.getSettingBool('allowed-channels-only')
        self.channelList.applyFilter()
        self.mediaFolder = self.addon.getAddonInfo('path') + 'resources/skins/Default/media/'

    # Private methods
    def __initialize_session(self):
        self.helper.dynamicCall(LoginSession.refresh_channels)
        self.helper.dynamicCall(LoginSession.refresh_entitlements)
        self.channels = self.helper.dynamicCall(LoginSession.get_channels)
        self.entitlements = self.helper.dynamicCall(LoginSession.get_entitlements)

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
                                     channels=self.channelList,
                                     mediaFolder=self.mediaFolder,
                                     addon=self.addon)
        self.grid.build()
        self.grid.show()
        self.initDone = True

    def onAction(self, action: Action) -> None:
        if action.getId() == G.ACTION_STOP:
            self.close()
        if self.grid.isAtFirstRow():
            #  Set control to header to select date or back to grid
            if action.getId() == xbmcgui.ACTION_MOVE_UP:
                self.setFocusId(1010)
            elif (action.getId() == xbmcgui.ACTION_MOVE_DOWN and
                  self.getFocusId() in [1016, 1017]):
                self.grid.setFocus()
            elif (action.getId() in [xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_MOVE_RIGHT] and
                  self.getFocusId() in [1016, 1017]):
                pass  # Action handled via .xml <onleft> <onright>
            else:
                self.grid.onAction(action)
        else:
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
