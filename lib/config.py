"""
    Module with configuration classes
"""
import json
import typing

from lib.utils import Utils


class RepoConfig:
    """
        Class to handle repository configuration
    """
    def __init__(self, configFile: str):
        with open(configFile, 'r', encoding='utf-8') as f:
            self.config = json.load(f)['config']
            self.repository = self.config['repository']
            self.locations = self.config['locations']
            self.addonList = self.config['addons']
        self.configdir = Utils.dirname(configFile)

    def repository_id(self):
        """ return repository id """
        return self.repository['id']

    def repository_name(self):
        """ :return repository name """
        return self.repository['name']

    def repository_version(self):
        """ return repository version """
        return self.repository['version']

    def repository_author(self):
        """ return repository author """
        return self.repository['author']

    def summary(self):
        """ return summary """
        return self.repository['summary']

    def description(self):
        """ return description """
        return self.repository['description']

    def url(self):
        """ return url """
        return self.locations['url']

    def target_folder(self):
        """ return targetfolder """
        return Utils.path_append_sep(self.locations['outputfolder'])

    def work_folder(self):
        """ return workfolder """
        return Utils.path_append_sep(self.locations['workfolder'])

    def url_path(self):
        """ return urlpath (to be appended to url) """
        return self.locations['urlpath']

    def addons(self) -> typing.List:
        """ return list of addons to be included in repository """
        addons = self.addonList['addons']
        return json.loads(addons)

    def hash_algo(self):
        """ return hash algorithm to use """
        return self.repository['hash-algorithm']
