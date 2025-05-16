import fnmatch
import os
import re
from zipfile import BadZipfile

import config as config_module

from winnow import robust_winnowing


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

def generate_fingerprints(self, repo):
    """
    Generate fingerprints for each relevant file in a repository using robust winnowing.
    Stores results in repo.fingerprints[filename] = set of hashes.
    """
    # According to Schleimer et al. (SIGMOD 2003), the rule of thumb is:
    #     w = k - t + 1
    # where t is the minimum match length (in characters) that guarantees at least one shared fingerprint.
    #
    # Example: If k = 25 and t = 25 (i.e., an exact match of 25 characters is required), then:
    #     w = 25 - 25 + 1 = 1
    #
    # In practice, we typically use k = 25 and w = 21, which guarantees detection for matches of at least
    # t = k + w - 1 = 45 characters — a value that strikes a good balance between sensitivity and robustness
    # in real-world software projects.
    #
    # For testing purposes, especially with small code snippets where total length is less than 45 characters,
    # smaller values such as k = 5 and w = 4 can be used to ensure the algorithm still produces fingerprints.
     
    k = self.config["plagiarism_detection"].get("k", 25)
    window = self.config["plagiarism_detection"].get("window", 21)
    language = self.config["plagiarism_detection"].get("language", "python")

    repo.fingerprints = {}

    for filename in repo.files:
        try:
            text = repo.read_file(filename)
            fingerprints = robust_winnowing(text, language=language, k=k, window_size=window)
            repo.fingerprints[filename] = fingerprints
        except Exception as e:
            self.logger.warning(f"Error processing {filename} in {repo.identifier}: {e}")
            