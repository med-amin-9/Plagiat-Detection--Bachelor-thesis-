import toml
import sys
import os

from tester import ExerciseTester


def get_configuration_paths() -> list[str]:
    """
    Returns a list of configuration paths to look for configuration files
    :return: List of paths to check
    """
    configuration_paths = []
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        configuration_paths.append(sys.argv[1])

    configuration_paths.append(os.path.join(os.getcwd(), "exercise-tester.py.toml"))

    if os.environ.get("HOME", None) is not None:
        configuration_paths.append(os.path.join(os.environ["HOME"], ".exercise-tester.py.rc"))

    configuration_paths.append("/etc/default/exercise-tester.py.conf")
    return configuration_paths


if __name__ == "__main__":
    config = {}
    for configuration_path in get_configuration_paths():
        if os.path.isfile(configuration_path):
            config = toml.load(configuration_path)
            break

    tester = ExerciseTester(config)
