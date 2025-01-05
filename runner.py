import toml
import sys
import os
import logging
import argparse

from toml import TomlDecodeError

from plagiarism import PlagiarismDetector
from tester import ExerciseTester


def get_configuration_paths(files: list[str]) -> list[str]:
    """
    Returns a list of configuration paths to look for configuration files
    :return: List of paths to check
    """
    configuration_paths = []
    for file in files:
        if os.path.isfile(file):
            configuration_paths.append(file)

    configuration_paths.append(str(os.path.join(os.getcwd(), "exercise-tester.toml")))

    if os.environ.get("HOME", None) is not None:
        configuration_paths.append(os.path.join(os.environ["HOME"], ".exercise-tester.rc"))

    configuration_paths.append("/etc/default/exercise-tester.conf")
    return configuration_paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--environment", help="Runtime environment (prod by default)",
                        default="prod", action="store", type=str)
    parser.add_argument("-p", "--plagiarism", help="Perform plagiarism detection tests",
                        default=False, action="store_true")
    parser.add_argument('config_files', nargs='*')
    arguments = parser.parse_args()

    configs = []
    for configuration_path in get_configuration_paths(arguments.config_files):
        if os.path.isfile(configuration_path):
            try:
                logging.debug(f"Loading configuration from {configuration_path}")
                config = toml.load(configuration_path)
                configs.append(config)
            except TomlDecodeError as tde:
                logging.error("File %s is not a valid toml: %s" %(configuration_path, tde.msg))
                sys.exit(1)

    if not arguments.plagiarism:
        tester = ExerciseTester(configs, arguments.environment)
        if tester.test():
            tester.run()
    else:
        detector = PlagiarismDetector(configs, arguments.environment)
        detector.run()
