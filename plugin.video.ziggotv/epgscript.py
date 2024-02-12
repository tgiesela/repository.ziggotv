"""
Script run from plugin.video.ziggotv when 'epg' is chosen. It creates a new
window to present the EPG.
"""
import sys

import xbmc
import xbmcaddon
import xbmcgui
from xbmcgui import Action, Control

from resources.lib.channel import ChannelList
from resources.lib.programevent import ProgramEventGrid
from resources.lib.utils import ProxyHelper, SharedProperties
from resources.lib.webcalls import LoginSession


class EpgWindowXml(xbmcgui.WindowXML):
    # pylint: disable=too-many-instance-attributes
    """
    Class representing Epg Window defined in screen-epg.xml.
    Ids used in this file correspond to the .xml file
    """

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
        self.channelList.apply_filter()
        self.mediaFolder = self.addon.getAddonInfo('path') + 'resources/skins/Default/media/'

    # Private methods
    def __initialize_session(self):
        self.channels = self.helper.dynamic_call(LoginSession.get_channels)
        self.entitlements = self.helper.dynamic_call(LoginSession.get_entitlements)

    # Callbacks

    # pylint: disable=useless-parent-delegation
    def show(self) -> None:
        super().show()

    # pylint: enable=useless-parent-delegation

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
        if action.getId() == xbmcgui.ACTION_STOP:
            self.grid.onAction(action)
            self.close()
            return

        if action.getId() == xbmcgui.ACTION_PREVIOUS_MENU or action.getId() == xbmcgui.ACTION_NAV_BACK:  # Esc
            self.grid.onAction(action)
            self.close()
            return

        if self.grid.is_at_first_row():
            #  Set control to header to select date or back to grid
            if action.getId() == xbmcgui.ACTION_MOVE_UP:
                self.setFocusId(1010)
            elif (action.getId() == xbmcgui.ACTION_MOVE_DOWN and
                  self.getFocusId() in [1016, 1017, 1018, 1020]):
                self.grid.set_focus()
            elif (action.getId() in [xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_MOVE_RIGHT] and
                  self.getFocusId() in [1016, 1017, 1018, 1020]):
                pass  # Action handled via .xml <onleft> <onright>
            else:
                self.grid.onAction(action)
        else:
            self.grid.onAction(action)


def check_service():
    """
    Function to check if the Ziggo service is running
    @return:
    """
    home: SharedProperties = SharedProperties(addon=addon)
    if home.is_service_active():
        return
    secondsToWait = 30
    timeWaiting = 0
    interval = 0.5
    dlg = xbmcgui.DialogProgress()
    dlg.create('ZiggoTV', 'Waiting for service to start...')
    while (not home.is_service_active() and
           timeWaiting < secondsToWait and not home.is_service_active() and not dlg.iscanceled()):
        xbmc.sleep(int(interval * 1000))
        timeWaiting += interval
        dlg.update(int(timeWaiting / secondsToWait * 100), 'Waiting for service to start...')
    dlg.close()
    if not home.is_service_active():
        raise RuntimeError('Service did not start in time')


REMOTE_DEBUG = False
if __name__ == '__main__':
    # if REMOTE_DEBUG:
    #     try:
    #         sys.path.append('E:\Eclipse IDE\eclipse\plugins\org.python.pydev.core_10.2.1.202307021217\pysrc')
    #         import pydevd
    #         pydevd.settrace('localhost', stdoutToServer=True, stderrToServer=True)
    #     except:
    #         sys.stderr.write("Error: " + "You must add org.python.pydev.debug.pysrc to your PYTHONPATH")
    #         sys.stderr.write("Error: " + "Debug not available")
    addonId = sys.argv[1]
    addon = xbmcaddon.Addon(addonId)
    xbmc.executebuiltin('Dialog.Close(busydialog)', True)
    check_service()
    window = EpgWindowXml('screen-epg.xml', addon.getAddonInfo('path'), addon)
    window.doModal()
