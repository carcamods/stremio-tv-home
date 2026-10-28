"""The release contract (ADRs 0003, 0009): every link people download the builder from names the release the
builder workflow runs, each builder pins that release's commit at setup, and the workflow pins the actions
it runs with people's keys to a commit."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "lists" / "builder" / "publish-lists.yml"
GUIDE = ROOT / "lists" / "README.md"
GUIDES = [ROOT / "PROMPT.md", GUIDE, WORKFLOW]
# Where a guide names a release: raw files, files on GitHub, and the API call that looks up its commit. A
# shell variable ($version, in the update steps) stands for whichever release the person picks.
LINK = re.compile(
    r"raw\.githubusercontent\.com/carcamods/stremio-tv-home/([^/\s]+)/"
    r"|github\.com/carcamods/stremio-tv-home/(?:blob|tree)/([^/\s]+)/"
    r"|repos/carcamods/stremio-tv-home/commits/([^/\s\"]+)"
)
# The command in the guide that writes the commit into a builder's workflow.
PIN = "s/STREMIO_TV_HOME_COMMIT: .*/STREMIO_TV_HOME_COMMIT: $commit/"


def workflow_version():
    return re.search(r"STREMIO_TV_HOME_VERSION: (v\d+\.\d+\.\d+)", WORKFLOW.read_text(encoding="utf-8"))[1]


class Release(unittest.TestCase):
    def test_guides_name_the_release_the_workflow_runs(self):
        version = workflow_version()
        for guide in GUIDES:
            text = guide.read_text(encoding="utf-8")
            refs = {ref for match in LINK.findall(text) for ref in match if ref and not ref.startswith("$")}
            self.assertEqual(refs, {version}, f"{guide.name} must link to the files of {version} only")
            for mention in re.findall(r"STREMIO_TV_HOME_VERSION: (\S+)", text):
                self.assertEqual(mention, version, f"{guide.name} names another release")

    def test_each_builder_runs_the_commit_it_pinned_at_setup(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        # One line for the guide's command to fill in, and here it's still a placeholder: a builder pins the
        # commit its release had when it was set up, never one written into this repo.
        self.assertEqual(text.count("STREMIO_TV_HOME_COMMIT: "), 1)
        placeholder = re.search(r"STREMIO_TV_HOME_COMMIT: (\S+)", text)[1]
        self.assertNotRegex(placeholder, r"^[0-9a-f]{40}$")
        self.assertIn("ref: ${{ env.STREMIO_TV_HOME_COMMIT }}", text)
        self.assertNotIn("ref: ${{ env.STREMIO_TV_HOME_VERSION }}", text)
        self.assertEqual(GUIDE.read_text(encoding="utf-8").count(PIN), 2, "setup and update both pin the commit")

    def test_the_builder_workflow_pins_its_actions_to_a_commit(self):
        uses = re.findall(r"uses: (\S+)", WORKFLOW.read_text(encoding="utf-8"))
        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
