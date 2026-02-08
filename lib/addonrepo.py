"""
    AddonRepo class. Handle zipping and hashing of a Kodi addon
"""
import dataclasses
import os
import shutil
import xml.etree.ElementTree
import zipfile
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse
from xml.dom import minidom

from git import Repo

from lib.utils import Utils, ZipAddon
from lib.config import RepoConfig


# pylint: disable=too-few-public-methods
class AddonRepo:
    """
        Class including functions to zip and hash a Kodi Addon.
    """

    @dataclasses.dataclass
    class MetaData:
        """
            Metadata of addon
        """

        def __init__(self, addonId, root, version):
            self.id = addonId
            self.root = root
            self.version = version

    class RepoSource(Enum):
        """
        Enum type for the different forms of an addon to be processed
        """
        GIT = 1
        FOLDER = 2
        ZIPFILE = 3

    def __init__(self, location, configfile):
        """
        :param location:
            if an url to download from git
                download it to a workdir
                zip the downloaded folder into zipfile
            if folder
                all files for the addon should be in the folder
                zip the given folder into a zipfile
            if it is a zip-file
                extract the zipfile to a workdir
                zip the unzipped folder into a zipfile
        :return:
        """
        self.repoConfig = RepoConfig(configfile)
        self.location = os.path.expanduser(location)
        self.addonXML = ''
        self.metadata = None
        if Utils.is_url(self.location):
            self.addonLocation = self.repoConfig.work_folder()
            self.source = self.RepoSource.GIT
        else:
            if os.path.exists(self.location):
                if  Utils.is_dir(self.location):
                    self.addonLocation = self.location
                    self.source = self.RepoSource.FOLDER
                elif Utils.is_file(self.location):
                    self.addonLocation = self.repoConfig.work_folder()
                    self.source = self.RepoSource.ZIPFILE
                else:
                    raise RuntimeError('Addon not file or folder: {0}'.format(location))
            else:
                raise RuntimeError('Addon not found: {0}'.format(location))

    def __download_addon(self):
        """
        the location is in the form 'repository#branch' so we will split is in two parts
        """
        location, branch = self.__split_giturl()
        url = location
        a = urlparse(url)
        if Path(a.path).suffix == '.git':
            folderName = os.path.basename(Path(a.path).stem)
        else:
            folderName = os.path.basename(Path(a.path))

        if len(location) == 0:
            raise RuntimeError('repository name is empty, invalid url: {0}'.format(self.location))
        self.addonLocation = Utils.joindir(self.addonLocation, folderName)
        if os.path.exists(self.addonLocation):
            Utils.rmtree(self.addonLocation)

        Repo.clone_from(url=location, to_path=self.addonLocation, branch=branch)

        self.__check_addon_folder()

    def __unzip_addon(self):
        folderName = os.path.basename(Path(self.location).stem)
        self.addonLocation = Utils.joindir(self.addonLocation, folderName)
        if os.path.exists(self.addonLocation):
            Utils.rmtree(self.addonLocation)

        with zipfile.ZipFile(self.location, 'r') as zipRef:
            zipRef.extractall(self.addonLocation)

        self.__check_addon_folder()

    def __check_addon_folder(self):
        if not os.path.exists(Utils.joindir(self.addonLocation, 'addon.xml')):
            # Check if it is in a single sub folder
            folders = os.listdir(self.addonLocation)
            if len(folders) != 1:
                raise RuntimeError('Too many folders found while searching for addon.xml')
            subfolder = Utils.joindir(self.addonLocation, folders[0])
            if not os.path.exists(Utils.joindir(subfolder, 'addon.xml')):
                raise RuntimeError('addon.xml not found, this is not a kodi-addon')
            self.addonLocation = subfolder
        self.addonXML = Utils.joindir(self.addonLocation, 'addon.xml')

    def __split_giturl(self):
        repoParts = self.location.split('#')
        gitrepo = ''
        if len(repoParts) >= 1:
            gitrepo = repoParts[0]
        if len(repoParts) == 2:
            gitBranch = repoParts[1]
        else:
            gitBranch = 'master'
        return gitrepo, gitBranch

    def __extract_addon_info(self):
        try:
            tree = xml.etree.ElementTree.parse(self.addonXML)
        except IOError as exc:
            raise RuntimeError(
                'Cannot open add-on metadata: {}'.format(self.addonXML)) from exc
        root = tree.getroot()
        addonId = root.get('id')
        version = root.get('version')
        self.metadata = AddonRepo.MetaData(root=root,addonId=addonId,version=version)

    def __zip_and_hash(self):
        self.__extract_addon_info()
        targetFolder = self.repoConfig.target_folder()
        addonTargetFolder = Utils.joindir(targetFolder, self.metadata.id)
        targetZipfile = Utils.joindir(addonTargetFolder, '{addon}-{version}.zip'.format(addon=self.metadata.id,
                                                                                        version=self.metadata.version))
        zipAddon = ZipAddon()
        zipAddon.zip_and_hash(targetZipfile, self.addonLocation, self.metadata.id)

    def __copy_file(self, sourceName: str, destName: str = None):
        try:
            if destName is None:
                destName = sourceName
            targetdir = Utils.joindir(self.repoConfig.target_folder(), self.metadata.id)
            sourcedir = self.addonLocation
            destFile = Utils.joindir(targetdir, destName)
            if not os.path.exists(Utils.dirname(destFile)):
                os.makedirs(Utils.dirname(destFile))
            shutil.copy(Utils.joindir(sourcedir, sourceName), destFile)
        except IOError:
            pass

    def __copy_additional_files(self):

        xmlFile = self.addonXML

        document = minidom.parse(xmlFile)

        for parent in document.getElementsByTagName('addon'):
            exts = parent.getElementsByTagName('extension')
            for ext in exts:
                point = ext.getAttribute('point')
                if point == 'xbmc.addon.metadata':
                    assets = ext.getElementsByTagName('assets')
                    for asset in assets:
                        icon = asset.getElementsByTagName('icon')
                        if icon[0] is not None:
                            self.__copy_file(icon[0].childNodes[0].data)
                        fanart = asset.getElementsByTagName('fanart')
                        if fanart.length > 0 and fanart[0] is not None:
                            self.__copy_file(fanart[0].childNodes[0].data)
            # Changelog.txt
            self.__copy_file('changelog.txt', 'changelog-' + self.metadata.version + '.txt')

    def process(self):
        """
        Function to download/locate the addon and then zip and hash the addon and copy the additional files
        :return:
        """
        if self.source == self.RepoSource.GIT:
            self.__download_addon()
        elif self.source == self.RepoSource.FOLDER:
            self.__check_addon_folder()
        elif self.source == self.RepoSource.ZIPFILE:
            self.__unzip_addon()
        else:
            raise RuntimeError('Unknown source for addon')

        self.__zip_and_hash()
        self.__copy_additional_files()
