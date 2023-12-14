import datetime
import os
import sys
from typing import List

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from xbmcgui import Action, Control

from resources.lib import utils
from resources.lib.Channel import Channel
from resources.lib.LinkedList import LinkedList, Node
from resources.lib.ProgramEvent import ProgramEvent, ProgramEventGrid
from resources.lib.events import ChannelGuide
from resources.lib.globals import G
from resources.lib.webcalls import LoginSession


class EpgWindowXml(xbmcgui.WindowXML):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, args[0], args[1])

    def __init__(self, xmlFilename: str, scriptPath: str, addon: xbmcaddon.Addon):
        super().__init__(xmlFilename, scriptPath)
        self.grid = None
        self.currentFocusedNode = None
        self.selectedevent = 0
        self.channelrow = None
        self.epgDatetime = None  # date in local timezone
        self.epgEndDatetime = None  # last date in local timezone
        self.entitlementlist = None
        self.selectedrow = 0
        self.listctrl: xbmcgui.ControlList = None
        self.addon = addon
        self.session = LoginSession(addon)
        self.channels = self.session.get_channels()
        self.mediafolder = self.addon.getAddonInfo('path') + 'resources/skins/Default/media/'

    # Private methods
    def __getListItem(self, channel: Channel):
        li = xbmcgui.ListItem(label="{0}. {1}".format(channel.logicalChannelNumber, channel.name))
        tag: xbmc.InfoTagVideo = li.getVideoInfoTag()
        tag.setTitle("{0}. {1}".format(channel.logicalChannelNumber, channel.name))
        tag.setSetId(channel.logicalChannelNumber)
        tag.setMediaType('video')
        tag.setUniqueIDs({'ziggochannelid': channel.id})
        li.setProperty('IsPlayable', 'true')
        li.setMimeType('application/dash+xml')
        li.setContentLookup(False)
        tag.setMediaType('video')
        subscribed = False
        for linearProduct in channel.linearProducts:
            if linearProduct in self.entitlementlist:
                subscribed = True

        thumbname = xbmc.getCacheThumbName(channel.logo['focused'])
        thumbfile = xbmcvfs.translatePath('special://thumbnails/' + thumbname[0:1] + '/' + thumbname)
        if os.path.exists(thumbfile):
            os.remove(thumbfile)
        if len(channel.imageStream) > 0:
            thumbname = xbmc.getCacheThumbName(channel.imageStream['full'])
            thumbfile = (
                xbmcvfs.translatePath(
                    'special://thumbnails/' + thumbname[0:1] + '/' + thumbname.split('.')[0] + '.jpg'))
            if os.path.exists(thumbfile):
                os.remove(thumbfile)
            li.setArt({'icon': channel.logo['focused'],
                       'thumb': channel.logo['focused'],
                       'poster': channel.imageStream['full']})
        else:
            li.setArt({'icon': channel.logo['focused'],
                       'thumb': channel.logo['focused']})
        # set the list item to playable
        li.setProperty('IsPlayable', 'true')

        title = tag.getTitle()
        tag.setSortTitle(title)
        tag.setPlot('')
        tag.setPlotOutline('')

        if not subscribed:
            li.setProperty('IsPlayable', 'false')
        if channel.locators['Default'] is None:
            li.setProperty('IsPlayable', 'false')

        return li

    def __setEntitlements(self):
        entitlements = self.session.get_entitlements()["entitlements"]
        self.entitlementlist = []
        i = 0
        while i < len(entitlements):
            self.entitlementlist.append(entitlements[i]["id"])
            i += 1

    def __shiftWindow(self, leftorright):
        self.listctrl: xbmcgui.ControlList = self.getControl(1200)  # ControlList channels

        guide = ChannelGuide(self.session)
        if leftorright == -1:
            self.__shiftEpgWindow(-90)  # 90 minutes
        else:
            self.__shiftEpgWindow(90)  # 90 minutes
        if guide.windowAvailable(
                self.epgDatetime.astimezone(datetime.timezone.utc)
                , self.epgEndDatetime.astimezone(datetime.timezone.utc)):
            pass
        else:
            if leftorright == -1:
                guide.obtainPreviousEvents()
            else:
                guide.obtainNextEvents()

        limit = 20
        cnt = 0
        #  Destroy current events
        for row in self.channelrow:
            evtlist: LinkedList = row
            node = evtlist.head
            while node is not None:
                program: ProgramEvent = node.data
                self.removeControl(program.button)
                node = node.next
            cnt += 1

        self.channelrow = []
        for channel in self.channels:
            channel.events = guide.getEvents(channel.id)
            cnt += 1
            if cnt <= limit:
                self.channelrow.append(self.__createProgramRow(channel, cnt - 1))
        evtlist: LinkedList = self.channelrow[0]
        firstProgram: ProgramEvent = evtlist.head.data
        firstProgram.setFocus()
        self.currentFocusedNode = evtlist.head
        self.selectedrow = 0

    def __createProgramRow(self, channel: Channel, row: int) -> LinkedList:
        evts = channel.events.getEventsInWindow(self.epgDatetime
                                                , self.epgDatetime
                                                + datetime.timedelta(hours=2))
        ctrlevts = LinkedList()
        for evt in evts:
            ctrl = ProgramEvent(self, row, evt, self.epgDatetime, self.epgEndDatetime, self.mediafolder)
            if ctrl is not None:
                ctrlevts.insertAtEnd(ctrl)
        return ctrlevts

    def __findProgramEvent(self, controlId):
        i = 0
        while i < len(self.channelrow):
            proglist = self.channelrow[i]
            node: Node = proglist.head
            while node is not None:
                program: ProgramEvent = node.data
                if program.controlId == controlId:
                    return i, node
                else:
                    node = node.next
            i += 1
        return -1, None

    def play(self, program: ProgramEvent):
        if program.programEvent.startTime > utils.DatetimeHelper.unixDatetime(datetime.datetime.now()):
            print('Cannot start playing, starttime in future')
            return
        print('Start playing: {0}'.format(program.programEvent.title))

    def show(self) -> None:
        super().show()

    def onControl(self, control: Control) -> None:
        print('onControl(): {0}'.format(control.getId()))

    def onFocus(self, controlId: int) -> None:
        self.grid.onFocus(controlId)

    def onClick(self, controlId: int) -> None:
        self.grid.onClick(controlId)
        # print('onClick(): controlId {0}'.format(controlId))
        # row, node = self.__findProgramEvent(controlId)
        # if node is None or row == -1:
        #     return
        # self.currentFocusedNode = node
        # self.selectedrow = row
        # self.play(node.data)

    def onInit(self):
        self.__setEntitlements()
        self.grid = ProgramEventGrid(self
                                     , channels=self.channels
                                     , mediaFolder=self.mediafolder
                                     , session=self.session)
        self.grid.build()
        self.grid.show()

    def onInit_old(self) -> None:
        self.listctrl: xbmcgui.ControlList = self.getControl(1200)  # ControlList channels
        self.listctrl.setVisible(True)
        self.__setEntitlements()
        self.__getFirstEpgDate()

        listitems = []
        for channel in self.channels:
            if channel.isHidden:
                continue
            listitem = self.__getListItem(channel)
            listitems.append(listitem)

        self.listctrl.addItems(listitems)
        self.setFocus(self.listctrl)

        guide = ChannelGuide(self.session)
        guide.obtainEvents()

        limit = 20
        cnt = 0
        self.channelrow = []
        for channel in self.channels:
            channel.events = guide.getEvents(channel.id)
            cnt += 1
            if cnt <= limit:
                self.channelrow.append(self.__createProgramRow(channel, cnt - 1))
        list: LinkedList = self.channelrow[0]
        firstProgram: ProgramEvent = list.head.data
        firstProgram.setFocus()
        self.currentFocusedNode = list.head
        self.selectedrow = 0
        print('OnInit done')

    def onAction(self, action: Action) -> None:
        if action.getId() == G.ACTION_STOP:
            self.close()
            # del self
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
    window = EpgWindowXml('screen-epg.xml', addon.getAddonInfo('path'), addon)
    window.doModal()
