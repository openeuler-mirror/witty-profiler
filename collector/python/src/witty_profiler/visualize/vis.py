import argparse
import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

from witty_profiler.common.logging import get_logger
from witty_profiler.graph.graph import Graph
from witty_profiler.visualize.renderer.renderer_base import LayoutRenderer

from .layout import Layout, available_layouts, get_layout_class
from .renderer import available_renderers, get_renderer_class

LOGGER = get_logger(__name__)


def parse_args():
    RENDERERS = available_renderers()

    """Parse command-line arguments and start Witty Profiler server."""
    parser = argparse.ArgumentParser(
        prog="witty-profiler-visualize",
        description="Witty Profiler - Visualize AI system topology",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Visualize AI system topology
  python -m witty_profiler-vis <input-json-file-path> -of <output-format> -o <output-path>
""",
    )
    parser.add_argument(
        "input_json_file_path",
        type=str,
        help="Input path of the graph json file",
    )
    parser.add_argument(
        "-le",
        "--layout_engine",
        type=str,
        choices=available_layouts(),
        default=available_layouts()[0],
        help=f"Layout engine to use, default is {available_layouts()[0]}.",
    )
    parser.add_argument(
        "-of",
        "--output_format",
        type=str,
        choices=RENDERERS,
        default=RENDERERS[0],
        help=f"Output format, default is {RENDERERS[0]}.",
    )
    parser.add_argument(
        "-o",
        "--output_basename",
        type=str,
        default=None,
        help="Output file basename, default same as input file",
    )
    args = parser.parse_args()
    return args


def visualize(args):
    """Visualize AI system topology."""
    # 1. 从json文件创建图
    with open(args.input_json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    graph = Graph(**data)
    # 2. 导出图
    if args.output_basename is None:
        basename = Path(args.input_json_file_path).stem
    else:
        basename = args.output_basename

    with open(
        Path(args.input_json_file_path).parent / f"{basename}.{args.output_format}",
        "w",
        encoding="utf-8",
    ) as f:
        renderer_class: type[LayoutRenderer] | None = get_renderer_class(
            args.output_format
        )
        if renderer_class is None:
            raise ValueError(f"Renderer '{args.output_format}' not found.")
        layout_class = get_layout_class(args.layout_engine)
        if layout_class is None:
            raise ValueError(f"Layout engine not found.")
        layout = layout_class()
        layout.build_from_graph(graph)
        renderer = renderer_class(layout=layout)
        render_result = renderer.render()
        f.write(render_result)
    LOGGER.info(
        f"Exported visualization to {Path(args.input_json_file_path).parent / f'{basename}.{args.output_format}'}"
    )

    # 3. 导出text结果
    text_output_path = Path(args.input_json_file_path).parent / f"{basename}_text.txt"
    with open(text_output_path, "w", encoding="utf-8") as f:
        f.write(str(graph))
    LOGGER.info(f"Exported text representation to {text_output_path}")


def main():
    args = parse_args()
    visualize(args)


if __name__ == "__main__":
    main()
    main()
