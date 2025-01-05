import fnmatch
import os
import re
from zipfile import BadZipfile

import config as config_module


class Winnow(object):
    """
    Winnowing algorithm for an input file
    """
    def __init__(self, input_file, normalize_pattern=None):
        """
        Create a new Winnowing algorithm instance for the given file
        :param input_file: Input file to analyze
        :param normalize_pattern: Normalization to apply to the file content
        """
        self.input_file = input_file
        self.normalize_pattern = normalize_pattern


class PlagiarismDetector(config_module.ConfigurationBasedObject):
    def __init__(self, config, environment='prod'):
        """
        Create a new exercise tester and supply the application configuration
        :param config: The configuration passed by the user (may contain a list in decreasing order of priority)
        :param environment: Runtime environment to use as optional suffix to configuration parameters
        """
        # Set default config as config parameters
        super().__init__(config, environment)

    def run(self):
        """
        Process data in all repositories and build documents to search for plagiarisms
        :return: None
        """
        included_files = []
        for item in self.config['plagiarism_detection'].get('files', []):
            included_files.append(re.compile(fnmatch.translate(item)))

        excluded_files = []
        for item in self.config['plagiarism_detection'].get('exclude_files', []):
            excluded_files.append(re.compile(fnmatch.translate(item)))

        for repo in self.repositories:
            if self.config['general']['repo_filter'] and repo.identifier not in self.config['general']['repo_filter']:
                self.logger.info(f"Skipping because Repo {repo} not in filter list")
                continue

            # Download repo content
            if repo.endpoint.require_download_before_update_check():
                repo.download()

            if repo.has_update():
                if not repo.endpoint.require_download_before_update_check():
                    self.logger.debug(f"Late fetching repository {repo}")
                    repo.download()

                # Check if we should unzip the content
                if self.config['general']['unzip_submissions'] and repo.supports_unzip:
                    try:
                        repo.unzip(self.config['general']['remove_archive_after_unzip'])
                    except BadZipfile:
                        self.logger.info(f"Skipping Repo {repo} because of corrupt archive")
                        continue

            filtered_files = repo.files
            if included_files:
                filtered_files = list(filter(lambda f: any([re.match(x, f) for x in included_files]), filtered_files))

            if excluded_files:
                filtered_files = list(filter(lambda f: all([not re.match(x, f) for x in excluded_files]), filtered_files))

            for file in filtered_files:
                # TODO: analyse files
                pass
