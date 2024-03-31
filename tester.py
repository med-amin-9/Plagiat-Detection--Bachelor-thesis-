import logging
import os.path
import csv
import requests
from io import StringIO

import model
import utils
from config import DEFAULT_CONFIGURATION


class ExerciseTester(object):

    def __init__(self, config):
        """
        Create a new exercise tester and supply the application configuration
        :param config: The configuration passed by the user
        """
        self.config = {}
        for key in DEFAULT_CONFIGURATION.keys():
            sub_config = config.get(key, {})
            processed_config = DEFAULT_CONFIGURATION[key].copy()
            processed_config.update(sub_config)
            self.config[key] = processed_config

        # Setup logging
        logging.basicConfig()
        self.logger = logging.getLogger()
        self.logger.setLevel(self.config['logging']['level'])

        # Fetch repos
        self.repositories = self._fetch_targets()

    def _fetch_targets(self) -> list[model.Repository]:
        """
        Fetches the list of repositories to process during execution
        :return:
        """
        sources = utils.ensure_list(self.config['source']['repositories'])
        if len(sources) == 0:
            raise Exception("No repository sources configured in source->repositories")

        repositories = []
        for source in sources:
            self.logger.debug("Processing source: %s", source)
            if source.startswith('http://') or source.startswith('https://'):
                # Fetch from http
                response = requests.get(source)
                if response.ok:
                    data = response.text
                    repositories += self._read_repositories_from_file_content(data)
                else:
                    self.logger.error("Failed to fetch repositories from %s", source)

            elif source.startswith('file://'):
                path = source[len('file://'):]
                if os.path.isfile(path):
                    data = open(path, 'r').read()
                    repositories += self._read_repositories_from_file_content(data)
                else:
                    self.logger.error("Failed to read repositories from file at %s", path)

            else:
                repository = model.Repository(source)
                repositories.append(repository)

        # Filter invalid repositories
        result = list(filter(lambda repo: repo is not None, repositories))
        self.logger.debug("Found %d repositories: %s", len(result), result)

    @staticmethod
    def _read_repositories_from_file_content(content: str) -> list[model.Repository]:
        """
        Read repository information from a CSV file content
        :param content: Content to process
        :return: Parsed models
        """
        # CSV can read only file like objects
        f = StringIO(content)
        reader = csv.reader(f, delimiter=';', quotechar='"', lineterminator='\n')

        # Turn all rows into repo model data
        result = []
        for row in reader:
            repository = model.Repository(row)
            result.append(repository)

        return result
