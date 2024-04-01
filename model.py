import hashlib

import utils


class Repository(object):
    """
    Class reflecting a repository to test
    """
    def __init__(self, config):
        """
        Parse the given repo configuration
        :param config: repo configu as fetched from config string, parsed input file or remote file
        """
        parsed_configuration = utils.ensure_list(config)
        self._url = parsed_configuration[0]

    @property
    def url(self):
        return self._url

    @property
    def directory(self):
        return 'repo_' + hashlib.md5(self.url.encode()).hexdigest()

    @property
    def unique_name(self):
        return self.directory

    def __repr__(self):
        """
        String representation of the repository
        :return: Output string
        """
        return "Repository(" + self._url + " -> " + self.directory + ")"
