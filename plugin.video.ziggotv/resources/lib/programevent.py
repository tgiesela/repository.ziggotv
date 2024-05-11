"""
Module with classes for events used in EPG
"""
import datetime
from typing import List

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import utils
from resources.lib.channel import Channel, ChannelList
from resources.lib.channelguide import ChannelGuide
from resources.lib.ziggoplayer import ZiggoPlayer, VideoHelpers
from resources.lib.events import Event
from resources.lib.globals import A
from resources.lib.recording import RecordingList
from resources.lib.utils import ProxyHelper, WebException
from resources.lib.webcalls import LoginSession


class ProgramEventGrid:
    """
    class which implements the EPG grid with rows and columns
    """
    # pylint: disable=too-many-instance-attributes
    MINUTES_IN_GRID = 120
    HALFHOUR_WIDTH = 350
    MAXROWS = 15

    def __init__(self,
                 window: xbmcgui.WindowXML,
                 channels: ChannelList,
                 mediaFolder: str,
                 addon: xbmcaddon.Addon):
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
        self.firstChannelIndex = 0
        self.currentRow = 0
        self.__get_first_window()
        self.addon = addon
        self.guide = ChannelGuide(addon, channels.channels)
        self.__update_events()
        self.player = ZiggoPlayer()
        self.videoHelper = VideoHelpers(self.addon)
        self.helper.dynamic_call(LoginSession.refresh_recordings,
                                 includeAdult=self.addon.getSettingBool('adult-allowed'))
        self.plannedRecordings: RecordingList = self.helper.dynamic_call(LoginSession.get_recordings_planned)

    def __set_epg_date(self, date: datetime.datetime):
        # 1011 EPG Date
        lbl: xbmcgui.ControlLabel = self.__get_control(1011)
        lbl.setLabel(date.strftime('%d-%m-%y'))

    def __set_epg_time(self, date: datetime.datetime):
        # 1012-1015 half hour time
        windowDate = date

        # 1019 EPG Start time
        lbl: xbmcgui.ControlLabel = self.__get_control(1019)
        lbl.setLabel(date.strftime('%H:%M'))

        lbl: xbmcgui.ControlLabel = self.__get_control(1012)
        lbl.setLabel(windowDate.strftime('%H:%M'))
        windowDate = windowDate + datetime.timedelta(minutes=30)
        lbl: xbmcgui.ControlLabel = self.__get_control(1013)
        lbl.setLabel(windowDate.strftime('%H:%M'))
        windowDate = windowDate + datetime.timedelta(minutes=30)
        lbl: xbmcgui.ControlLabel = self.__get_control(1014)
        lbl.setLabel(windowDate.strftime('%H:%M'))
        windowDate = windowDate + datetime.timedelta(minutes=30)
        lbl: xbmcgui.ControlLabel = self.__get_control(1015)
        lbl.setLabel(windowDate.strftime('%H:%M'))
        windowDate = windowDate + datetime.timedelta(minutes=30)
        self.epgEndDatetime = windowDate

    def __process_dates(self):
        self.__set_epg_date(self.startWindow)
        self.__set_epg_time(self.startWindow)
        self.unixstarttime = utils.DatetimeHelper.unix_datetime(self.startWindow)
        self.unixendtime = utils.DatetimeHelper.unix_datetime(self.endWindow)

    def shift_epg_window(self, minutes: int):
        """
        shift the epg window a number of minutes to the left (<0) or right (>0)
        @param minutes: if negative shift to the left if positive shift to the right
        @return:
        """
        self.startWindow = self.startWindow + datetime.timedelta(minutes=minutes)
        self.endWindow = self.startWindow + datetime.timedelta(hours=2)
        self.__process_dates()

    def __get_first_window(self):
        self.startWindow = datetime.datetime.now()
        if self.startWindow.minute > 30:
            self.startWindow = self.startWindow.replace(minute=30, second=0, microsecond=0)
        else:
            self.startWindow = self.startWindow.replace(minute=0, second=0, microsecond=0)
        self.endWindow = self.startWindow + datetime.timedelta(hours=2)
        self.__process_dates()

    def __update_events(self):
        # self.guide.load_stored_events()
        self.guide.obtain_events_in_window(
            self.startWindow.astimezone(datetime.timezone.utc),
            self.endWindow.astimezone(datetime.timezone.utc))
        for channel in self.channels:
            channel.events = self.guide.get_events(channel.id)

    def __shift_window(self, leftorright):
        if leftorright == -1:
            self.shift_epg_window(-90)  # 90 minutes
        else:
            self.shift_epg_window(90)  # 90 minutes
        self.__update_events()
        self.build(stayOnRow=True)
        self.show()

    def __position_time(self):
        timeBar: xbmcgui.ControlLabel = self.window.getControl(2100)
        leftGrid: xbmcgui.ControlImage = self.window.getControl(2106)
        rightGrid: xbmcgui.ControlImage = self.window.getControl(2107)
        leftGrid.setHeight(len(self.rows) * self.rows[0].rowHeight)
        rightGrid.setHeight(len(self.rows) * self.rows[0].rowHeight)
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

    def __get_control(self, controlId):
        return self.window.getControl(controlId)

    def __find_control(self, controlId):
        rownr = 0
        while rownr < len(self.rows):
            programnr = self.rows[rownr].get_control(controlId)
            if programnr >= 0:
                return rownr, programnr
            rownr += 1
        return -1, -1

    def clear(self):
        """
        function to clear all data of all rows
        @return:
        """
        for row in self.rows:
            row.clear()
        self.rows.clear()

    def build(self, stayOnRow=False):
        """
        function to build the epg. Window parameters must have been set before
        @param stayOnRow: when shifting to left or right, we can keep the cursor on the same row
        @return:
        """
        self.clear()
        row = 0
        while row < self.MAXROWS and self.firstChannelIndex + row < len(self.channels):
            self.rows.append(ProgramEventRow(row, self.channels[self.firstChannelIndex + row], self))
            row += 1
        if not stayOnRow:
            self.currentRow = 0

    def show(self):
        """
        Shows the build rows with events
        @return:
        """
        for row in self.rows:
            row.show()
        row = self.rows[self.currentRow]
        self.__position_time()
        if len(row.programs) > 0:
            row.set_focus_first()

    #  pylint: disable=invalid-name
    def onFocus(self, controlId):
        """
        When an program event gets the focus, the details will be displayed in bottom area of the epg
        @param controlId:
        @return:
        """
        row, program = self.__find_control(controlId)
        if row == -1 or program == -1:
            return
        self.currentRow = row
        self.rows[self.currentRow].set_focus(program)
        self.__display_details(row, program)
        xbmc.log('onFocus(): controlId {0} on row {1} item {2}'.format(controlId, self.currentRow, program),
                 xbmc.LOGDEBUG)

    def onAction(self, action: xbmcgui.Action):
        """
        function to handle all key, click and cursor move events
        @param action:
        @return:
        """
        if action.getId() == xbmcgui.ACTION_STOP:
            # if xbmc.Player().isPlaying():
            #    xbmc.Player().stop()
            return

        if action.getId() == xbmcgui.ACTION_PREVIOUS_MENU or action.getId() == xbmcgui.ACTION_NAV_BACK:
            # if xbmc.Player().isPlaying():
            #    xbmc.Player().stop()
            return

        if action.getId() == xbmcgui.ACTION_MOVE_LEFT:
            moved = self.rows[self.currentRow].move_left()
            if not moved:
                self.__shift_window(-1)
            return

        if action.getId() == xbmcgui.ACTION_MOVE_RIGHT:
            moved = self.rows[self.currentRow].move_right()
            if not moved:
                self.__shift_window(1)
            return

        if action.getId() == xbmcgui.ACTION_MOVE_DOWN:
            self.move_down()
        elif action.getId() == xbmcgui.ACTION_MOVE_UP:
            self.move_up()
        elif action.getId() == xbmcgui.ACTION_PAGE_DOWN:
            self.page_down()
        elif action.getId() == xbmcgui.ACTION_PAGE_UP:
            self.page_up()

    def onClick(self, controlId: int) -> None:
        """
        Handle the click event for a specific control
        @param controlId:
        @return:
        """
        if controlId in [1016, 1017]:  # Move  1 Day
            if controlId == 1016:
                self.shift_epg_window(-1440)
            else:
                self.shift_epg_window(+1440)
            self.__update_events()
            self.build(stayOnRow=True)
            self.show()
        elif controlId in [1018, 1020]:  # move 6 hours
            if controlId == 1018:
                self.shift_epg_window(-360)
            else:
                self.shift_epg_window(+360)
            self.__update_events()
            self.build(stayOnRow=True)
            self.show()
        else:
            row, program = self.__find_control(controlId)
            if row == -1 or program == -1:
                return
            event = self.rows[row].programs[program]
            try:
                self.videoHelper.play_epg(event.programEvent, self.rows[row].channel)

            except WebException as exc:
                xbmc.log('Webexception in play_epg: {0}'.format(exc), xbmc.LOGERROR)
                xbmcgui.Dialog().ok('Error', exc.response)
            # pylint: disable=broad-exception-caught
            except Exception as exc:
                xbmc.log('Exception in play_epg: {0}'.format(exc), xbmc.LOGERROR)
                xbmcgui.Dialog().ok('Error', '{0}'.format(exc))

    def onControl(self, control: xbmcgui.Control):
        """
        Not used
        @param control:
        @return:
        """
    #  pylint: enable=invalid-name

    def shift_down(self):
        """
        Shift epg window down one page if we are not on the last row
        @return:
        """
        if self.firstChannelIndex + self.MAXROWS >= len(self.channels):
            return
        self.firstChannelIndex += self.MAXROWS - 1
        self.clear()
        self.build()
        self.show()

    def shift_up(self):
        """
        Shift epg window up one page if we are not on the first row
        @return:
        """
        if self.firstChannelIndex <= 0:
            return
        self.firstChannelIndex -= self.MAXROWS - 1
        self.firstChannelIndex = max(self.firstChannelIndex, 0)
        self.clear()
        self.build()
        self.show()

    def move_down(self):
        """
        Move the cursor one row down
        @return:
        """
        currentRow = self.rows[self.currentRow]
        currentEvent = currentRow.programs[currentRow.focusItem]
        self.currentRow += 1
        while self.currentRow < self.MAXROWS and len(self.rows[self.currentRow].programs) == 0:
            self.currentRow += 1
        if self.currentRow >= self.MAXROWS:
            self.shift_down()
        if currentRow is not None and currentEvent is not None:
            self.rows[self.currentRow].set_focus_nearest(currentEvent)
        else:
            self.rows[self.currentRow].set_focus_first()

    def move_up(self):
        """
        Move the cursor one row up
        @return:
        """
        currentRow = self.rows[self.currentRow]
        currentEvent = currentRow.programs[currentRow.focusItem]
        self.currentRow -= 1
        while self.currentRow >= 0 and len(self.rows[self.currentRow].programs) == 0:
            self.currentRow -= 1
        if self.currentRow < 0:
            if self.firstChannelIndex > 0:
                self.shift_up()
            else:
                self.currentRow = 0
        if currentRow is not None and currentEvent is not None:
            self.rows[self.currentRow].set_focus_nearest(currentEvent)
        else:
            self.rows[self.currentRow].set_focus_first()

    def page_up(self):
        """
        move the epg a page up
        @return:
        """
        self.shift_up()

    def page_down(self):
        """
        move the epg a page down
        @return:
        """
        self.shift_down()

    def __display_details(self, row, program):
        program = self.rows[row].programs[program]
        event = program.event
        if not event.hasDetails:
            event.details = self.helper.dynamic_call(LoginSession.get_event_details, eventId=event.id)
        title: xbmcgui.ControlLabel = self.__get_control(1201)
        title.setLabel(event.title)

        description: xbmcgui.ControlLabel = self.__get_control(1203)
        description.setLabel(event.details.description)

        times: xbmcgui.ControlLabel = self.__get_control(1202)
        startTime = utils.DatetimeHelper.from_unix(event.startTime)
        endTime = utils.DatetimeHelper.from_unix(event.endTime)
        times.setLabel(startTime.strftime('%H:%M') + ' - ' + endTime.strftime('%H:%M'))

        seasoninfo: xbmcgui.ControlLabel = self.__get_control(1204)
        if event.details.isSeries:
            if event.details.season > 1000 or event.details.episode > 1000:
                seasoninfo.setVisible(False)
            else:
                seasoninfo.setLabel('(S{0}:E{1})'.format(event.details.season, event.details.episode))
                seasoninfo.setVisible(True)
        else:
            seasoninfo.setVisible(False)

    def set_focus(self):
        """
        function called when item gets focus.
        @return:
        """
        row: ProgramEventRow = self.rows[self.currentRow]
        program: ProgramEvent = row.programs[row.focusItem]
        self.window.setFocusId(program.controlId)

    def is_at_first_row(self):
        """
        function to detect if we are on the first row
        @return:
        """
        return self.firstChannelIndex <= 0 and self.currentRow == 0


class ProgramEventRow:
    # pylint: disable=too-many-instance-attributes
    """
    class representing a row in the EPG grid
    """
    def __init__(self,
                 rownr: int,
                 channel: Channel,
                 grid: ProgramEventGrid):
        self.rowHeight = 55
        self.channelName = None
        self.channelIcon = None
        self.focusItem = 0
        self.rownr = rownr
        self.channel = channel
        self.grid = grid
        self.pixelsForWindow = 4 * grid.HALFHOUR_WIDTH  # 4 times half an hour
        self.pixelsPerMinute = self.pixelsForWindow / grid.MINUTES_IN_GRID
        self.programs: List[ProgramEvent] = []
        self.add_channel_info(channel)
        evts = channel.events.get_events_in_window(grid.startWindow,
                                                   grid.endWindow)
        for evt in evts:
            self.programs.append(self.add_event(evt))

    def add_channel_info(self, channel):
        """
        Adds channel information to the epg grid
        @param channel:
        @return:
        """
        ctrlgroup = self.grid.window.getControl(2000)
        self.rowHeight = int(ctrlgroup.getHeight() / self.grid.MAXROWS)
        ctrl = self.grid.window.getControl(2001)
        width = ctrl.getWidth()
        offsetX = ctrlgroup.getX() + ctrl.getX()
        offsetY = ctrlgroup.getY() + ctrl.getY() + self.rownr * self.rowHeight
        self.channelIcon = xbmcgui.ControlImage(x=offsetX,
                                                y=offsetY,
                                                width=width,
                                                height=self.rowHeight,
                                                filename=channel.logo['focused'],
                                                aspectRatio=2
                                                )
        ctrl = self.grid.window.getControl(2002)
        width = ctrl.getWidth()
        offsetX = ctrlgroup.getX() + ctrl.getX()
        offsetY = ctrlgroup.getY() + ctrl.getY() + self.rownr * self.rowHeight
        if self.grid.channels.is_entitled(channel):
            txtColor = 'white'
        else:
            txtColor = '80FF3300'
        self.channelName = xbmcgui.ControlLabel(x=offsetX + 5,
                                                y=offsetY,
                                                width=width - 5,
                                                height=self.rowHeight,
                                                label='{0}. {1}'.format(channel.logicalChannelNumber, channel.name),
                                                font='font12',
                                                textColor=txtColor,
                                                alignment=A.XBFONT_CENTER_Y + A.XBFONT_LEFT
                                                )
        self.grid.window.addControls([self.channelIcon, self.channelName])

    def add_event(self, event: Event):
        """
        Adds an event button to the EPG
        @param event: information of the event
        @return: the button class
        """
        button = ProgramEvent(self, event)
        return button

    def show(self):
        """
        Creates a list of controls and adds them to the window.
        @return:
        """
        ctrls = []
        for program in self.programs:
            ctrls.append(program.button)
        self.grid.window.addControls(ctrls)

    def clear(self):
        """
        Removes all controls in the row from the window
        @return:
        """
        ctrls = []
        for program in self.programs:
            ctrls.append(program.button)
        ctrls.append(self.channelIcon)
        ctrls.append(self.channelName)
        self.grid.window.removeControls(ctrls)
        self.programs.clear()

    def move_left(self):
        """
        go to the program event left of the current one
        @return:
        """
        if self.focusItem <= 0:
            return False
        self.focusItem -= 1
        program = self.programs[self.focusItem]
        self.grid.window.setFocus(program.button)
        return True

    def move_right(self):
        """
        go to the program event to the right of the current one
        @return:
        """
        if self.focusItem >= len(self.programs) - 1:
            return False
        self.focusItem += 1
        program = self.programs[self.focusItem]
        self.grid.window.setFocus(program.button)
        return True

    def set_focus_first(self):
        """
        Sets the focus on the first item in the row
        @return:
        """
        program = self.programs[0]
        self.grid.window.setFocus(program.button)
        self.focusItem = 0

    def set_focus_nearest(self, currentEvent):
        """
        Sets the focus on the nearest item in the row
        @param currentEvent: the event to which it is currently positioned
        @return:
        """
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
        self.set_focus_first()

    def set_focus(self, program):
        """
        set focus on a specific program
        @param program:
        @return:
        """
        self.focusItem = program

    def get_control(self, controlId):
        """
        Get a specific control with the id of controlId
        @param controlId: id to look for in programs
        @return:
        """
        buttonnr = 0
        while buttonnr < len(self.programs):
            if self.programs[buttonnr].button.getId() == controlId:
                return buttonnr
            buttonnr += 1
        return -1


class ProgramEvent:
    # pylint: disable=too-many-instance-attributes
    """
    class containing the event and the button for the EPG.
    """
    def __init__(self,
                 row: ProgramEventRow,
                 event: Event):

        self.window = row.grid.window
        self.rowheight = row.rowHeight
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
        offsetX = ctrlgroup.getX() + ctrl.getX() + int(
            ((eventStart - self.grid.unixstarttime) / 60) * self.pixelsPerMinute)
        offsetY = ctrlgroup.getY() + ctrl.getY() + row.rownr * self.rowheight
        textColor = '80FF3300'
        if event.canReplay and row.grid.channels.supports_replay(row.channel):
            textColor = 'white'
        else:
            #  Replay not allowed or not possible
            #  Let's check if event is still running or in the future,
            #  then we can switch to the channel if it is selected
            if event.endTime > utils.DatetimeHelper.unix_datetime(datetime.datetime.now()):
                textColor = 'white'
        plannedRec = self.grid.plannedRecordings.find(event.id)
        if plannedRec is not None:
            shadowColor = 'FFFF0000'
        else:
            shadowColor = 'white'
        self.button = xbmcgui.ControlButton(x=offsetX,
                                            y=offsetY,
                                            width=width - 1,
                                            height=self.rowheight - 1,
                                            label='',
                                            focusTexture=self.mediafolder + 'tvg-program-focus.png',
                                            noFocusTexture=self.mediafolder + 'tvg-program-nofocus.png',
                                            font='font12',
                                            focusedColor=textColor,
                                            textColor=textColor,
                                            textOffsetY=5,
                                            alignment=A.XBFONT_CENTER_Y + A.XBFONT_TRUNCATED,
                                            shadowColor=shadowColor
                                            )
        if width > 30:
            self.button.setLabel(event.title)

    @property
    def controlId(self) -> int:
        """
        get the id of the control
        @return: id
        """
        return self.button.getId()

    @property
    def event(self) -> Event:
        """
        get the program event
        @return: event
        """
        return self.programEvent

    @event.setter
    def event(self, value):
        self.programEvent = value
