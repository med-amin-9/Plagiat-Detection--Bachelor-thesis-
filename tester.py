from __future__ import annotations

import datetime
import re
import logging
import os.path
import csv
import subprocess

import requests
import git
from io import StringIO

from furl import furl

import model
import utils
from config import DEFAULT_CONFIGURATION


class ExerciseTester(object):

    def __init__(self, config):
        """
        Create a new exercise tester and supply the application configuration
        :param config: The configuration passed by the user (may contain a list in decreasing order of priority)
        """
        # Set default config as config parameters
        self.config = {}
        for key in DEFAULT_CONFIGURATION.keys():
            self.config[key] = DEFAULT_CONFIGURATION[key].copy()

        config = utils.ensure_list(config)
        for c in config[::-1]:
            for key in self.config:
                for option in self.config[key]:
                    value = c.get(key, {}).get(option)
                    if value:
                        self.config[key][option] = value

        # Validate config
        self._validate_config()

        # Setup logging
        logging.basicConfig()
        self.logger = logging.getLogger()
        self.logger.setLevel(self.config['logging']['level'])

        # Fetch repos
        self.repositories = self._fetch_targets()

    def run(self) -> None:
        """
        Run the exercises from the referenced repositories in the
        configured docker containers
        """
        d = self.config['source']['directory']
        path = os.path.abspath(d)
        self.logger.info("Run tests in base directory %s", path)

        for repo in self.repositories:
            self.logger.debug("Fetching repository %s", repo)
            repo_path = os.path.join(path, repo.directory)
            if os.path.exists(repo_path):
                self._run_with_existing_path(repo, repo_path)
            else:
                self._run_with_clone(repo, repo_path)

    def _validate_config(self) -> None:
        """
        Test the application config and bail out on invalid setup parameters
        :return: None
        """
        # We need a docker image to run the tests
        if self.config['docker']['image'] is None:
            raise Exception("No docker image specified")

    def _run_with_existing_path(self, repository: model.Repository, path) -> None:
        """
        Run the tests on the given repository
        :param repository: The Repository model describing the remote repository
        :param path: Path where a copy of the repository is stored
        :return: None
        """
        # Validate path
        if not os.path.isdir(path):
            self.logger.error("Path at %s exists but is not a directory", path)
            return

        # Init repo
        self.logger.debug("Process repo %s at %s", repository.url, path)
        repo = git.Repo(path)

        # Update content
        for remote in repo.remotes:
            self.logger.debug("Fetch and pull from remote %s", remote.name)
            remote.fetch()
            remote.pull()

        # Search most recent commit to check
        last_request = None
        last_feedback = None
        for commit in repo.iter_commits():
            if re.search(self.config['git']['commit_message_request_marker'], commit.message) and \
                    (last_request is None or last_request.committed_datetime < commit.committed_datetime):
                last_request = commit

            if re.search(self.config['git']['commit_message_feedback_marker'], commit.message) and \
                    (last_feedback is None or last_feedback.committed_datetime < commit.committed_datetime):
                last_feedback = commit

        if last_request is None:
            self.logger.info("No check request found for this repo.")
            return

        if last_feedback is not None and last_feedback.committed_datetime > last_request.committed_datetime:
            self.logger.info("Feedback commit already present for repo.")
            return

        result = self._check(repository, path)

        # Publish the results
        result_path = os.path.join(path, self.config['git']['report_file'])
        with open(result_path, 'w') as fd:
            fd.write(result)

        # Commit file and push to origin
        repo.index.add(self.config['git']['report_file'])
        message = self.config['git']['feedback_commit_message'].format(commit=last_request)
        commit = repo.index.commit(message)
        self.logger.debug("Created feedback commit %s", commit.hexsha)

        self.logger.debug("Push to remote")
        repo.remote().push()

    def _check(self, repository: model.Repository, path) -> str:
        """
        Perform the test of the given repository path
        :param repository: The Repository model describing the remote repository
        :param path: The path where the source files are stored
        :return: Test result output to publish in the repository
        """
        image = self.config['docker']['image']
        volume = f"{path}:{self.config['docker']['repo_volume_path']}"
        command = ['docker', 'run', '--rm', '--network=none', f'--name="{repository.unique_name}"', '-v', volume, image]

        t_start = datetime.datetime.now()
        try:
            process = subprocess.run(command, capture_output=True, timeout=self.config['docker']['max_runtime'],
                                     check=True, text=True)
            output = process.stdout if process.stdout is not None else ''
            error = process.stderr if process.stderr is not None else ''
            status_message = "Erfolgreich ausgeführt"
            return_code = process.returncode
        except subprocess.TimeoutExpired as e:
            output = e.stdout.decode('utf-8') if e.stdout is not None else ''
            error = e.stderr.decode('utf-8') if e.stderr is not None else ''
            status_message = "Abbruch durch Überschreitung der maximalen Laufzeit"
            return_code = '---'
        except subprocess.CalledProcessError as e:
            output = e.stdout.decode('utf-8') if e.stdout is not None else ''
            error = e.stderr.decode('utf-8') if e.stderr is not None else ''
            status_message = f"Anwendung mit Fehlercode beendet"
            return_code = e.returncode
        finally:
            t_end = datetime.datetime.now()

        runtime = t_end - t_start
        return (f'# Auswertung\n\nErgebnis: {status_message}\nLaufzeit: {runtime.seconds}s\nCode: {return_code}s\n\n'
                f'## Ausgabe\n\n{output}\n\n'
                f'## Fehlerausgabe\n\n{error}\n\n')

    def _run_with_clone(self, repository: model.Repository, path) -> None:
        """
        Clone the repository on the given path and run tests on it
        :param repository: Repository instance
        :param path: repository storage path
        :return: None
        """
        url = furl(repository.url)
        if self.config['git']['username'] and self.config['git']['password'] and not url.username:
            url.username = self.config['git']['username']
            url.password = self.config['git']['password']

        git.Repo.clone_from(url.tostr(), path)
        self._run_with_existing_path(repository, path)

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
        return result

    @staticmethod
    def _read_repositories_from_file_content(content: str) -> list[model.Repository]:
        """
        Read repository information from a CSV file content
        :param content: The File content to process
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
