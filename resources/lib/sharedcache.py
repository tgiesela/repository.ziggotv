from xbmcgui import Window


class SharedCache:
    def __init__(self):
        self.window = Window(10000)
        self.propwindow = Window()
        self.window.clearProperties()  # Can interfere with other plugins

    def setprop(self, key, value):
        print("SHAREDCACHE property {0} set to {1}".format(key, value))
        self.window.setProperty(key, value)

    def getprop(self, key):
        print("SHAREDCACHE property {0} ".format(key))
        return self.window.getProperty(key)

    def clear(self):
        self.window.clearProperties()
