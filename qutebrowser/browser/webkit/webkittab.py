# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Wrapper over our (QtWebKit) WebView."""

from PyQt5.QtCore import pyqtSlot, Qt, QEvent
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWebKitWidgets import QWebPage

from qutebrowser.browser import tab
from qutebrowser.browser.webkit import webview
from qutebrowser.utils import qtutils


class WebViewScroller(tab.AbstractScroller):

    def pos_px(self):
        return self.widget.page().mainFrame().scrollPosition()

    def pos_perc(self):
        return self.widget.scroll_pos

    def to_point(self, point):
        self.widget.page().mainFrame().setScrollPosition(point)

    def delta(x=0, y=0):
        qtutils.check_overflow(x, 'int')
        qtutils.check_overflow(y, 'int')
        self.widget.page().mainFrame().scroll(x, y)

    def delta_page(self, x=0, y=0):
        if y.is_integer():
            y = int(y)
            if y == 0:
                pass
            elif y < 0:
                self.page_up(count=y)
            elif y > 0:
                self.page_down(count=y)
            y = 0
        if x == 0 and y == 0:
            return
        size = frame.geometry()
        self.delta(x * size.width(), y * size.height())

    def to_perc(self, x=None, y=None):
        if x is None and y == 0:
            self.top()
        elif x is None and y == 100:
            self.bottom()
        else:
            for val, orientation in [(x, Qt.Horizontal), (y, Qt.Vertical)]:
                perc = qtutils.check_overflow(val, 'int', fatal=False)
                frame = self.widget.page().mainFrame()
                m = frame.scrollBarMaximum(orientation)
                if m == 0:
                    continue
                frame.setScrollBarValue(orientation, int(m * val / 100))

    def _key_press(self, key, count=1, getter_name=None, direction=None):
        frame = self.widget.page().mainFrame()
        press_evt = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, 0, 0, 0)
        release_evt = QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier, 0, 0, 0)
        getter = None if getter_name is None else getattr(frame, getter_name)

        for _ in range(count):
            # Abort scrolling if the minimum/maximum was reached.
            if frame.scrollBarValue(direction) == getter(direction):
                return
            self.widget.keyPressEvent(press_evt)
            self.widget.keyReleaseEvent(release_evt)

    def up(self, count=1):
        self._key_press(Qt.Key_Up, count, 'scrollBarMinimum', Qt.Vertical)

    def down(self, count=1):
        self._key_press(Qt.Key_Down, count, 'scrollBarMaximum', Qt.Vertical)

    def left(self, count=1):
        self._key_press(Qt.Key_Left, count, 'scrollBarMinimum', Qt.Horizontal)

    def right(self, count=1):
        self._key_press(Qt.Key_Right, count, 'scrollBarMaximum', Qt.Horizontal)

    def top(self):
        self._key_press(Qt.Key_Home)

    def bottom(self):
        self._key_press(Qt.Key_End)

    def page_up(self, count=1):
        self._key_press(Qt.Key_PageUp, count, 'scrollBarMinimum', Qt.Vertical)

    def page_down(self, count=1):
        self._key_press(Qt.Key_PageDown, count, 'scrollBarMaximum',
                        Qt.Vertical)

    def at_top(self):
        return self.pos_px().y() == 0

    def at_bottom(self):
        frame = self.widget.page().currentFrame()
        return self.pos_px().y() >= frame.scrollBarMaximum(Qt.Vertical)


class WebViewHistory(tab.AbstractHistory):

    def __iter__(self):
        return iter(self.history.items())

    def current_idx(self):
        return self.history.currentItemIndex()

    def back(self):
        self.history.back()

    def forward(self):
        self.history.forward()

    def can_go_back(self):
        return self.history.canGoBack()

    def can_go_forward(self):
        return self.history.canGoForward()

    def serialize(self):
        return qtutils.serialize(self.history)

    def deserialize(self, data):
        return qtutils.deserialize(data, self.history)

    def load_items(self, items):
        stream, _data, user_data = tabhistory.serialize(items)
        qtutils.deserialize_stream(stream, self.history)
        for i, data in enumerate(user_data):
            self.history.itemAt(i).setUserData(data)
        cur_data = self.history.currentItem().userData()
        if cur_data is not None:
            if 'zoom' in cur_data:
                self.tab.zoom_perc(cur_data['zoom'] * 100)
            if ('scroll-pos' in cur_data and
                    self.tab.scroll.pos_px() == QPoint(0, 0)):
                QTimer.singleShot(0, functools.partial(
                    self.tab.scroll, cur_data['scroll-pos']))


class WebViewTab(tab.AbstractTab):

    def __init__(self, win_id, parent=None):
        super().__init__(win_id)
        widget = webview.WebView(win_id, self.tab_id)
        self.history = WebViewHistory(self)
        self.scroll = WebViewScroller(parent=self)
        self._set_widget(widget)
        self._connect_signals()

    def openurl(self, url):
        self._widget.openurl(url)

    @property
    def cur_url(self):
        return self._widget.cur_url

    @property
    def progress(self):
        return self._widget.progress

    @property
    def load_status(self):
        return self._widget.load_status

    def dump_async(self, callback=None, *, plain=False):
        frame = self._widget.page().mainFrame()
        if plain:
            callback(frame.toPlainText())
        else:
            callback(frame.toHtml())

    def icon(self):
        return self._widget.icon()

    def shutdown(self):
        self._widget.shutdown()

    def reload(self, *, force=False):
        if force:
            action = QWebPage.ReloadAndBypassCache
        else:
            action = QWebPage.Reload
        self._widget.triggerPageAction(action)

    def stop(self):
        self._widget.stop()

    def title(self):
        return self._widget.title()

    def set_zoom_factor(self, factor):
        self._widget.setZoomFactor(factor)

    def zoom_factor(self):
        return self._widget.zoomFactor()

    def _connect_signals(self):
        view = self._widget
        page = view.page()
        frame = page.mainFrame()
        page.windowCloseRequested.connect(self.window_close_requested)
        page.linkHovered.connect(self.link_hovered)
        page.loadProgress.connect(self.load_progress)
        frame.loadStarted.connect(self.load_started)
        view.scroll_pos_changed.connect(self.scroll.perc_changed)
        view.titleChanged.connect(self.title_changed)
        view.url_text_changed.connect(self.url_text_changed)
        view.load_status_changed.connect(self.load_status_changed)
        view.shutting_down.connect(self.shutting_down)

        # Make sure we emit an appropriate status when loading finished.
        # While Qt has a bool "ok" attribute for loadFinished, it always is True
        # when using error pages...
        # See https://github.com/The-Compiler/qutebrowser/issues/84
        frame.loadFinished.connect(lambda:
                                   self.load_finished.emit(
                                       not self._widget.page().error_occurred))

        # Emit iconChanged with a QIcon like QWebEngineView does.
        view.iconChanged.connect(lambda:
                                 self.icon_changed.emit(self._widget.icon()))
