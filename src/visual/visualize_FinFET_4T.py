import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Patch
from matplotlib.lines import Line2D


def load_results(filename):
    """
    Load placement + pin nets and routing segments from your results file.
    Returns:
      placement: dict[name] = {
          'x','y','width','height','flip','s_net','g_net','d_net'
      }
      routing: list of {
          'layer_u','row_u','col_u','layer_v','row_v','col_v','net'
      }
    """
    placement = {}
    routing = []
    mode = None

    with open(filename) as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            # start of placement section
            if line.startswith("** Placement Result"):
                mode = "placement"
                # skip header + underline (use next(..., None) to avoid StopIteration)
                next(f, None)
                next(f, None)
                continue

            # start of routing section
            if line.startswith("** Routing Result"):
                mode = "routing"
                # skip routing header + underline, if present
                next(f, None)
                next(f, None)
                continue

            if line.startswith("** Cell Information"):
                next(f, None)
                next(f, None)
                next(f, None)
                continue

            if mode == "placement":
                toks = line.split()
                print("toks", toks)
                name = toks[0]
                x, y = float(toks[1]), float(toks[2])
                flip_flag = (toks[3] == "F")
                width, height = float(toks[4]), float(toks[5])
                s_net = toks[7] if float(toks[6]) >= 0 else None
                d_net = toks[9] if float(toks[8]) >= 0 else None
                g_net = toks[11] if float(toks[10]) >= 0 else None

                placement[name] = {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "flip": flip_flag,
                    "s_net": s_net,
                    "g_net": g_net,
                    "d_net": d_net,
                }

            elif mode == "routing":
                # skip any non-data lines
                if "=>" not in raw:
                    continue

                # try to parse, but silently ignore malformed lines
                try:
                    left, right = raw.split("=>")
                    lu, ru, cu, net = left.split()
                    lv, rv, cv, _   = right.split()
                except ValueError:
                    continue

                routing.append({
                    "layer_u": int(lu),
                    "row_u":   float(ru),
                    "col_u":   float(cu),
                    "layer_v": int(lv),
                    "row_v":   float(rv),
                    "col_v":   float(cv),
                    "net":     net,
                })

    return placement, routing


def draw_layout_with_pin_and_routing(
    placement, routing, filename=None, pin_radius=1.0, track_width=4.0
):
    """
    Draw transistors with pin labels and routing as thin rectangle patches.
    """
    # 1) compute exact bounds including routing
    xs = []
    ys = []
    for info in placement.values():
        xs += [info["x"], info["x"] + info["width"]]
        ys += [info["y"], info["y"] + info["height"]]
    for r in routing:
        xs += [r["col_u"], r["col_v"]]
        ys += [r["row_u"], r["row_v"]]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    # 2) setup figure
    # fig, ax = plt.subplots(figsize=(8, 6))
    # resize based on the layout size
    fig_width = max_x - min_x + 20
    fig_height = max_y - min_y + 20
    fig, ax = plt.subplots(figsize=(fig_width / 25, fig_height / 25), dpi=100)

    # 3) draw placement + pins
    for name, info in placement.items():
        x, y = info["x"], info["y"]
        w, h = info["width"], info["height"]
        flip = info["flip"]
        s_net, g_net, d_net = info["s_net"], info["g_net"], info["d_net"]

        # body
        rect = Rectangle(
            (x, y), w, h, edgecolor="black", facecolor="lightgray", lw=1, alpha=0.5
        )
        ax.add_patch(rect)
        ax.text(
            x + w - 20,
            y + h * 0.05,
            name + " (F)" if flip else name,
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
        )

        # pin positions
        if flip:
            pins = [
                ("D", (x, y + h), d_net),
                ("G", (x + w / 2, y + h), g_net),
                ("S", (x + w, y + h), s_net),
            ]
        else:
            pins = [
                ("S", (x, y + h), s_net),
                ("G", (x + w / 2, y + h), g_net),
                ("D", (x + w, y + h), d_net),
            ]

        for pin_name, (px, py), net in pins:
            if net is None:
                continue
            # draw a small circle
            circ = Circle(
                (px, py),
                radius=pin_radius,
                edgecolor="black",
                facecolor="white",
                lw=1.2,
            )
            ax.add_patch(circ)
            # label the net inside or beside the pin
            text_offset = 7
            ax.text(
                px + text_offset,
                py - text_offset,
                net,
                ha="center",
                va="center",
                fontsize=6,
                fontstyle="italic",
                fontweight="bold",
            )
            circ = Circle(
                (px, py - h),
                radius=pin_radius,
                edgecolor="black",
                facecolor="white",
                lw=1.2,
            )
            ax.add_patch(circ)

    # 4) draw routing with patches
    nets = sorted({r["net"] for r in routing})
    cmap = plt.get_cmap("tab10")
    net_colors = {n: cmap(i % cmap.N) for i, n in enumerate(nets)}

    for r in routing:
        x0, y0 = r["col_u"], r["row_u"]
        x1, y1 = r["col_v"], r["row_v"]
        col = net_colors[r["net"]]

        # --- detect inter‐layer via and draw a crossing symbol ---
        if r["layer_u"] != r["layer_v"]:
            if r["layer_u"] == 0 and r["layer_v"] == 1:
                layer_name = "CA"
            elif r["layer_u"] == 1 and r["layer_v"] == 2:
                layer_name = "V0"
            elif r["layer_u"] == 2 and r["layer_v"] == 3:
                layer_name = "V1"
            else:
                raise ValueError(
                    f"Unexpected layer transition {r['layer_u']} -> {r['layer_v']}"
                )
            # Draw a little "×" at the via location
            via_size = track_width * 4  # adjust for visibility
            ax.plot(
                x0, y0, marker="x", color=col, markersize=via_size, markeredgewidth=2, alpha=0.8
            )
            # Optionally label the net
            ax.text(
                x0,
                y0 + track_width * 1.5,
                r["net"] + "," + layer_name,
                ha="center",
                va="bottom",
                fontsize=6,
                bbox=dict(
                    facecolor="lightgray",  # fill color
                    edgecolor="black",  # box border color
                    boxstyle="round,pad=0.3",  # rounded corners and padding
                    alpha=0.5,  # transparency
                ),
            )
            # skip the rest of the segment‐drawing
            continue
        
        if r["layer_u"] == 0:
            layer_name = "PC"
            # continue # ignore this
        elif r["layer_u"] == 1:
            layer_name = "M0"
        elif r["layer_u"] == 2:
            layer_name = "M1"
        elif r["layer_u"] == 3:
            layer_name = "M2"
        else:
            raise ValueError(f"Unexpected layer {r['layer_u']}")
        
        dx, dy = x1 - x0, y1 - y0

        # horizontal wire
        if abs(dy) < 1e-6:
            x_start = min(x0, x1)
            length = abs(dx)
            y_start = y0 - track_width / 2
            patch = Rectangle(
                (x_start, y_start),
                length,
                track_width,
                facecolor=col,
                edgecolor="black",
                lw=0.5,
                alpha=0.6,
            )
            ax.add_patch(patch)

        # vertical wire
        elif abs(dx) < 1e-6:
            y_start = min(y0, y1)
            length = abs(dy)
            x_start = x0 - track_width / 2
            patch = Rectangle(
                (x_start, y_start),
                track_width,
                length,
                facecolor=col,
                edgecolor="black",
                lw=0.5,
                alpha=0.6,
            )
            ax.add_patch(patch)

        else:
            # fallback diagonal
            ax.plot([x0, x1], [y0, y1], color=col, lw=1.5)

        # optional net label at midpoint
        xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
        ax.text(xm, ym, r["net"] + "," + layer_name, ha="center", va="center", fontsize=6, color="white",
                bbox=dict(
                    facecolor=col,  # fill color
                    edgecolor="black",  # box border color
                    boxstyle="round,pad=0.3",  # rounded corners and padding
                    alpha=0.5,  # transparency
                ))

    # 5) legend
    handles = [Patch(facecolor=net_colors[n], edgecolor="black", label=n) for n in nets]
    ax.legend(
        handles=handles,
        title="Nets",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        fontsize=6,
    )

    # 6) finalize
    ax.set_xlim(min_x - 10, max_x + 10)
    ax.set_ylim(min_y - 10, max_y + 10)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X / Column")
    ax.set_ylabel("Y / Row")
    ax.set_xticks([i * 22.5 for i in range(int(min_x / 22.5), int(max_x / 22.5) + 1)])
    ax.set_yticks([i * 24.0 for i in range(int(min_y / 24.0), int(max_y / 24.0) + 1)])
    ax.set_title(f"Transistor P&R for {filename}")
    ax.grid(True, linestyle="--", linewidth=0.5)
    # rotate x-ticks
    plt.xticks(rotation=45, ha="right", fontsize=6)
    plt.tight_layout()

    if filename:
        plt.savefig(filename, dpi=300)
        print(f"Saved to {filename}")
    else:
        plt.show()


# Example usage:
# placement = load_results("results.txt")
# draw_layout_with_pin_labels(placement, filename="placement_pins.png")
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visualize_layout.py <results_file> [<out.png>]")
        sys.exit(1)

    fname = sys.argv[1]
    out_png = sys.argv[2] if len(sys.argv) > 2 else None

    placement, routing = load_results(fname)
    draw_layout_with_pin_and_routing(
        placement, routing, filename=out_png, pin_radius=2.0
    )
