import os
import tempfile
import unittest
from unittest.mock import patch

import witty_profiler.backend.fastapi_server as fastapi_server_module
from witty_profiler.graph.graph import Graph


class DummyCore:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.triggered = False
        self.graph = Graph()

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def trigger_collect(self):
        self.triggered = True

    def get_last_graph(self):
        return self.graph


@unittest.skipUnless(
    hasattr(fastapi_server_module, "FastAPIServer"),
    "FastAPI backend is not available in current environment",
)
class TestFastAPIServerOffline(unittest.TestCase):

    def test_run_offline_exports_all_visual_formats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            core = DummyCore()

            def fake_convert_to_tmp_path(_, filename: str):
                return os.path.join(tmpdir, filename)

            def fake_export_graph(_graph, output_path: str, output_format: str):
                if output_format == "graphviz":
                    return [output_path + ".svg", output_path + ".png"]
                return [output_path]

            with patch.object(
                fastapi_server_module.GlobalConfigManager,
                "convert_to_tmp_path",
                new=fake_convert_to_tmp_path,
            ), patch.object(
                fastapi_server_module.time,
                "sleep",
                return_value=None,
            ), patch.object(
                fastapi_server_module,
                "export_graph",
                side_effect=fake_export_graph,
            ) as export_mock:
                server = fastapi_server_module.FastAPIServer(core)
                server.run_offline(0.0)

            self.assertTrue(core.started)
            self.assertTrue(core.stopped)
            self.assertTrue(core.triggered)

            called_formats = {
                call.kwargs["output_format"] for call in export_mock.call_args_list
            }
            self.assertSetEqual(called_formats, {"html", "drawio", "gexf", "graphviz"})

    def test_run_offline_export_failure_does_not_abort(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            core = DummyCore()

            def fake_convert_to_tmp_path(_, filename: str):
                return os.path.join(tmpdir, filename)

            def fake_export_graph(_graph, output_path: str, output_format: str):
                if output_format == "drawio":
                    raise RuntimeError("drawio renderer unavailable")
                if output_format == "graphviz":
                    return [output_path + ".svg", output_path + ".png"]
                return [output_path]

            with patch.object(
                fastapi_server_module.GlobalConfigManager,
                "convert_to_tmp_path",
                new=fake_convert_to_tmp_path,
            ), patch.object(
                fastapi_server_module.time,
                "sleep",
                return_value=None,
            ), patch.object(
                fastapi_server_module,
                "export_graph",
                side_effect=fake_export_graph,
            ) as export_mock:
                server = fastapi_server_module.FastAPIServer(core)
                server.run_offline(0.0)

            self.assertEqual(export_mock.call_count, 4)
            self.assertTrue(core.stopped)


if __name__ == "__main__":
    unittest.main()
