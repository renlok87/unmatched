"""Real restic round trips; never contacts Google Drive or the live repository."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
STATE = Path(os.environ.get("LOCALAPPDATA", ".")) / "UnmatchedBackup"
POWERSHELL = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"


@unittest.skipUnless(os.name == "nt" and (STATE / "bin/restic.exe").is_file(),
                     "Requires Windows and locally installed restic")
class BackupRoundTrip(unittest.TestCase):
    def test_preserves_untracked_assets_and_history_without_caches_or_secrets(self):
        # Catches broad gitignore/Saved exclusions, lost old versions, and a false
        # success exit code after an unreadable repository.
        self.assertTrue((HERE / "backup.ps1").is_file(), "Backup runner is missing")
        with tempfile.TemporaryDirectory(prefix="unmatched-backup-test-") as tmp:
            root = Path(tmp)
            source = root / "project with spaces"
            state = root / "state"
            source.mkdir()
            state.mkdir()
            assets = {
                "art/hero/model.blend": b"original blender source",
                "art/hero/model.blend1": b"previous blender source",
                "art/hero/textures/Медуза.png": b"image bytes",
                "scraped-data/images/card.png": b"ignored by git but valuable",
                "unreal/Unmatched/Content/Hero.uasset": b"unreal source asset",
                "unreal/Unmatched/Saved/Autosaves/Hero.uasset": b"recoverable autosave",
                "unreal/Unmatched/Plugins/Vendor/Binaries/Win64/vendor.dll": b"vendor plugin binary",
                "public/assets/audio/music.wav": b"music master",
                "docs/concept.png": b"concept reference",
            }
            excluded = {
                "node_modules/example/cache.png": b"dependency",
                "unreal/Unmatched/Intermediate/compiled.bin": b"build cache",
                "unreal/Unmatched/DerivedDataCache/cache.bin": b"rebuildable cache",
                "unreal/Unmatched/Saved/StagedBuilds/game.pak": b"packaged game",
                ".env": b"secret never uploaded",
                ".claude/settings.local.json": b"local credentials",
            }
            for name, content in {**assets, **excluded}.items():
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            config = {
                "project_root": str(source),
                "repository": str(root / "repository"),
                "tag": "unmatched-assets",
                "restic_exe": str(STATE / "bin/restic.exe"),
                "rclone_exe": str(STATE / "bin/rclone.exe"),
                "use_vss": False,
            }
            (state / "settings.json").write_text(json.dumps(config), encoding="utf-8")
            (state / "policy.json").write_bytes((HERE / "policy.json").read_bytes())

            def run(action, *args, success=True):
                result = subprocess.run(
                    [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                     "-File", str(HERE / "backup.ps1"), "-Action", action,
                     "-StateDir", str(state), *args],
                    capture_output=True, text=True, errors="replace", timeout=120,
                )
                if success:
                    detail = result.stdout + result.stderr
                    if result.returncode:
                        for log in (state / "logs").rglob("*.err.log"):
                            data = log.read_bytes()
                            detail += data.decode("utf-16" if data.startswith(b"\xff\xfe") else "utf-8", errors="replace")
                    self.assertEqual(result.returncode, 0, detail)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            run("Initialize")
            run("Backup")
            first = json.loads((state / "status.json").read_text(encoding="utf-8-sig"))["last_backup"]
            self.assertEqual(first["files"], len(assets))
            (source / "art/hero/model.blend").write_bytes(b"new edited blender source")
            (source / "scraped-data/images/card.png").unlink()
            run("Backup")
            restored = root / "restored"
            run("Restore", "-Snapshot", first["snapshot_id"], "-Target", str(restored))
            actual = {p.relative_to(restored).as_posix(): p.read_bytes()
                      for p in restored.rglob("*") if p.is_file()}
            for name, content in assets.items():
                matches = [v for p, v in actual.items() if p.endswith("/" + name)]
                self.assertEqual(matches, [content], name)
            self.assertEqual(len(actual), len(assets), "Cache or secret entered the backup")
            run("Check")
            run("Maintain")
            # A new process must decrypt the same DPAPI key and list history.
            run("Snapshots")
            with (state / "run.lock").open("rb"):
                busy = run("Backup", success=False)
            self.assertEqual(busy.returncode, 75, "Overlapping operations must not run")
            # Never restore over an existing directory, including the live source.
            run("Restore", "-Target", str(source), success=False)
            config = json.loads((state / "settings.json").read_text(encoding="utf-8-sig"))
            config["repository"] = str(root / "does-not-exist")
            (state / "settings.json").write_text(json.dumps(config), encoding="utf-8")
            run("Backup", success=False)
            after = json.loads((state / "status.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(after["state"], "failed")
            self.assertEqual(after["last_backup"]["snapshot_id"],
                             json.loads((state / "last-success.json").read_text(encoding="utf-8-sig"))["snapshot_id"])


if __name__ == "__main__":
    unittest.main()
