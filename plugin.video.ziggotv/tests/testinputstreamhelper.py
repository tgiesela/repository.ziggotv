"""
Dummy class to replace InputStreamHelper during tests
"""
class Helper:
    def __init__(self, protocol, drm):
        self.protocol = protocol
        self.drm = drm
    @staticmethod
    def check_inputstream():
        """
        Dummy function
        @return:
        """
        return True

    def inputstream_addon(self):
        return 'inputstream.adaptive'