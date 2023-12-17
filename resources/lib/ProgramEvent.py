import datetime
from collections import namedtuple
from typing import List
import typing

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import utils
from resources.lib.Channel import Channel
from resources.lib.UrlTools import UrlTools
from resources.lib.ZiggoPlayer import ZiggoPlayer, VideoHelpers
from resources.lib.events import Event, ChannelGuide
from resources.lib.globals import G
from resources.lib.webcalls import LoginSession

import urllib.parse


class ProgramEventGrid:
    def __init__(self,
                 window: xbmcgui.WindowXML,
                 channels: List[Channel],
                 mediaFolder: str,
                 session: LoginSession,
                 addon: xbmcaddon.Addon):
        self.startWindow = None
        self.endWindow = None
        self.rows: List[ProgramEventRow] = []
        self.channels: List[Channel] = channels
        self.channelsInGrid: List[Channel] = []
        self.mediaFolder = mediaFolder
        self.window = window
        self.__MAXROWS = 20
        self.__firstChannelIndex = 0
        self.__currentRow = 0
        self.__getFirstWindow()
        self.session = session
        self.addon = addon
        self.guide = ChannelGuide(session)
        self.guide.obtainEvents()
        for channel in self.channels:
            channel.events = self.guide.getEvents(channel.id)

    def __setEPGDate(self, date: datetime.datetime):
        # 1011 EPG Date
        lbl: xbmcgui.ControlLabel = self.__getControl(1011)
        lbl.setLabel(date.strftime('%d-%m-%y'))

    def __setEpgTime(self, date: datetime.datetime):
        # 1012-1015 half hour time
        windowDate = date
        lbl: xbmcgui.ControlLabel = self.__getControl(1012)
        lbl.setLabel(windowDate.strftime('%H:%M'))
        windowDate = windowDate + datetime.timedelta(minutes=30)
        lbl: xbmcgui.ControlLabel = self.__getControl(1013)
        lbl.setLabel(windowDate.strftime('%H:%M'))
        windowDate = windowDate + datetime.timedelta(minutes=30)
        lbl: xbmcgui.ControlLabel = self.__getControl(1014)
        lbl.setLabel(windowDate.strftime('%H:%M'))
        windowDate = windowDate + datetime.timedelta(minutes=30)
        lbl: xbmcgui.ControlLabel = self.__getControl(1015)
        lbl.setLabel(windowDate.strftime('%H:%M'))
        windowDate = windowDate + datetime.timedelta(minutes=30)
        self.epgEndDatetime = windowDate

    def __processDates(self):
        self.__setEPGDate(self.startWindow)
        self.__setEpgTime(self.startWindow)
        self.unixstarttime = utils.DatetimeHelper.unixDatetime(self.startWindow)
        self.unixendtime = utils.DatetimeHelper.unixDatetime(self.endWindow)

    def shiftEpgWindow(self, minutes: int):
        self.startWindow = self.startWindow + datetime.timedelta(minutes=minutes)
        self.endWindow = self.startWindow + datetime.timedelta(hours=2)
        self.__processDates()

    def __getFirstWindow(self):
        self.startWindow = datetime.datetime.now()
        if self.startWindow.minute > 30:
            self.startWindow = self.startWindow.replace(minute=30, second=0, microsecond=0)
        else:
            self.startWindow = self.startWindow.replace(minute=0, second=0, microsecond=0)
        self.endWindow = self.startWindow + datetime.timedelta(hours=2)
        self.__processDates()

    def __updateEvents(self):
        self.guide.obtainEventsInWindow(
            self.startWindow.astimezone(datetime.timezone.utc),
            self.endWindow.astimezone(datetime.timezone.utc))
        for channel in self.channels:
            channel.events = self.guide.getEvents(channel.id)

    def __shiftWindow(self, leftorright):
        if leftorright == -1:
            self.shiftEpgWindow(-90)  # 90 minutes
        else:
            self.shiftEpgWindow(90)  # 90 minutes
        self.__updateEvents()
        self.build()
        self.show()

    def __positionTime(self):
        timeBar: xbmcgui.ControlLabel = self.window.getControl(2100)
        currentTime = datetime.datetime.now()
        if currentTime >= self.startWindow or currentTime < self.endWindow:
            pixelsForWindow = 4 * 300  # 4 times half an hour
            pixelsPerMinute = pixelsForWindow / 120
            delta = currentTime - self.startWindow
            deltaMinutes = int(delta.total_seconds() / 60)
            timeBar.setPosition(int(deltaMinutes * pixelsPerMinute), 0)
            timeBar.setVisible(True)
        else:
            timeBar.setVisible(False)

    def __getControl(self, controlId):
        return self.window.getControl(controlId)

    def __findControl(self, controlId):
        rownr = 0
        while rownr < len(self.rows):
            programnr = self.rows[rownr].getControl(controlId)
            if programnr >= 0:
                return rownr, programnr
            rownr += 1
        return -1, -1

    def __get_locator(self, channel: Channel) -> typing.Tuple[str, str]:
        try:
            # max_res = xbmcaddon.Addon('inputstream.adaptive').getSetting('adaptivestream.res.max')
            max_res_drm = xbmcaddon.Addon('inputstream.adaptive').getSetting('adaptivestream.res.secure.max')
            if max_res_drm in ['auto', '1080p', '2K', '4K', '1440p']:
                hd_allowed = True
            else:
                hd_allowed = False
        except:
            hd_allowed = True
        asset_type = 'Orion-DASH'
        if 'Orion-DASH-HEVC' in channel.locators and hd_allowed:
            avc = channel.locators['Orion-DASH-HEVC']
            asset_type = 'Orion-DASH-HEVC'
        elif 'Orion-DASH' in channel.locators:
            avc = channel.locators['Orion-DASH']
        else:
            avc = channel.locators['Default']
        return avc, asset_type

    def __play_channel(self, channel):
        helper = VideoHelpers(self.addon, self.session)
        urlHelper = UrlTools(self.addon)
        player = ZiggoPlayer()
        locator, asset_type = channel.get_locator()
        streaming_token = self.session.obtain_tv_streaming_token(channel, asset_type)
        url = urlHelper.build_url(streaming_token, locator)
        play_item = helper.listitem_from_url(requesturl=url,
                                             streaming_token=streaming_token,
                                             drmContentId=self.session.stream_info['drmContentId'])
        player.play(item=url, listitem=play_item)
        while player.isPlaying():
            xbmc.sleep(10)

    def __replay_event(self, event: Event):
        helper = VideoHelpers(self.addon, self.session)
        urlHelper = UrlTools(self.addon)
        player = ZiggoPlayer()
        streaming_token = self.session.obtain_replay_streaming_token(event.details.eventId)
        url = urlHelper.build_url(streaming_token, self.session.replay_stream_info['url'])
        play_item = helper.listitem_from_url(requesturl=url,
                                             streaming_token=streaming_token,
                                             drmContentId=self.session.replay_stream_info['drmContentId'])
        player.play(item=url, listitem=play_item)
        player.seekTime(0)
        while player.isPlaying():
            xbmc.sleep(10)

    def __play(self, event: Event, channel: Channel):
        if not event.hasDetails:
            event.details = self.session.get_event_details(event.id)
        if event.startTime < utils.DatetimeHelper.unixDatetime(datetime.datetime.now()) < event.endTime:
            choice = xbmcgui.Dialog().yesnocustom('Play', 'Program is currently running.\n'
                                                          'Play from beginning or switch to channel',
                                                  'Cancel', 'Play', 'Switch', False)
            if choice in [-1, 2]:
                return
            else:
                if choice == 0:    # nobutton -> Play
                    self.__replay_event(event)
                elif choice == 1:  # yesbutton -> Switch to channel
                    self.__play_channel(channel)
        elif event.endTime <= utils.DatetimeHelper.unixDatetime(datetime.datetime.now()):  # event already finished
            self.__replay_event(event)
        else:
            self.__play_channel(channel)

    def clear(self):
        for row in self.rows:
            row.clear()
        self.rows.clear()

    def build(self):
        self.clear()
        row = 0
        while row < self.__MAXROWS and self.__firstChannelIndex + row < len(self.channels):
            self.rows.append(ProgramEventRow(row, self.channels[self.__firstChannelIndex + row], self))
            row += 1
        self.__currentRow = 0

    def show(self):
        for row in self.rows:
            row.show()
        row = self.rows[0]
        self.__positionTime()
        if len(row.programs) > 0:
            row.setFocusFirst()

    def onFocus(self, controlId):
        row, program = self.__findControl(controlId)
        if row == -1 or program == -1:
            return
        else:
            self.__currentRow = row
            self.rows[self.__currentRow].setFocus(program)
        self.__displayDetails(row, program)
        xbmc.log('onFocus(): controlId {0} on row {1} item {2}'.format(controlId, self.__currentRow, program),
                 xbmc.LOGDEBUG)

    def onAction(self, action: xbmcgui.Action):
        if action.getId() == xbmcgui.ACTION_MOVE_LEFT:
            moved = self.rows[self.__currentRow].moveLeft()
            if not moved:
                self.__shiftWindow(-1)

        if action.getId() == xbmcgui.ACTION_MOVE_RIGHT:
            moved = self.rows[self.__currentRow].moveRight()
            if not moved:
                self.__shiftWindow(1)

        if action.getId() == xbmcgui.ACTION_MOVE_DOWN:
            self.moveDown()

        if action.getId() == xbmcgui.ACTION_MOVE_UP:
            self.moveUp()

        if action.getId() == xbmcgui.ACTION_PAGE_DOWN:
            self.pageDown()

        if action.getId() == xbmcgui.ACTION_PAGE_UP:
            self.pageUp()

    def onClick(self, controlId: int) -> None:
        if controlId == 1016:  # Move back 1 Day
            self.shiftEpgWindow(-1440)
            self.__updateEvents()
            self.build()
            self.show()
        elif controlId == 1017:  # move 1 day forward
            self.shiftEpgWindow(+1440)
            self.__updateEvents()
            self.build()
            self.show()
        else:
            row, program = self.__findControl(controlId)
            if row == -1 or program == -1:
                return
            else:
                event = self.rows[row].programs[program]
                self.__play(event.programEvent, self.rows[row].channel)

    def onControl(self, control: xbmcgui.Control):
        pass

    def shiftDown(self):
        self.__firstChannelIndex += self.__MAXROWS - 1
        self.clear()
        self.build()
        self.show()

    def shiftUp(self):
        self.__firstChannelIndex -= self.__MAXROWS - 1
        if self.__firstChannelIndex < 0:
            self.__firstChannelIndex = 0
        self.clear()
        self.build()
        self.show()

    def moveDown(self):
        self.__currentRow += 1
        while self.__currentRow < self.__MAXROWS and len(self.rows[self.__currentRow].programs) == 0:
            self.__currentRow += 1
        if self.__currentRow >= self.__MAXROWS:
            self.shiftDown()
        self.rows[self.__currentRow].setFocusFirst()

    def moveUp(self):
        if self.__currentRow > 0:
            self.__currentRow -= 1
        while self.__currentRow >= 0 and len(self.rows[self.__currentRow].programs) == 0:
            self.__currentRow -= 1
        if self.__currentRow <= 0:
            self.shiftUp()
        self.rows[self.__currentRow].setFocusFirst()

    def pageUp(self):
        self.shiftUp()

    def pageDown(self):
        self.shiftDown()

    def __displayDetails(self, row, program):
        program = self.rows[row].programs[program]
        event = program.event
        if not event.hasDetails:
            event.details = self.session.get_event_details(event.id)
        title: xbmcgui.ControlLabel = self.__getControl(1201)
        title.setLabel(event.title)

        description: xbmcgui.ControlLabel = self.__getControl(1203)
        description.setLabel(event.details.description)

        times: xbmcgui.ControlLabel = self.__getControl(1202)
        startTime = utils.DatetimeHelper.fromUnix(event.startTime)
        endTime = utils.DatetimeHelper.fromUnix(event.endTime)
        times.setLabel(startTime.strftime('%H:%M') + ' - ' + endTime.strftime('%H:%M'))

        seasoninfo: xbmcgui.ControlLabel = self.__getControl(1204)
        if event.details.isSeries:
            if event.details.season > 1000:
                seasoninfo.setVisible(False)
            else:
                seasoninfo.setLabel('(S{0}:E{1})'.format(event.details.season, event.details.episode))
                seasoninfo.setVisible(True)
        else:
            seasoninfo.setVisible(False)


class ProgramEventRow:
    def __init__(self,
                 rownr: int,
                 channel: Channel,
                 grid: ProgramEventGrid):
        self.channelName = None
        self.channelIcon = None
        self.focusItem = 0
        self.rownr = rownr
        self.rowheight = 38
        self.pixelsForWindow = 4 * 300  # 4 times half an hour
        self.pixelsPerMinute = self.pixelsForWindow / 120
        self.channel = channel
        self.grid = grid
        self.programs: List[ProgramEvent] = []
        self.addChannelInfo(channel)
        evts = channel.events.getEventsInWindow(grid.startWindow,
                                                grid.endWindow)
        for evt in evts:
            self.programs.append(self.addEvent(evt))

    def addChannelInfo(self, channel):
        ctrlgroup = self.grid.window.getControl(2000)
        ctrl = self.grid.window.getControl(2001)
        width = ctrl.getWidth()
        offset_x = ctrlgroup.getX() + ctrl.getX()
        offset_y = ctrlgroup.getY() + ctrl.getY() + self.rownr * self.rowheight
        self.channelIcon = xbmcgui.ControlImage(x=offset_x,
                                                y=offset_y,
                                                width=width,
                                                height=self.rowheight,
                                                filename=channel.logo['focused'],
                                                aspectRatio=2
                                                )
        ctrl = self.grid.window.getControl(2002)
        width = ctrl.getWidth()
        offset_x = ctrlgroup.getX() + ctrl.getX()
        offset_y = ctrlgroup.getY() + ctrl.getY() + self.rownr * self.rowheight
        self.channelName = xbmcgui.ControlLabel(x=offset_x + 5,
                                                y=offset_y,
                                                width=width - 5,
                                                height=self.rowheight,
                                                label='{0}. {1}'.format(channel.logicalChannelNumber, channel.name),
                                                font='font10'
                                                )
        self.grid.window.addControls([self.channelIcon, self.channelName])

    def addEvent(self, event: Event):
        button = ProgramEvent(self, event)
        return button

    def show(self):
        ctrls = []
        for program in self.programs:
            ctrls.append(program.button)
        self.grid.window.addControls(ctrls)

    def clear(self):
        ctrls = []
        for program in self.programs:
            ctrls.append(program.button)
        ctrls.append(self.channelIcon)
        ctrls.append(self.channelName)
        self.grid.window.removeControls(ctrls)
        self.programs.clear()

    def moveLeft(self):
        if self.focusItem <= 0:
            return False
        else:
            self.focusItem -= 1
            program = self.programs[self.focusItem]
            self.grid.window.setFocus(program.button)
            return True

    def moveRight(self):
        if self.focusItem >= len(self.programs) - 1:
            return False
        else:
            self.focusItem += 1
            program = self.programs[self.focusItem]
            self.grid.window.setFocus(program.button)
            return True

    def setFocusFirst(self):
        program = self.programs[0]
        self.grid.window.setFocus(program.button)
        self.focusItem = 0

    def setFocus(self, program):
        self.focusItem = program

    def getControl(self, controlId):
        buttonnr = 0
        while buttonnr < len(self.programs):
            if self.programs[buttonnr].button.getId() == controlId:
                return buttonnr
            buttonnr += 1
        return -1


class ProgramEvent:

    def __init__(self,
                 row: ProgramEventRow,
                 event: Event):

        self.window = row.grid.window
        self.rowheight = row.rowheight
        self.row = row
        self.grid = row.grid
        self.pixelsForWindow = row.pixelsForWindow
        self.pixelsPerMinute = row.pixelsPerMinute
        self.mediafolder = row.grid.mediaFolder
        self.programEvent = event

        eventStart = event.startTime
        if eventStart < self.grid.unixstarttime:
            eventStart = self.grid.unixstarttime

        eventEnd = event.endTime
        if eventEnd > self.grid.unixendtime:
            eventEnd = self.grid.unixendtime

        ctrlgroup = self.window.getControl(2000)
        ctrl = self.window.getControl(2003)
        width = int(((eventEnd - eventStart) / 60) * self.pixelsPerMinute)
        offset_x = ctrlgroup.getX() + ctrl.getX() + int(
            ((eventStart - self.grid.unixstarttime) / 60) * self.pixelsPerMinute)
        offset_y = ctrlgroup.getY() + ctrl.getY() + row.rownr * self.rowheight
        self.button = xbmcgui.ControlButton(x=offset_x,
                                            y=offset_y,
                                            width=width - 1,
                                            height=self.rowheight - 1,
                                            label='',
                                            focusTexture=self.mediafolder + 'tvg-program-focus.png',
                                            noFocusTexture=self.mediafolder + 'tvg-program-nofocus.png',
                                            font='font10',
                                            focusedColor='white',
                                            textColor='red',
                                            textOffsetY=5,
                                            alignment=G.ALIGNMENT.XBFONT_CENTER_Y + G.ALIGNMENT.XBFONT_TRUNCATED
                                            )
        if width > 30:
            self.button.setLabel(event.title)

    @property
    def controlId(self):
        return self.button.getId()

    @property
    def event(self):
        return self.programEvent

    @event.setter
    def event(self, value):
        self.programEvent = value

    def setFocus(self):
        self.window.setFocus(self.button)
