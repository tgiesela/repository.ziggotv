import datetime
from typing import List

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import utils
from resources.lib.channel import Channel, ChannelList, ChannelGuide
from resources.lib.ZiggoPlayer import ZiggoPlayer, VideoHelpers
from resources.lib.events import Event
from resources.lib.globals import G, S
from resources.lib.recording import RecordingList
from resources.lib.utils import ProxyHelper
from resources.lib.webcalls import LoginSession, WebException


class ProgramEventGrid:
    def __init__(self,
                 window: xbmcgui.WindowXML,
                 channels: ChannelList,
                 mediaFolder: str,
                 addon: xbmcaddon.Addon):
        self.MINUTES_IN_GRID = 120
        self.HALFHOUR_WIDTH = 350
        self.MAXROWS = 15
        self.helper = ProxyHelper(addon)
        self.startWindow = None
        self.endWindow = None
        self.epgEndDatetime = None
        self.unixstarttime = None
        self.unixendtime = None
        self.rows: List[ProgramEventRow] = []
        self.channels: ChannelList = channels
        self.channelsInGrid: List[Channel] = []
        self.mediaFolder = mediaFolder
        self.window = window
        self.__firstChannelIndex = 0
        self.__currentRow = 0
        self.__getFirstWindow()
        self.addon = addon
        self.guide = ChannelGuide(addon, channels.channels)
        self.__updateEvents()
        self.player = ZiggoPlayer()
        self.videoHelper = VideoHelpers(self.addon)
        self.plannedRecordings: RecordingList = self.helper.dynamicCall(LoginSession.getRecordingsPlanned)

    def __setEPGDate(self, date: datetime.datetime):
        # 1011 EPG Date
        lbl: xbmcgui.ControlLabel = self.__getControl(1011)
        lbl.setLabel(date.strftime('%d-%m-%y'))

    def __setEpgTime(self, date: datetime.datetime):
        # 1012-1015 half hour time
        windowDate = date

        # 1019 EPG Start time
        lbl: xbmcgui.ControlLabel = self.__getControl(1019)
        lbl.setLabel(date.strftime('%H:%M'))

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
        self.guide.loadStoredEvents()
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
        self.build(stayOnRow=True)
        self.show()

    def __positionTime(self):
        timeBar: xbmcgui.ControlLabel = self.window.getControl(2100)
        leftGrid: xbmcgui.ControlImage = self.window.getControl(2106)
        rightGrid: xbmcgui.ControlImage = self.window.getControl(2107)
        leftGrid.setHeight(len(self.rows) * self.rows[0].ROW_HEIGHT)
        rightGrid.setHeight(len(self.rows) * self.rows[0].ROW_HEIGHT)
        leftGrid.setVisible(False)
        rightGrid.setVisible(False)
        timeBar.setVisible(False)
        currentTime = datetime.datetime.now()
        pixelsForWindow = 4 * self.HALFHOUR_WIDTH  # 4 times half an hour
        if self.startWindow <= currentTime < self.endWindow:
            pixelsPerMinute = pixelsForWindow / self.MINUTES_IN_GRID
            delta = currentTime - self.startWindow
            deltaMinutes = int(delta.total_seconds() / 60)
            width = int(deltaMinutes * pixelsPerMinute)
            timeBar.setPosition(int(deltaMinutes * pixelsPerMinute), 0)
            timeBar.setVisible(True)
            leftGrid.setPosition(1, 0)
            leftGrid.setWidth(width-2)
            leftGrid.setVisible(True)
            rightGrid.setPosition(width + 2, 0)
            rightGrid.setWidth(pixelsForWindow - width - 2)
            rightGrid.setVisible(True)
        else:
            if currentTime < self.startWindow:
                rightGrid.setPosition(1, 0)
                rightGrid.setWidth(pixelsForWindow-2)
                rightGrid.setVisible(True)
            else:
                leftGrid.setPosition(1, 0)
                leftGrid.setWidth(pixelsForWindow-2)
                leftGrid.setVisible(True)

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

    def isAtFirstRow(self):
        return self.__firstChannelIndex <= 0 and self.__currentRow == 0

    def clear(self):
        for row in self.rows:
            row.clear()
        self.rows.clear()

    def build(self, stayOnRow=False):
        self.clear()
        row = 0
        while row < self.MAXROWS and self.__firstChannelIndex + row < len(self.channels):
            self.rows.append(ProgramEventRow(row, self.channels[self.__firstChannelIndex + row], self))
            row += 1
        if not stayOnRow:
            self.__currentRow = 0

    def show(self):
        for row in self.rows:
            row.show()
        row = self.rows[self.__currentRow]
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
        if action.getId() == xbmcgui.ACTION_STOP:
            # if xbmc.Player().isPlaying():
            #    xbmc.Player().stop()
            return

        if action.getId() == xbmcgui.ACTION_PREVIOUS_MENU or action.getId() == xbmcgui.ACTION_NAV_BACK:
            # if xbmc.Player().isPlaying():
            #    xbmc.Player().stop()
            return

        if action.getId() == xbmcgui.ACTION_MOVE_LEFT:
            moved = self.rows[self.__currentRow].moveLeft()
            if not moved:
                self.__shiftWindow(-1)
            return

        if action.getId() == xbmcgui.ACTION_MOVE_RIGHT:
            moved = self.rows[self.__currentRow].moveRight()
            if not moved:
                self.__shiftWindow(1)
            return

        if action.getId() == xbmcgui.ACTION_MOVE_DOWN:
            self.moveDown()
            return

        if action.getId() == xbmcgui.ACTION_MOVE_UP:
            self.moveUp()
            return

        if action.getId() == xbmcgui.ACTION_PAGE_DOWN:
            self.pageDown()
            return

        if action.getId() == xbmcgui.ACTION_PAGE_UP:
            self.pageUp()
            return

    def onClick(self, controlId: int) -> None:
        if controlId in [1016, 1017]:  # Move  1 Day
            if controlId == 1016:
                self.shiftEpgWindow(-1440)
            else:
                self.shiftEpgWindow(+1440)
            self.__updateEvents()
            self.build(stayOnRow=True)
            self.show()
        elif controlId in [1018, 1020]:  # move 6 hours
            if controlId == 1018:
                self.shiftEpgWindow(-360)
            else:
                self.shiftEpgWindow(+360)
            self.__updateEvents()
            self.build(stayOnRow=True)
            self.show()
        else:
            row, program = self.__findControl(controlId)
            if row == -1 or program == -1:
                return
            else:
                event = self.rows[row].programs[program]
                try:
                    self.videoHelper = VideoHelpers(self.addon)
                    self.videoHelper.play_epg(event.programEvent, self.rows[row].channel)
                except WebException as exc:
                    xbmcgui.Dialog().ok('Error', exc.getResponse())
                except Exception as exc:
                    xbmcgui.Dialog().ok('Error', '{0}'.format(exc))

    def onControl(self, control: xbmcgui.Control):
        pass

    def shiftDown(self):
        if self.__firstChannelIndex + self.MAXROWS >= len(self.channels):
            return
        self.__firstChannelIndex += self.MAXROWS - 1
        self.clear()
        self.build()
        self.show()

    def shiftUp(self):
        if self.__firstChannelIndex <= 0:
            return
        self.__firstChannelIndex -= self.MAXROWS - 1
        if self.__firstChannelIndex < 0:
            self.__firstChannelIndex = 0
        self.clear()
        self.build()
        self.show()

    def moveDown(self):
        currentRow = self.rows[self.__currentRow]
        currentEvent = currentRow.programs[currentRow.focusItem]
        self.__currentRow += 1
        while self.__currentRow < self.MAXROWS and len(self.rows[self.__currentRow].programs) == 0:
            self.__currentRow += 1
        if self.__currentRow >= self.MAXROWS:
            self.shiftDown()
        if currentRow is not None and currentEvent is not None:
            self.rows[self.__currentRow].setFocusNearest(currentEvent)
        else:
            self.rows[self.__currentRow].setFocusFirst()

    def moveUp(self):
        currentRow = self.rows[self.__currentRow]
        currentEvent = currentRow.programs[currentRow.focusItem]
        self.__currentRow -= 1
        while self.__currentRow >= 0 and len(self.rows[self.__currentRow].programs) == 0:
            self.__currentRow -= 1
        if self.__currentRow < 0:
            if self.__firstChannelIndex > 0:
                self.shiftUp()
            else:
                self.__currentRow = 0
        if currentRow is not None and currentEvent is not None:
            self.rows[self.__currentRow].setFocusNearest(currentEvent)
        else:
            self.rows[self.__currentRow].setFocusFirst()

    def pageUp(self):
        self.shiftUp()

    def pageDown(self):
        self.shiftDown()

    def __displayDetails(self, row, program):
        program = self.rows[row].programs[program]
        event = program.event
        if not event.hasDetails:
            event.details = self.helper.dynamicCall(LoginSession.get_event_details, eventId=event.id)
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
            if event.details.season > 1000 or event.details.episode > 1000:
                seasoninfo.setVisible(False)
            else:
                seasoninfo.setLabel('(S{0}:E{1})'.format(event.details.season, event.details.episode))
                seasoninfo.setVisible(True)
        else:
            seasoninfo.setVisible(False)

    def userWantsSwitch(self):
        choice = xbmcgui.Dialog().yesno('Play',
                                        self.addon.getLocalizedString(S.MSG_SWITCH),
                                        self.addon.getLocalizedString(S.BTN_CANCEL),
                                        self.addon.getLocalizedString(S.BTN_SWITCH),
                                        False,
                                        xbmcgui.DLG_YESNO_NO_BTN)
        return choice

    def setFocus(self):
        row: ProgramEventRow = self.rows[self.__currentRow]
        program: ProgramEvent = row.programs[row.focusItem]
        self.window.setFocusId(program.controlId)


class ProgramEventRow:
    def __init__(self,
                 rownr: int,
                 channel: Channel,
                 grid: ProgramEventGrid):
        self.channelName = None
        self.channelIcon = None
        self.focusItem = 0
        self.rownr = rownr
        self.ROW_HEIGHT = 55
        self.channel = channel
        self.grid = grid
        self.pixelsForWindow = 4 * grid.HALFHOUR_WIDTH  # 4 times half an hour
        self.pixelsPerMinute = self.pixelsForWindow / grid.MINUTES_IN_GRID
        self.programs: List[ProgramEvent] = []
        self.addChannelInfo(channel)
        evts = channel.events.getEventsInWindow(grid.startWindow,
                                                grid.endWindow)
        for evt in evts:
            self.programs.append(self.addEvent(evt))

    def addChannelInfo(self, channel):
        ctrlgroup = self.grid.window.getControl(2000)
        self.ROW_HEIGHT = int(ctrlgroup.getHeight() / self.grid.MAXROWS)
        ctrl = self.grid.window.getControl(2001)
        width = ctrl.getWidth()
        offset_x = ctrlgroup.getX() + ctrl.getX()
        offset_y = ctrlgroup.getY() + ctrl.getY() + self.rownr * self.ROW_HEIGHT
        self.channelIcon = xbmcgui.ControlImage(x=offset_x,
                                                y=offset_y,
                                                width=width,
                                                height=self.ROW_HEIGHT,
                                                filename=channel.logo['focused'],
                                                aspectRatio=2
                                                )
        ctrl = self.grid.window.getControl(2002)
        width = ctrl.getWidth()
        offset_x = ctrlgroup.getX() + ctrl.getX()
        offset_y = ctrlgroup.getY() + ctrl.getY() + self.rownr * self.ROW_HEIGHT
        if self.grid.channels.isEntitled(channel):
            txtColor = 'white'
        else:
            txtColor = '80FF3300'
        self.channelName = xbmcgui.ControlLabel(x=offset_x + 5,
                                                y=offset_y,
                                                width=width - 5,
                                                height=self.ROW_HEIGHT,
                                                label='{0}. {1}'.format(channel.logicalChannelNumber, channel.name),
                                                font='font12',
                                                textColor=txtColor,
                                                alignment=G.ALIGNMENT.XBFONT_CENTER_Y + G.ALIGNMENT.XBFONT_LEFT
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

    def setFocusNearest(self, currentEvent):
        # Find the event that is nearest to current Event and set focus on it
        buttonNr = 0
        while buttonNr < len(self.programs):
            if (self.programs[buttonNr].event.startTime < currentEvent.event.startTime <
                    self.programs[buttonNr].event.endTime):
                #  Found on
                self.grid.window.setFocus(self.programs[buttonNr].button)
                self.focusItem = buttonNr
                return
            buttonNr += 1
        self.setFocusFirst()

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
        self.rowheight = row.ROW_HEIGHT
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
        textColor = '80FF3300'
        if event.canReplay and row.grid.channels.supportsReplay(row.channel):
            textColor = 'white'
        else:
            #  Replay not allowed or not possible
            #  Let's check if event is still running or in the future,
            #  then we can switch to the channel if it is selected
            if event.endTime > utils.DatetimeHelper.unixDatetime(datetime.datetime.now()):
                textColor = 'white'
        plannedRec = self.grid.plannedRecordings.find(event.id)
        if plannedRec is not None:
            shadowColor = 'FFFF0000'
        else:
            shadowColor = 'white'
        self.button = xbmcgui.ControlButton(x=offset_x,
                                            y=offset_y,
                                            width=width - 1,
                                            height=self.rowheight - 1,
                                            label='',
                                            focusTexture=self.mediafolder + 'tvg-program-focus.png',
                                            noFocusTexture=self.mediafolder + 'tvg-program-nofocus.png',
                                            font='font12',
                                            focusedColor=textColor,
                                            textColor=textColor,
                                            textOffsetY=5,
                                            alignment=G.ALIGNMENT.XBFONT_CENTER_Y + G.ALIGNMENT.XBFONT_TRUNCATED,
                                            shadowColor=shadowColor
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
