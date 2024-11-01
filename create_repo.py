"""
Script to create a repository for Kodi.
The script uses a config.json file to figure out which addon's should be included.

The [repository] section contains the information of the repository itself, such as
    - name
    - version
    - id
    - summary
    - description

The [location] section contains information used durind processing, such as:
    - url to use in the repository from which the addons will be downloaded by Kodi
    - urlpath to append to url
    - outputfolder where the created repository will be created
    - workfolder used for extracting zip files and git repositories.

The [addons] section contains a list of addons to be included. The list can consist of
    - addon-name (folder) to include
    - zip-file in which an addon is included
    - a git repository in the form https://repo-name#<branch>
 """
import xml.etree.ElementTree
import os
import argparse
from lib.addonrepo import AddonRepo
from lib.config import RepoConfig
from lib.utils import Utils, ZipAddon


class Repository:
    """
    A zipped Kodi repository only contains an addon.xml file which points to a remote addons.xml file.
    The remote addons.xml file contains information of all addons/plugins which belong to the repository.
    So we have to perform the following steps:
        create the addon.xml file for the repository
        for each addon
            append info of the addon to the addons.xml file
            create a zip file for the addon
        create a zip file for the repository which only contains the addon.xml file
    """
    CONFIG_DIR = 'config'
    CONFIG_FILE = 'config.json'

    def __init__(self, configfile=CONFIG_FILE):
        self.configdir = self.CONFIG_DIR
        self.configfile = configfile
        self.repoConfig = RepoConfig(Utils.joindir(self.configdir, configfile))

    @staticmethod
    def __save_file(repoXml, file):
        folder = Utils.dirname(file)
        if not os.path.exists(folder):
            os.makedirs(folder)
        with open(file, 'wb') as f:
            try:
                f.write(bytes(repoXml, encoding='utf-8'))
            except IOError:
                print('An error occurred while writing to {0}'.format(file))

    def __create_repo_addon_xml(self, repoFolder, repoId):
        print('Create repository addon')

        with open(Utils.joindir(self.repoConfig.configdir, 'template.xml'), 'r', encoding='utf-8') as f:
            templateXml = f.read()

        repoXml = templateXml.format(
            addonid=self.repoConfig.repository_id(),
            name=self.repoConfig.repository_name(),
            version=self.repoConfig.repository_version(),
            author=self.repoConfig.repository_author(),
            summary=self.repoConfig.summary(),
            description=self.repoConfig.description(),
            url=self.repoConfig.url(),
            urlpath=self.repoConfig.url_path(),
            hashalgo=self.repoConfig.hash_algo()
        )
        addonXmlFilename = Utils.joindir(repoFolder + repoId, 'addon.xml')
        self.__save_file(repoXml, addonXmlFilename)

    def create(self):
        """
        Function to create the repository and addon zipfiles
        :return:
        """
        self.__create_repo_addon_xml(self.repoConfig.work_folder(), self.repoConfig.repository_id())
        folderToZip = self.repoConfig.work_folder() + self.repoConfig.repository_id()

        self.repoConfig.addonList.append(folderToZip)

        # Generate the addons.xml file while creating the zip files .
        root = xml.etree.ElementTree.Element('addons')

        for addon in self.repoConfig.addonList:
            addon = AddonRepo(addon, Utils.joindir(self.configdir, self.configfile))
            addon.process()
            root.append(addon.metadata.root)
        tree = xml.etree.ElementTree.ElementTree(root)

        if not os.path.exists(self.repoConfig.target_folder()):
            os.makedirs(self.repoConfig.target_folder())

        with open(Utils.joindir(self.repoConfig.target_folder(), 'addons.xml'), 'wb') as infoFile:
            tree.write(infoFile, encoding='UTF-8', xml_declaration=True)
        ZipAddon.create_checksumfile(infoFile.name, False)

    def clean_work_folder(self):
        """
        Clean the work folder.
        :return:
        """
        if os.path.exists(self.repoConfig.work_folder()):
            Utils.rmtree(self.repoConfig.work_folder())

    def clean(self):
        """
            Before we start, we will clean the targetFolder and the workfolder
        """
        if os.path.exists(self.repoConfig.target_folder()):
            Utils.rmtree(self.repoConfig.target_folder())
        self.clean_work_folder()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # Adding optional arguments
    parser.add_argument("-c", "--config-file",
                        help="name of config file, default: config.json",
                        default='config.json')
    args = parser.parse_args()
    repo = Repository(args.config_file)
    repo.clean()
    repo.create()
    repo.clean_work_folder()
