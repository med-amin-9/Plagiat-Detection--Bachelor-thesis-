import csv
import os
from io import StringIO

import requests

import model
from endpoint import EndpointFactory


class Source(object):
    """
    Declares a new source for submissions
    """

    TYPE_GITLAB = "gitlab"
    TYPE_MOODLE = "moodle"
    TYPE_LOCAL_CSV = "local_csv"
    TYPE_REMOTE_CSV = "remote_csv"
    TYPE_SINGLE_SUBMISSION = "submission"

    def __init__(self, url: str, working_directory: str):
        """
        Init a new source with the given url
        Based on the url the source will determine how to fetch submissions
        :param url: URL to use to read submission
        """
        factory = EndpointFactory.get()
        if url.startswith("http") or url.startswith("https"):
            self.type = Source.TYPE_REMOTE_CSV

            # Fetch from http
            response = requests.get(url)
            if response.ok:
                data = response.text
                self.submissions = self._read_submissions_from_csv(data)
            else:
                raise Exception(f"Failed to fetch sources from {url}")

        elif url.startswith('file://'):
            self.type = Source.TYPE_LOCAL_CSV

            path = url[len('file://'):]
            if os.path.isfile(path):
                data = open(path, 'r').read()
                self.submissions = self._read_submissions_from_csv(data)
            else:
                raise Exception(f"Failed to read repositories from file at {path}")

        elif url.startswith('forks://') or url.startswith('gitlab://'):
            self.type = Source.TYPE_GITLAB

            project = url.split("://", 2)[1]
            self.submissions = factory.get_endpoint('gitlab').get_repositories_by_forks(project)

        elif url.startswith('moodle://'):
            self.type = Source.TYPE_MOODLE

            url = url[len('moodle://'):]
            course_name, assignment_name = url.split('/')
            self.submissions = factory.get_endpoint('moodle').get_repositories(course_name, assignment_name)

        else:
            self.type = Source.TYPE_SINGLE_SUBMISSION
            self.submissions = [factory.get_endpoint('gitlab').get_repository_by_clone_url(url)]

        # Set the working directory for all submissions
        for submission in self.submissions:
            submission.working_directory = working_directory

    @staticmethod
    def _read_submissions_from_csv(content: str) -> list[model.Repository]:
        """
        Read repository information from a CSV file content
        :param content: The File content to process
        :return: Parsed models
        """
        # CSV can read only file like objects
        f = StringIO(content)
        reader = csv.reader(f, delimiter=';', quotechar='"', lineterminator='\n')
        factory = EndpointFactory.get()

        # Turn all rows into repo model data
        result = []
        for row in reader:
            url = row[0]
            repository = factory.get_endpoint('gitlab').get_repository_by_clone_url(url)
            result.append(repository)

        return result
