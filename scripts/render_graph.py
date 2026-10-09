"""Export the actual compiled LangGraph and render it locally without network."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from agent import AppConfig, build_graph


def main():
    diagram = build_graph(AppConfig()).get_graph()
    (ROOT / "graph.mmd").write_text(diagram.draw_mermaid(), encoding="utf-8")
    positions = {
        "__start__": (0, 8), "classify": (0, 7),
        "answer": (-4, 6), "math_tool": (-4, 4.5), "write_answer": (-4, 3.2),
        "learn": (4.5, 6), "read_source": (0, 4.7),
        "verified_examples": (3, 4.7), "teaching_bestpractices": (6, 4.7),
        "web_search": (9, 4.7), "write_explanation": (4.5, 3.2),
        "user_input": (4.5, 1.8), "__end__": (0, 0.5),
    }
    if set(positions) != set(diagram.nodes):
        raise ValueError("Compiled graph changed; update the visual layout.")
    fig, ax = plt.subplots(figsize=(18, 10))
    fig.patch.set_facecolor("white")
    ax.set_xlim(-6, 11)
    ax.set_ylim(-0.4, 9)
    ax.axis("off")
    boxes = {}
    for name in diagram.nodes:
        x, y = positions[name]
        width = max(1.6, len(name) * 0.115 + 0.55)
        color = "#dcecfb" if name in {"__start__", "__end__"} else "#f0eafd"
        if name in {"read_source", "verified_examples", "teaching_bestpractices", "web_search"}:
            color = "#ddf4e6"
        box = FancyBboxPatch((x - width / 2, y - 0.25), width, 0.5,
                            boxstyle="round,pad=0.09", facecolor=color,
                            edgecolor="#415066", linewidth=1.4, zorder=3)
        ax.add_patch(box)
        boxes[name] = box
        label = {"__start__": "START", "__end__": "END"}.get(name, name)
        ax.text(x, y, label, ha="center", va="center", fontsize=12, zorder=4)
    for edge in diagram.edges:
        source, target = positions[edge.source], positions[edge.target]
        loop = edge.source == "user_input" and edge.target == "write_explanation"
        arrow = FancyArrowPatch(source, target, patchA=boxes[edge.source], patchB=boxes[edge.target],
            arrowstyle="-|>", mutation_scale=17, linewidth=1.5, color="#415066",
            linestyle="--" if edge.conditional else "-",
            connectionstyle="arc3,rad=-0.65" if loop else "arc3,rad=0", zorder=2)
        ax.add_patch(arrow)
        label = edge.data or (edge.target if edge.source == "classify" else None)
        if label:
            x, y = ((source[0] + target[0]) / 2, (source[1] + target[1]) / 2)
            if loop:
                x += 1.05
            ax.text(x, y + 0.1, str(label), fontsize=11, ha="center",
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 2}, zorder=5)
    ax.text(4.5, 2.72, "One barrier: waits for all four resources", fontsize=11,
            ha="center", color="#415066")
    ax.text(4.5, 1.28, "Checkpointed pause / resume", fontsize=11,
            ha="center", color="#415066")
    ax.set_title("MathTutor — actual compiled LangGraph", fontsize=22, pad=18)
    fig.savefig(ROOT / "graph.png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {ROOT / 'graph.png'} and {ROOT / 'graph.mmd'}")


if __name__ == "__main__":
    main()
