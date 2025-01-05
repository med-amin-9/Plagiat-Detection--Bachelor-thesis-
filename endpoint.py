import typing
from zipfile import ZipFile

import markdown
import requests
import urllib.parse
import logging
import os
import git
import re
import shutil

from furl import furl
from git import GitCommandError

import utils
import config
import model


class Endpoint(object):
    """
    Generic endpoint base class
    """

    def __init__(self, configuration: dict[str, typing.Any], defaults: dict[str, typing.Any]) -> None:
        """
        Set up the endpoint to prepare is for execution
        :param configuration: Endpoint configuration dictionary
        :param defaults: Default configuration to apply
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.getLogger().level)

        self.configuration = configuration
        for key, value in defaults.items():
            self.configuration.setdefault(key, value)

        self.validate_configuration()

    def validate_configuration(self) -> None:
        """
        Give derived classes the opportunity to validate configuration options
        :return: None
        """
        pass

    def get_current_grade(self, repository: model.Repository):
        """
        Return the current grade of the repository
        :param repository: Repository to return the last grading for
        :return: Grading as a float number or None if no last grading could be found
        """
        return None

    @staticmethod
    def require_download_before_update_check() -> bool:
        """
        Check if the repository must be downloaded via the endpoint before an update can be checked
        :return: true if the repository requires download before an update check can be performed
        """
        return False


class LocalEndpoint(Endpoint):
    """
    Defines local repositories
    """
    def __init__(self) -> None:
        """
        Set up the local endpoint
        """
        super().__init__({}, {})

    def get_repository_with_path(self, path: str) -> model.Repository:
        """
        Create a repository model for a local path
        :param path: Path where the project is stored
        :return: Model repository
        """
        return model.Repository(self, path, {"path": path})

    def download(self, repository: model.Repository):
        """
        Download the given repository
        :param repository: Repository model for a git repository to be downloaded
        :return: None
        """
        if os.path.exists(repository.path) and self.has_update(repository):
            # Remove the old content
            self.logger.info("Remove existing data in path %s", repository.path)
            shutil.rmtree(repository.path)

        path = repository.data.get("path")
        for root, dirs, files in os.walk(path):
            sub_dir = root[len(path):]
            destination_path = os.path.normpath(repository.path + os.path.sep + sub_dir)
            os.makedirs(destination_path, exist_ok=True)
            for file in files:
                shutil.copyfile(os.path.join(root, file), os.path.join(destination_path, file))

    @staticmethod
    def has_update(repository: model.Repository) -> bool:
        """
        Check if the given repository has a new submission to check
        :param repository: Repository to test
        :return: true if updates are available a new test should be performed
        """
        return True

    def submit_grade(self, repository: model.Repository, grade: int, message: str):
        """
        Save grading information to the given repository
        :param repository: Repository to save grading information to
        :param grade: Grade (should be in range of 0 - 100)
        :param message: Grading details message
        :return: None
        """

        self.logger.warning(f"Submitting grading {grade}/100 for local repository {repository.identifier}")
        self.logger.warning(message)

    @property
    def supports_unzip(self) -> bool:
        """
        Indicator if this endpoint supports unzipping content
        :return: True if the endpoint supports unzipping content
        """
        return False


class GitlabEndpoint(Endpoint):
    """
    Defines an endpoint to a gitlab instance
    """

    def __init__(self, configuration: dict[str, typing.Any]) -> None:
        """
        Set up the gitlab endpoint
        :param configuration: endpoint configuration: Supported keys are
            uri: URI to use as base for requests
            username: Username to use for authentication when pulling from the repo
            password: Password to use if username is given
            report_file: Name of the file where the generated test report is written to
            commit_message_request_marker: Text to look for in commit messages to detect commits requested for testing
            commit_message_feedback_marker: Text to look for in commit messages to detect generated feedback commits
            feedback_commit_message: Message to use as commit message when publishing results
        """
        super().__init__(configuration, config.DEFAULT_CONFIGURATION.get('git', {}))

    def validate_configuration(self) -> None:
        assert self.configuration['uri'] is not None

    @staticmethod
    def require_download_before_update_check() -> bool:
        return True

    def get_repositories_by_forks(self, project_name: str) -> list[model.Repository]:
        """
        Read gitlab projects that were forked from the given root project living at the given url
        :param project_name: Project to fetch forks from
        :return: Forked project submissions
        """
        project_endpoint = self._get_project_endpoint(project_name)
        project = self._get_project(project_name)

        num_forks = project.get('forks_count', 0)
        page_size = self.configuration['page_size']
        result = []
        for page in range(1, num_forks // page_size + 2):
            params = {"per_page": page_size, "page": page}
            response = requests.get(f"{project_endpoint}/forks", headers=self.headers, params=params)
            if not response.ok:
                raise Exception(response.text)

            for repo in response.json():
                result.append(model.Repository(self, repo['http_url_to_repo'], repo))

        return result

    def get_repository_by_clone_url(self, url: str) -> model.Repository:
        """
        Return the repository model instance associated with the given git pull url
        :param url: git clone url of the project to check out
        :return: Repository identifying the project
        """
        if url.startswith('git@'):
            project_name = url.split(":", 2)[1]
        elif url.startswith(self.configuration['uri']):
            project_name = url[len(self.configuration['uri']):]
            if project_name.startswith("/"):
                project_name = project_name[1:]
        else:
            raise ValueError(f"Invalid git pull url: {url}")

        # Fetch project
        project = self._get_project(project_name)
        return model.Repository(self, project['http_url_to_repo'], project)

    def _get_project_endpoint(self, project: str) -> str:
        """
        Get he API endpoint to get project data
        :param project: Project name
        :return: API endpoint
        """
        return f"{self.api_endpoint}/projects/{urllib.parse.quote(project, safe='')}"

    def _get_project(self, project: str):
        """
        Read project information from the rest API
        :param project: Project to fetch data for
        :return: Project information read from gitlab instance
        """
        project_endpoint = self._get_project_endpoint(project)
        response = requests.get(project_endpoint, headers=self.headers)
        if not response.ok:
            raise Exception(response.text)
        else:
            return response.json()

    def download(self, repository: model.Repository):
        """
        Download the given repository
        :param repository: Repository model for a git repository to be downloaded
        :return: None
        """
        self.logger.debug(f"Fetching repository {repository.identifier}")
        if os.path.exists(repository.path):
            try:
                self._pull(repository)
            except GitCommandError as gce:
                self.logger.warning(f"Pull of repository did fail with {gce}. Will try a fresh clone and remove {repository.path}")
                shutil.rmtree(repository.path)
                self._clone(repository)
        else:
            self._clone(repository)

    def _pull(self, repository: model.Repository) -> None:
        """
        Update the given repository
        :param repository: The Repository model describing the remote repository
        :return: None
        """
        # Validate path
        assert os.path.isdir(repository.path)

        # Update repo
        url = repository.data.get("http_url_to_repo")
        self.logger.debug(f"Fetch and pull repo {url} at {repository.path}")
        repo = git.Repo(repository.path)
        repo.git.reset('--hard', 'origin/HEAD')

        untracked_file_directories = set()
        for file in repo.untracked_files:
            p = os.path.join(repo.working_dir, file)
            os.remove(p)
            untracked_file_directories.add(os.path.dirname(file))

        for directory in untracked_file_directories:
            if not directory:
                continue

            p = os.path.join(repo.working_dir, directory)
            if os.path.isdir(p) and len(os.listdir(p)) == 0:
                os.rmdir(p)

        # Update content
        for remote in repo.remotes:
            self.logger.debug(f"Fetch and pull from remote {remote.name}")
            remote.fetch()
            remote.pull()

    def _clone(self, repository: model.Repository) -> None:
        """
        Clone the repository on the given path and run tests on it
        :param repository: Repository instance
        :return: None
        """
        url = furl(repository.data.get("http_url_to_repo"))
        self.logger.debug(f"Clone repo from {url} to {repository.path}")
        if self.configuration['username'] and self.configuration['password'] and not url.username:
            url.username = self.configuration['username']
            url.password = self.configuration['password']

        git.Repo.clone_from(url.tostr(), repository.path)

    def has_update(self, repository: model.Repository) -> bool:
        """
        Check if the given repository has a new submission to check
        :param repository: Repository to test
        :return: true if updates are available a new test should be performed
        """
        # Search most recent commit to check
        repo = git.Repo(repository.path)

        last_request_marker = self.configuration['commit_message_request_marker']
        last_request = GitlabEndpoint._get_last_feedback_with_marker(repo, last_request_marker)
        last_feedback_marker = self.configuration['commit_message_feedback_marker']
        last_feedback = GitlabEndpoint._get_last_feedback_with_marker(repo, last_feedback_marker)

        if last_request is None:
            self.logger.debug(f"No check request found for repo at {repository.identifier}.")
            return False

        elif last_feedback is not None and last_feedback.committed_datetime > last_request.committed_datetime:
            self.logger.debug(f"Feedback commit already present for repo at {repository.identifier}.")
            return False

        else:
            return True

    @staticmethod
    def _get_last_feedback_with_marker(repository: git.Repo, marker: str) -> git.Commit:
        """
        Find the most recent commit that has the given marker in the commit message
        :param repository: Git Repository to look for commits
        :param marker: Marker in the commit message to look for
        :return: Matched latest commit or None if none was found
        """
        result = None
        for commit in repository.iter_commits():
            if (re.search(marker, commit.message) and
                    (result is None or result.committed_datetime < commit.committed_datetime)):
                result = commit

        return result

    def submit_grade(self, repository: model.Repository, grade: int, message: str):
        """
        Save grading information to the given repository
        :param repository: Repository to save grading information to
        :param grade: Grade (should be in range of 0 - 100)
        :param message: Grading details message
        :return: None
        """
        # Publish the results
        result_path = os.path.join(repository.path, self.configuration['report_file'])
        with open(result_path, 'w') as fd:
            file_content = self.configuration['grading_file_template'].format(grade=grade, message=message)
            fd.write(file_content)

        repo = git.Repo(repository.path)

        # Find the commit the grading is related to
        last_request_marker = self.configuration['commit_message_request_marker']
        last_request = GitlabEndpoint._get_last_feedback_with_marker(repo, last_request_marker)

        # Commit file and push to origin
        repo.index.add(self.configuration['report_file'])
        message = self.configuration['feedback_commit_message'].format(commit=last_request)
        commit = repo.index.commit(message)
        self.logger.debug("Created feedback commit %s", commit.hexsha)

        self.logger.debug("Push to remote")
        repo.remote().push()

    @property
    def api_endpoint(self) -> str:
        """
        Return the API endpoint URI
        :return: uri
        """
        return f"{self.configuration['uri']}/api/v4/"

    @property
    def headers(self) -> dict[str, str]:
        """
        REST API request headers
        :return: Headers dictionary
        """
        return {'PRIVATE-TOKEN': self.configuration['password']}

    @property
    def supports_unzip(self) -> bool:
        """
        Indicator if this endpoint supports unzipping content
        :return: True if the endpoint supports unzipping content
        """
        return False


class MoodleEndpoint(Endpoint):
    """
    Defines an endpoint to a moodle instance
    """

    ASSIGNMENT_TYPE = "assign"
    FILE_PLUGIN_TYPE = "file"
    ACCEPTED_SUBMISSION_STATUS = ["submitted"]
    REOPENED_SUBMISSION_STATUS = ["reopened"]

    def __init__(self, configuration: dict[str, typing.Any]) -> None:
        """
        Set up the moodle endpoint
        :param configuration: endpoint configuration: Supported keys are
            username: Username to use for authentication when accessing moodle
            password: Password to use for username
        """
        super().__init__(configuration, config.DEFAULT_CONFIGURATION.get('moodle', {}))

        # Fetch authentication token
        token_endpoint = f"{self.api_endpoint}/login/token.php"
        params = {
            "username": self.configuration['username'],
            "password": self.configuration['password'],
            "service": self.configuration['service']
        }
        result = requests.get(token_endpoint, params=params)
        if not result.ok or not result.json().get('token'):
            raise Exception(result.text)

        self.token = result.json().get('token')

        # Fetch authenticated user information
        user_info = self._call('GET', 'core_webservice_get_site_info')
        if not user_info:
            raise Exception("Failed to get user id from endpoint")

        self.user_id = user_info.get('userid')

    @property
    def api_endpoint(self) -> str:
        """
        Return the API endpoint URI
        :return: uri
        """
        return self.configuration['uri']

    @property
    def supports_unzip(self) -> bool:
        """
        Indicator if this endpoint supports unzipping content
        :return: True if the endpoint supports unzipping content
        """
        return True

    def get_current_grade(self, repository: model.Repository):
        """
        Return the current grade of the repository
        :param repository: Repository to return the last grading for
        :return: Grading as a float number or None if no last grading could be found
        """
        try:
            submission = repository.data['submission']
            status = submission.get('gradingstatus', 'notgraded')
            if status == 'graded' and submission.get('grade') is not None:
                return float(submission.get('grade', '0'))
        except ValueError:
            pass

        return None

    def validate_configuration(self) -> None:
        assert self.configuration['uri'] is not None
        assert self.configuration['username'] is not None
        assert self.configuration['password'] is not None

    def get_repositories(self, course_name: str, assignment_name: str) -> list[model.Repository]:
        """
        Read moodle submissions from the given course and assignment
        :param course_name: shortname of the course to fetch submissions from
        :param assignment_name: name of the assignment to fetch submissions from
        :return: assignment submission repositories
        """
        # Fetch course info
        courses = self._call('GET', 'core_enrol_get_users_courses', {'userid': self.user_id})
        if not courses:
            raise Exception("Failed to get courses from endpoint")

        course = next((x for x in courses if x.get("shortname") == course_name), None)
        if not course:
            raise Exception(f"Could not get course {course_name} in list of user courses")

        # Fetch the desired assignment
        course_id = course.get("id")
        course_content = self._call('GET', 'core_course_get_contents', {'courseid': course_id})
        if not courses:
            raise course_content(f"Could not get course content of {course_name}")

        assignment_module = None
        for item in course_content:
            for module in item.get("modules", []):
                if module.get("modname") == MoodleEndpoint.ASSIGNMENT_TYPE and module.get("name") == assignment_name:
                    assignment_module = module
                    break

        if not assignment_module:
            raise Exception(f"Could not get assignment {assignment_name} in {course_name}")

        # Fetch submissions
        assignment_id = assignment_module.get("instance")
        module_submissions = self._call('GET', 'mod_assign_get_submissions', {'assignmentids[0]': assignment_id})
        if (not module_submissions
                or module_submissions.get("assignments") is None
                or len(module_submissions.get("assignments")) != 1):
            raise Exception(f"Could not get submissions for assignment {assignment_name} in {course_name}")

        assignment = module_submissions["assignments"][0]
        result = []
        for submission in assignment.get("submissions", []):
            submission_status = submission.get("status")
            userid = submission.get("userid")
            if (self.configuration.get("use_previous_attempt_for_reopened_submissions", False) and
                    submission_status in self.REOPENED_SUBMISSION_STATUS):
                self.logger.debug(f"Submission {submission.get('id')} is reopened. Search last submitted one.")

                user_submissions = self._call('GET', 'mod_assign_get_submission_status',
                                              {'userid': userid, 'assignid': assignment_id})

                attempts = filter(lambda x: x.get('submission', {}).get('status') in self.ACCEPTED_SUBMISSION_STATUS,
                                  user_submissions.get("previousattempts", []))
                try:
                    attempt = max(attempts, key=lambda x: x.get('attemptnumber'))
                    submission = attempt.get('submission')
                    self.logger.debug(f"Selected last submitted submission {submission.get('id')}.")
                except ValueError:
                    self.logger.debug(f"No other submitted attempt found")
                    continue

                try:
                    grading = attempt.get('grade')
                    if grading is not None and grading.get('grade') is not None:
                        submission['gradingstatus'] = 'graded'
                        submission['grade'] = float(grading['grade'])
                except ValueError:
                    self.logger.debug(f"No grade for submission found")
                    submission['gradingstatus'] = 'notgraded'

            elif submission_status not in self.ACCEPTED_SUBMISSION_STATUS:
                self.logger.debug(f"Skip Submission as it is not in recognized state but in state {submission_status}")
                continue

            else:
                # try to find up to date grading
                user_submissions = self._call('GET', 'mod_assign_get_submission_status',
                                              {'userid': userid, 'assignid': assignment_id})
                grade = user_submissions.get('feedback', {}).get('grade', {}).get('grade', 0)
                try:
                    submission['grade'] = float(grade)
                except ValueError:
                    self.logger.debug(f"Failed to read grade for already graded submission")
                    submission['grade'] = False

            # Check if there are files in the submission
            files = self._get_files(submission)
            if len(files) == 0:
                self.logger.debug(f"Skip Submission as it does not contain any files")
                continue

            data = {
                "course": course,
                "assignment": assignment,
                "submission": submission
            }
            identifier = f"{course_name}/{assignment_name}/{submission.get('id')}"
            result.append(model.Repository(self, identifier, data))

        return result

    def _call(self, method, function, parameters: dict[str, typing.Any] = None):
        """
        Invoke the given moodle API method and return the JSON result
        :param method: HTTP method to use
        :param function: webservice function name to call
        :param parameters: List of parameters to pass
        :return: unpacked json object
        :exception Exception: If an error occurs communicating with the moodle service
        """
        endpoint = f"{self.api_endpoint}/webservice/rest/server.php"
        params = {
            "wstoken": self.token,
            "moodlewsrestformat": "json",
            "wsfunction": function
        }

        if parameters is not None:
            params.update(parameters)

        if method == 'GET':
            result = requests.get(endpoint, params=params)
        else:
            result = requests.request(method, endpoint, data=params)

        if not result.ok:
            raise Exception(result.text)

        return result.json()

    def download(self, repository: model.Repository):
        """
        Download the given repository
        :param repository: Repository model for a git repository to be downloaded
        :return: None
        """
        self.logger.debug(f"Fetching moodle submission {repository}")
        if os.path.exists(repository.path) and self.has_update(repository):
            # Remove the old content
            self.logger.info("Remove existing data in path %s", repository.path)
            shutil.rmtree(repository.path)

        # Fetch files for the repository
        submission = repository.data['submission']
        files = self._get_files(submission)

        for file in files:
            destination_path = os.path.normpath(repository.path + file.get('filepath'))
            os.makedirs(destination_path, exist_ok=True)
            destination = os.path.join(destination_path, file.get('filename'))

            url = file.get("fileurl")
            self.logger.debug(f"Downloading {url} to {destination}")
            with requests.get(url, params={"token": self.token}, stream=True) as request:
                request.raise_for_status()
                with open(destination, 'wb') as f:
                    for chunk in request.iter_content(chunk_size=8192):
                        f.write(chunk)

    @staticmethod
    def _get_files(submission):
        """
        Extract all files from the given submission
        :param submission: Submission to look for files in the file plugin
        :return: List of file data structures
        """
        files = []
        for plugin in submission.get("plugins", []):
            if plugin.get("type") != MoodleEndpoint.FILE_PLUGIN_TYPE:
                continue

            for file_area in plugin.get("fileareas", []):
                files += file_area.get("files", [])

        return files

    @staticmethod
    def has_update(repository: model.Repository) -> bool:
        """
        Check if the given repository has a new submission to check
        :param repository: Repository to test
        :return: true if updates are available a new test should be performed
        """
        updated_at = repository.data['submission'].get('timemodified')
        last_grading = repository.metadata.get(repository.MODIFIED_AT_METADATA_KEY)
        return last_grading is None or last_grading < updated_at

    def unzip(self, repository: model.Repository, remove_archive: bool):
        """
        Unzip the given repository if it contains only one file in zip format
        :param repository: Repository to unzip content for
        :param remove_archive: Boolean indicating if the source archive should be deleted after unzipping content
        :return: None
        """
        submission = repository.data['submission']
        files = self._get_files(submission)
        if len(files) == 1 and files[0].get('mimetype') == 'application/zip':
            file = files[0]
            directory = os.path.normpath(repository.path + file.get('filepath'))
            zip_file_path = directory + os.path.sep + file.get('filename')
            zip_file = ZipFile(zip_file_path)

            members = []
            for member in zip_file.filelist:
                # Skip directories - they are included by default
                if member.is_dir():
                    continue

                parts = member.filename.split(os.path.sep)
                if not any([x.startswith("__") or x.startswith(".") for x in parts]):
                    members.append(member)

            remove_toplevel_directory = False
            directories = set()
            for member in members:
                dir_name = member.filename.split(os.path.sep)[0]
                directories.add(dir_name)

            # Check if only one directory was found and the found directory is not the empty string
            if len(directories) == 1 and all(directories):
                remove_toplevel_directory = True

            for member in members:
                if remove_toplevel_directory:
                    member_path = os.path.join(*os.path.split(member.filename)[1:])
                else:
                    member_path = os.path.join(member.filename)

                d = os.path.dirname(member_path)
                if d:
                    destination = os.path.join(repository.path, d)
                    os.makedirs(destination, exist_ok=True)
                else:
                    destination = repository.path

                with zip_file.open(member) as in_fd:
                    with open(os.path.join(destination, os.path.basename(member.filename)), 'wb') as out_fd:
                        out_fd.write(in_fd.read())

            zip_file.close()

            if remove_archive:
                os.remove(zip_file_path)

    def submit_grade(self, repository: model.Repository, grade: int, message: str):
        """
        Save grading information to the given repository by submitting it to the moodle platform
        :param repository: Repository to save grading information to
        :param grade: Grade (should be in range of 0 - 100)
        :param message: Grading details message
        :return: None
        """
        # Publish the results
        assignment_id = repository.data['assignment'].get('assignmentid')
        user_id = repository.data['submission'].get('userid')
        # attempt = repository.data['submission'].get('attemptnumber', -1)
        attempt = -1
        add_attempt = False

        html_message = markdown.markdown(message)
        params = {
            "assignmentid": assignment_id,
            "userid": user_id,
            "attemptnumber": attempt,
            "grade": grade,
            "addattempt": "1" if add_attempt else "0",
            "workflowstate": "graded",
            "applytoall": "0",
            "plugindata[assignfeedbackcomments_editor][text]": html_message,
            "plugindata[assignfeedbackcomments_editor][format]": "1"
        }

        self.logger.debug(f"Submitting grading {grade}/100 for {repository.identifier}")
        self._call('POST', 'mod_assign_save_grade', params)


class EndpointFactory(object, metaclass=utils.Singleton):
    """
    Defines an endpoint factory to request access to different endpoints
    """

    TYPE_GITLAB = "git"
    TYPE_MOODLE = "moodle"
    TYPE_LOCAL = "local"

    def __init__(self):
        self.endpoints = {}

    def register_endpoint(self, name: str, endpoint_type: str, configuration: dict[str, typing.Any]) -> None:
        """
        Registers a new endpoint for the given name
        :param name: endpoint register name
        :param endpoint_type: Type of the endpoint
        :param configuration: Endpoint configuration
        :return: None
        """
        if endpoint_type == EndpointFactory.TYPE_GITLAB:
            self.endpoints[name] = GitlabEndpoint(configuration)
        elif endpoint_type == EndpointFactory.TYPE_MOODLE:
            self.endpoints[name] = MoodleEndpoint(configuration)
        elif endpoint_type == EndpointFactory.TYPE_LOCAL:
            self.endpoints[name] = LocalEndpoint()
        else:
            raise ValueError(f"Unsupported endpoint type: {endpoint_type}")

    def get_endpoint(self, name: str) -> Endpoint:
        return self.endpoints[name]

    def __getitem__(self, name: str) -> Endpoint:
        return self.endpoints[name]

    @staticmethod
    def get():
        return EndpointFactory()
