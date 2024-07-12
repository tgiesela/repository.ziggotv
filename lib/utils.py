"""
    module with some utility functions
"""
import re
import os
import shutil
import zipfile
from hashlib import sha256
import stat


class Utils:
    """
        Class with some utility functions
    """
    @staticmethod
    def is_url(path):
        """ Check if poath is an URL"""
        return bool(re.match(r'[A-Za-z0-9+.-]+://.', path))

    @staticmethod
    def is_dir(path):
        """ Check is path is a (existing) folder """
        return os.path.isdir(path)

    @staticmethod
    def is_file(path):
        """ Check if path is a file """
        return os.path.isfile(path)

    @staticmethod
    def path_append_sep(path: str) -> str:
        """ Function append a separator to a path if not already present """
        if path[-1] == '/' or path[-1] == os.sep:
            return path
        return path + '/'

    @staticmethod
    def joindir(path, file) -> str:
        """ joind directory path with filename """
        return Utils.path_append_sep(path) + file

    @staticmethod
    def dirname(pathorfile) -> str:
        """ get directory of a path/file """
        return os.path.dirname(pathorfile)

    @staticmethod
    def onerror(func, path, _):
        """
        Error handler for ``shutil.rmtree``.

        If the error is due to an access error (read only file)
        it attempts to add write permission and then retries.

        If the error is for another reason it re-raises the error.

        Usage : ``shutil.rmtree(path, onerror=onerror)``
        """
        # Is the error an access error?
        # pylint: disable=misplaced-bare-raise
        if not os.access(path, os.W_OK):
            os.chmod(path, stat.S_IWUSR)
            func(path)
        else:
            raise

    @staticmethod
    def rmtree(folder):
        """ function to remove a directory and all its files"""
        # (due to version mismatch (3.12.0 vs 3.12.4))
        # pylint: disable=deprecated-argument
        shutil.rmtree(folder, onerror=Utils.onerror)


class ZipAddon:
    """
        Class to Zip and Hash an addon
    """
    IGNORED_DIRS = ['.git', '.idea', '__MACOSX', '.svn', '.vscode', 'venv', '.github', 'tests']
    IGNORED_FILES = ['.gitignore', '.gitattributes', '.gitkeep', '.github', '.pylintrc', 'requirements.txt']

    def __add_folder_to_zipfile(self, folder, archive: zipfile.ZipFile, relativePath: str):
        for (root, folders, files) in os.walk(folder, topdown=True):
            for file in files:
                if file == os.path.basename(archive.filename):
                    # Do not include the zipfile itself
                    continue
                if file in self.IGNORED_FILES:
                    # Do not include ignored files
                    continue
                archive.write(Utils.joindir(root, file),
                              Utils.joindir(relativePath, file))
            for _folder in folders:
                if _folder in self.IGNORED_DIRS:
                    # Do not include ignored folders
                    continue
                self.__add_folder_to_zipfile(Utils.joindir(root, _folder),
                                             archive,
                                             Utils.joindir(relativePath, _folder))
            break

    @staticmethod
    def create_checksumfile(filename, isBinary):
        """
        Calculates a checksum on filename. Checksum file will be named filename.sha256.
        :param filename: File to calculate checksum on
        :param isBinary: File contains binary data
        :return:
        """
        h256 = sha256()
        # pylint: disable=unspecified-encoding
        with open(filename, 'rb') as file:
            h256.update(file.read())
        hashfileName = filename + '.sha256'

        with open(hashfileName, 'w', newline='\n', encoding='ascii') as f:
            f.write('{0} {1}{2}\n'.format(h256.hexdigest(), '*' if isBinary else ' ', os.path.basename(filename)))

    def zip_and_hash(self, targetZipfile, locationToZip, addonId):
        """
        Function to create zip file and a hash in a hashfile.
        :param targetZipfile: the name of the zipfile to create
        :param locationToZip: the folder that need to be zipped
        :param addonId: the id of the addon
        :return:
        """
        print('Creating zip file {0}'.format(targetZipfile))
        if not os.path.exists(Utils.dirname(targetZipfile)):
            os.makedirs(Utils.dirname(targetZipfile))
        with zipfile.ZipFile(file=targetZipfile, mode='w', compression=zipfile.ZIP_DEFLATED) as archive:
            self.__add_folder_to_zipfile(locationToZip, archive, addonId)
        self.create_checksumfile(targetZipfile, True)
