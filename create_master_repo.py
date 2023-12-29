import gzip
import sys
import traceback
import typing
import zipfile
import shutil
from xml.dom import minidom
import os
import json

import requests
from configparser import ConfigParser

__version__ = '1.0.0'

import argparse

# Ignored files and folders:
ignored_dirs = ['.git', '.idea', '__MACOSX', '.svn', '.vscode', 'venv']
ignored_files = ['.gitignore', 'gitattributes', '.gitkeep', '.github']


def pathAppendSep(path: str) -> str:
    if path[-1] == '/' or path[-1] == os.sep:
        return path
    else:
        return path + '/'


class RepoConfig:
    def __init__(self, config_file: str):
        self.toolsdir = pathAppendSep(os.path.dirname(config_file))  # Always ends with '/'
        self.config = ConfigParser()
        self.config.read(config_file)

    def repositoryId(self):
        return self.config.get('addon', 'id')

    def repositoryName(self):
        return self.config.get('addon', 'name')

    def repositoryVersion(self):
        return self.config.get('addon', 'version')

    def repositoryAuthor(self):
        return self.config.get('addon', 'author')

    def summary(self):
        return self.config.get('addon', 'summary')

    def description(self):
        return self.config.get('addon', 'description')

    def url(self):
        return self.config.get('locations', 'url')

    def targetFolder(self):
        return pathAppendSep(self.config.get('locations', 'outputfolder'))

    def urlPath(self):
        return self.config.get('locations', 'urlpath')

    def addons(self) -> typing.List:
        addons = self.config.get('addons', 'addons')
        return json.loads(addons)


class Generator:

    def __init__(self, config: RepoConfig):
        self.repoConfig = config
        self.output = pathAppendSep(self.repoConfig.targetFolder())
        self.repoId = self.repoConfig.repositoryId()
        self.addons: typing.List = self.repoConfig.addons()
        self.__create_temp_repository()
        try:
            self.__generate_repositories()
            self.__copy_additional_files()
        except Exception as exc:
            tb = traceback.format_exc()
            print('Exception during creation of repositories')
            print(tb)
        self.__remove_temp_repository()

    def __copy_file(self, folder: str, sourceName: str, destName: str = None):
        try:
            if destName is None:
                destName = sourceName
            targetdir = os.path.dirname(self.output + folder + destName)
            if not os.path.exists(targetdir):
                os.makedirs(targetdir)
            shutil.copy(folder + sourceName, self.output + folder + destName)
        except IOError:
            pass

    def __copy_additional_files(self):

        # os.chdir(os.path.abspath(os.path.join(self.repoId, os.pardir)))

        for folder in self.addons:

            folder = pathAppendSep(folder)
            xml_file = os.path.join(folder, 'addon.xml')

            if not os.path.isfile(xml_file):
                continue
            if not (os.path.isdir(folder) or folder in ignored_dirs):
                continue

            document = minidom.parse(xml_file)

            for parent in document.getElementsByTagName('addon'):
                version = parent.getAttribute('version')
                exts = parent.getElementsByTagName('extension')
                for ext in exts:
                    point = ext.getAttribute('point')
                    if point == 'xbmc.addon.metadata':
                        assets = ext.getElementsByTagName('assets')
                        for asset in assets:
                            icon = asset.getElementsByTagName('icon')
                            if icon[0] is not None:
                                self.__copy_file(folder, icon[0].childNodes[0].data, icon[0].childNodes[0].data)
                            fanart = asset.getElementsByTagName('fanart')
                            if fanart[0] is not None:
                                self.__copy_file(folder, fanart[0].childNodes[0].data, fanart[0].childNodes[0].data)
                # Changelog.txt
                self.__copy_file(folder, 'changelog.txt', 'changelog-' + version + '.txt')

    def __generate_repo_files(self, folder):

        print("Create repository addon")

        with open(self.repoConfig.toolsdir + "template.xml", "r") as f:
            template_xml = f.read()

        repo_xml = template_xml.format(
            addonid=self.repoConfig.repositoryId(),
            name=self.repoConfig.repositoryName(),
            version=self.repoConfig.repositoryVersion(),
            author=self.repoConfig.repositoryAuthor(),
            summary=self.repoConfig.summary(),
            description=self.repoConfig.description(),
            url=self.repoConfig.url(),
            urlpath=self.repoConfig.urlPath()
        )

        # save file
        if not os.path.exists(folder):
            os.makedirs(folder)
        else:
            raise Exception('Folder {0} already exists, cannot continue.'.format(folder))

        filename = folder + os.path.sep + "addon.xml"
        self.__save_file(repo_xml, file=filename)

    def __create_temp_repository(self):
        #  create folder if it does not exist
        folder = pathAppendSep(self.repoId)
        self.__generate_repo_files(folder)

    def __remove_temp_repository(self):
        folder = pathAppendSep(self.repoId)
        shutil.rmtree(folder)

    @staticmethod
    def __save_file(repo_xml, file):
        with open(file, "wb") as f:
            try:
                f.write(bytes(repo_xml, encoding='utf-8'))
            except IOError:
                print('An error occured while writing to {0}'.format(file))

    def __generate_repositories(self):
        # First we download the create_repository script mentioned in the Kodi documentation. See:
        # https://kodi.wiki/view/Add-on_repositories Script URL:
        # https://raw.githubusercontent.com/chadparry/kodi-repository.chad.parry.org/master/tools/create_repository.py
        URL = ('https://raw.githubusercontent.com/chadparry/kodi-repository.chad.parry.org/master/tools'
               '/create_repository.py')
        response = requests.get(URL)
        script = os.path.join(self.repoConfig.toolsdir, 'create_repository.py')
        if not response.ok:
            if not os.path.exists(script):
                raise Exception('Failed to download create_repository script : {0}'.format(URL))
            else:
                print('Fallback to already existing script.')
        else:
            with open(os.path.join(script), 'wb') as f:
                f.write(response.content)
        script = script.replace('/', os.sep)
        addons = 'repository.ziggotv'
        for addon in self.repoConfig.addons():
            addons = addons + ' ' + addon
        targetFolder = pathAppendSep(self.repoConfig.targetFolder())
        if not os.path.exists(targetFolder):
            os.makedirs(targetFolder)
        retval = os.system(sys.executable + ' ' + script + ' --datadir ' + targetFolder + ' ' + addons)
        if retval == 0:
            print('Repositories successfully created')
        else:
            raise Exception('Unsuccessful return-code {0} during creation of repositories'.format(retval))


def main():
    print('Repository creator script, version: {0}'.format(__version__))

    parser = argparse.ArgumentParser(
        description='Create a Kodi master add-on repository from add-on sources')
    parser.add_argument(
        '--tooldir',
        '-t',
        default='.',
        help='Path to folder containing template.xml and config.ini [current directory]')
    args = parser.parse_args()
    config = RepoConfig(os.path.basename(os.path.abspath(args.tooldir)) + os.sep + 'config.ini')

    Generator(config)


if __name__ == "__main__":
    main()
