import fnmatch
import os
import re
import json
import datetime
from zipfile import BadZipFile

import config as config_module
from winnow import robust_winnowing


class PlagiarismDetector(config_module.ConfigurationBasedObject):
    """
    Detects plagiarism between student submissions using fingerprinting and similarity metrics.
    """

    def __init__(self, config, environment='prod'):
        super().__init__(config, environment)
        self.results = []

    def run(self):
        """
        Process data in all repositories and build documents to search for plagiarisms
        :return: None
        """
        included_files = [re.compile(fnmatch.translate(p)) for p in self.config['plagiarism_detection'].get('files', [])]
        excluded_files = [re.compile(fnmatch.translate(p)) for p in self.config['plagiarism_detection'].get('exclude_files', [])]

        for repo in self.repositories:
            if self.config['general']['repo_filter'] and repo.identifier not in self.config['general']['repo_filter']:
                self.logger.info(f"Skipping repo {repo.identifier} not in filter list")
                continue

            if repo.endpoint.require_download_before_update_check():
                repo.download()

            if repo.has_update():
                if not repo.endpoint.require_download_before_update_check():
                    self.logger.debug(f"Late fetching repository {repo.identifier}")
                    repo.download()

                if self.config['general'].get('unzip_submissions', False) and getattr(repo, 'supports_unzip', False):
                    try:
                        repo.unzip(self.config['general'].get('remove_archive_after_unzip', False))
                    except BadZipFile:
                        self.logger.info(f"Skipping repo {repo.identifier} because of corrupt archive")
                        continue

            # Filter relevant files
            filtered_files = repo.files
            if included_files:
                filtered_files = list(filter(lambda f: any(r.match(f) for r in included_files), filtered_files))
            if excluded_files:
                filtered_files = list(filter(lambda f: all(not r.match(f) for r in excluded_files), filtered_files))

            setattr(repo, "files", filtered_files)
            self.generate_fingerprints(repo)

        self.compare_all_submissions()
        self.export_results()

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

        setattr(repo, "fingerprints", {})

        for filename in repo.files:
            try:
                text = repo.read_file(filename)
                fingerprints = robust_winnowing(text, language=language, k=k, window_size=window)
                repo.fingerprints[filename] = fingerprints
            except Exception as e:
                self.logger.warning(f"Error processing {filename} in {repo.identifier}: {e}")

    def compare_all_submissions(self):
        """
        Compare all submissions using Jaccard similarity and store results above threshold.
        """
        threshold = self.config["plagiarism_detection"].get("threshold", 0.5)
        all_files = []

        for repo in self.repositories:
            if not hasattr(repo, 'fingerprints'):
                self.logger.warning(f"Skipping repo {repo.identifier}: no fingerprints generated")
                continue
            for fname, fp in repo.fingerprints.items():
                all_files.append((repo.identifier, fname, fp))

        for i in range(len(all_files)):
            for j in range(i + 1, len(all_files)):
                id1, file1, fp1 = all_files[i]
                id2, file2, fp2 = all_files[j]

                if not fp1 or not fp2:
                    continue

                intersection = len(fp1 & fp2)
                union = len(fp1 | fp2)
                if union == 0:
                    continue

                jaccard = intersection / union
                if jaccard >= threshold:
                    self.results.append({
                        "file_1": f"{id1}/{file1}",
                        "file_2": f"{id2}/{file2}",
                        "similarity": round(jaccard, 4)
                    })

    def export_results(self):
        """
        Export plagiarism detection results to a timestamped JSON file.
        """
        base_output = self.config["plagiarism_detection"].get("output", "plagiarism_results")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = f"{base_output}_{timestamp}.json"

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=4)
            self.logger.info(f"Plagiarism report written to {output_file}")
        except Exception as e:
            self.logger.error(f"Failed to export plagiarism results: {e}")