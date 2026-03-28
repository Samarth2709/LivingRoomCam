from pathlib import Path
import tempfile
import unittest

from livingroomcam.config import load_pi_agent_config, load_server_config


class ConfigTests(unittest.TestCase):
    def test_server_config_resolves_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config"
            config_dir.mkdir()
            path = config_dir / "server.local.json"
            path.write_text(
                """
                {
                  \"db_path\": \"data/test.sqlite3\",
                  \"frame_store_dir\": \"state/frames\",
                  \"face_store_dir\": \"state/faces\",
                  \"static_dir\": \"static\"
                }
                """
            )
            config = load_server_config(path)
            self.assertEqual(config.db_path, root / "data/test.sqlite3")
            self.assertEqual(config.frame_store_dir, root / "state/frames")

    def test_pi_agent_config_reads_camera_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config"
            config_dir.mkdir()
            path = config_dir / "pi.local.json"
            path.write_text(
                """
                {
                  \"server_url\": \"http://127.0.0.1:8765\",
                  \"camera_command\": [\"pi-camera\", \"video\", \"-o\", \"-\"]
                }
                """
            )
            config = load_pi_agent_config(path)
            self.assertEqual(config.camera_command[-1], "-")


if __name__ == "__main__":
    unittest.main()
