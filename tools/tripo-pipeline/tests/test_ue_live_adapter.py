"""Wire contracts for the UE 5.8 and 5.9 editor adapters. No running editor required."""
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review.ue_live import TOOLSETS, TOOLSETS_59, Ue, UeError


def response(value):
    return {"result": {"structuredContent": {"returnValue": value}}}


def connection(version):
    return {"result": {"protocolVersion": "2025-03-26", "serverInfo": {"version": version}}}


class EditorDialectTest(unittest.TestCase):
    def test_58_preserves_tool_and_arguments(self):
        with patch.object(Ue, "_post", side_effect=[connection("5.8.0"), {}, response(["x"])]) as post:
            ue = Ue()
            args = {"folder_path": "/Game/Figures", "recursive": False}
            self.assertEqual(ue.call("asset", "find_assets", args), ["x"])
            wire = post.call_args.args[0]["params"]["arguments"]
            self.assertEqual(wire, {"toolset_name": TOOLSETS["asset"], "tool_name": "find_assets", "arguments": args})

    def test_59_uses_cached_schema_and_exhaustive_legacy_search(self):
        ts = TOOLSETS_59["asset"]
        schema = {"properties": {"filter": {"properties": {"folderPath": {}, "bRecursive": {"type": "boolean"},
                                                           "maxResults": {"type": "integer"}}}}}
        described = {"result": {"structuredContent": {"toolsets": {
            ts: {"tools": [{"name": ts + ".FindAssets", "inputSchema": schema}]}}}}}
        replies = [connection("5.9.0-60738873"), {}, described, response(["first"]), response(["second"])]
        with patch.object(Ue, "_post", side_effect=replies) as post:
            ue = Ue()
            self.assertEqual(ue.call("asset", "find_assets", {"folder_path": "/Game", "recursive": False}), ["first"])
            wire = post.call_args.args[0]["params"]["arguments"]
            self.assertEqual(wire["tool_name"], "FindAssets")
            self.assertEqual(wire["arguments"]["filter"], {"folderPath": "/Game", "bRecursive": False, "maxResults": 0})
            self.assertEqual(ue.call("asset", "FindAssets", {"filter": {"maxResults": 2}}), ["second"])
            self.assertEqual(post.call_count, 5)
            self.assertEqual(post.call_args.args[0]["params"]["arguments"]["arguments"], {"filter": {"maxResults": 2}})

    def test_unknown_toolset_inside_success_response(self):
        replies = [connection("5.9.0"), {}, {"result": {"structuredContent": {
            "toolsets": {}, "errors": {"Missing": "not found"}}}}]
        with patch.object(Ue, "_post", side_effect=replies) as post:
            with self.assertRaisesRegex(UeError, "Unknown toolset Missing"):
                Ue().call("Missing", "Write", {})
            self.assertEqual(post.call_count, 3)

    def test_unidentified_project_refused_before_tools(self):
        with patch.object(Ue, "_post", side_effect=[connection("5.9.0")]) as post:
            with self.assertRaisesRegex(UeError, "project mismatch"):
                Ue(expected_project="Expected.uproject")
            self.assertEqual(post.call_count, 1)
