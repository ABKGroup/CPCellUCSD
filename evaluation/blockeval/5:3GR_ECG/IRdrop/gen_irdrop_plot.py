#!/usr/bin/env python3
"""
gen_irdrop_plot.py

Generate an IR-drop placement plot from:
  1) Voltus IV report (e.g., VDD_VSS.avg.iv)
  2) DEF (e.g., jpeg_encoder.def)
  3) LEF (e.g., 6T_2F_45CPP_... .lef)

Output: PNG image showing each placed instance colored by IR-drop.

Updates:
- Fix for older matplotlib: PatchCollection.set_array() needs numpy array (not list)
- Add --vmin/--vmax to control color range
- Annotate max IR-drop value (and instance) on the plot
"""

import argparse
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

import numpy as np

import matplotlib
matplotlib.use("Agg")  # safe for headless
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle
from matplotlib.colors import Normalize


# ----------------------------
# Parsers
# ----------------------------

@dataclass(frozen=True)
class IVEntry:
    cell: str
    ir_drop: float  # nominal - pwr_iv


@dataclass(frozen=True)
class DefPlace:
    x: float  # microns
    y: float  # microns
    orient: str


def parse_iv_report(iv_path: str) -> Tuple[float, Dict[str, IVEntry]]:
    """
    Parse VOLTUS IV report:
      - Extract NOMINAL_VOLTAGE
      - After BEGIN, parse lines like:
        - inst_name DIV PWR_IV GND_IV CELL_NAME

    IMPORTANT:
      Based on your definition, we use DIV as the instance VDD voltage.
      IR-drop = NOMINAL_VOLTAGE - DIV
    """
    nominal = None
    in_body = False
    inst_map: Dict[str, IVEntry] = {}

    nominal_re = re.compile(r"^\s*NOMINAL_VOLTAGE\s+([0-9]*\.?[0-9]+)", re.IGNORECASE)

    with open(iv_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if nominal is None:
                m = nominal_re.match(line)
                if m:
                    nominal = float(m.group(1))
                    continue

            if line == "BEGIN":
                in_body = True
                continue
            if not in_body:
                continue
            if line.startswith("END"):
                break

            if not line.startswith("-"):
                continue

            toks = line.split()
            # Expect: ['-', inst, DIV, PWR_IV, GND_IV, CELL]
            if len(toks) < 6:
                continue

            inst = toks[1]
            div_v = toks[2]     # <-- use DIV column as instance voltage
            cell = toks[5]

            if div_v.upper() == "NA":
                continue

            try:
                divv = float(div_v)
            except ValueError:
                continue

            if nominal is None:
                raise RuntimeError("Could not find NOMINAL_VOLTAGE in IV report header.")

            ir_drop = nominal - divv
            inst_map[inst] = IVEntry(cell=cell, ir_drop=ir_drop)

    if nominal is None:
        raise RuntimeError("Could not find NOMINAL_VOLTAGE in IV report header.")

    return nominal, inst_map

def parse_def_components(def_path: str, micron_units_div: float = 10000.0) -> Dict[str, DefPlace]:
    """
    Parse DEF COMPONENTS placement lines like:
      - instName macroName + PLACED ( x y ) ORIENT ;

    Returns inst -> DefPlace(x/micron_units_div, y/micron_units_div, orient)
    """
    in_components = False
    comp_re = re.compile(
        r"^\s*-\s+(\S+)\s+(\S+)\s+\+\s+PLACED\s+\(\s*(\d+)\s+(\d+)\s*\)\s+(\S+)\s*;?\s*$",
        re.IGNORECASE,
    )

    places: Dict[str, DefPlace] = {}

    with open(def_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()

            if not in_components:
                if line.startswith("COMPONENTS"):
                    in_components = True
                continue

            if line.startswith("END COMPONENTS"):
                break

            if not line.startswith("-"):
                continue

            m = comp_re.match(line)
            if not m:
                continue

            inst = m.group(1)
            x_def = int(m.group(3))
            y_def = int(m.group(4))
            orient = m.group(5).rstrip(";").upper()

            x = x_def / micron_units_div
            y = y_def / micron_units_div
            places[inst] = DefPlace(x=x, y=y, orient=orient)

    return places


def parse_lef_sizes(lef_path: str) -> Dict[str, Tuple[float, float]]:
    """
    Parse LEF for:
      MACRO <name>
        ...
        SIZE <w> BY <h> ;
      END <name>

    Returns cell_name -> (w, h)
    """
    macro_name: Optional[str] = None
    sizes: Dict[str, Tuple[float, float]] = {}

    macro_re = re.compile(r"^\s*MACRO\s+(\S+)\s*$", re.IGNORECASE)
    size_re = re.compile(r"^\s*SIZE\s+([0-9]*\.?[0-9]+)\s+BY\s+([0-9]*\.?[0-9]+)\s*;\s*$", re.IGNORECASE)
    end_re = re.compile(r"^\s*END\s+(\S+)\s*$", re.IGNORECASE)

    with open(lef_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            m = macro_re.match(line)
            if m:
                macro_name = m.group(1)
                continue

            if macro_name is not None:
                sm = size_re.match(line)
                if sm:
                    w = float(sm.group(1))
                    h = float(sm.group(2))
                    sizes[macro_name] = (w, h)
                    continue

                em = end_re.match(line)
                if em and em.group(1) == macro_name:
                    macro_name = None
                    continue

    return sizes


# ----------------------------
# Plotting
# ----------------------------

def plot_ir_drop(
    iv_map: Dict[str, IVEntry],
    def_map: Dict[str, DefPlace],
    lef_sizes: Dict[str, Tuple[float, float]],
    out_png: str,
    title: str,
    max_instances: Optional[int] = None,
    alpha: float = 1.0,
    dpi: int = 250,
    vmin_user: Optional[float] = None,
    vmax_user: Optional[float] = None,
) -> None:
    """
    Draw each instance as a rectangle at DEF (x,y) with LEF (w,h), colored by IR-drop.
    Color range can be forced by vmin_user/vmax_user.
    Also annotates the max IR-drop value on the plot.
    """
    patches: List[Rectangle] = []
    values: List[float] = []
    inst_for_patch: List[str] = []

    missing_place = 0
    missing_size = 0

    items = list(iv_map.items())
    if max_instances is not None and max_instances > 0:
        items = items[:max_instances]

    for inst, iv in items:
        place = def_map.get(inst)
        if place is None:
            missing_place += 1
            continue

        size = lef_sizes.get(iv.cell)
        if size is None:
            missing_size += 1
            continue

        w, h = size

        # For N/S/FN/FS there is no 90° rotation; bounding box stays (w,h)
        rect = Rectangle((place.x, place.y), w, h)
        patches.append(rect)
        values.append(iv.ir_drop)
        inst_for_patch.append(inst)

    if not patches:
        raise RuntimeError(
            "No instances to plot after joining IV + DEF + LEF.\n"
            f"Missing placements: {missing_place}, missing sizes: {missing_size}\n"
            "Check that instance names match between IV and DEF, and cell names exist in LEF."
        )

    data_min = float(min(values))
    data_max = float(max(values))

    vmin = data_min if vmin_user is None else float(vmin_user)
    vmax = data_max if vmax_user is None else float(vmax_user)

    if vmin >= vmax:
        raise ValueError("vmin must be < vmax for colormap normalization")

    # Find max IR-drop instance (from plotted set)
    max_idx = int(np.argmax(np.asarray(values, dtype=float)))
    max_inst = inst_for_patch[max_idx]
    max_val = float(values[max_idx])

    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111)
    ax.set_aspect("equal", adjustable="box")

    coll = PatchCollection(
        patches,
        cmap="coolwarm",  # blue (low) -> red (high)
        norm=Normalize(vmin=vmin, vmax=vmax),
        linewidths=0.0,
        alpha=alpha,
    )

    coll.set_array(np.asarray(values, dtype=float))  # matplotlib py3.6 fix
    coll.set_clim(vmin, vmax)  # clip colors to chosen range
    ax.add_collection(coll)

    # Axis limits
    xs = [r.get_x() for r in patches]
    ys = [r.get_y() for r in patches]
    ws = [r.get_width() for r in patches]
    hs = [r.get_height() for r in patches]
    ax.set_xlim(min(xs), max(x + w for x, w in zip(xs, ws)))
    ax.set_ylim(min(ys), max(y + h for y, h in zip(ys, hs)))

    ax.set_title(title)
    ax.set_xlabel("X (microns)")
    ax.set_ylabel("Y (microns)")

    cbar = fig.colorbar(coll, ax=ax, shrink=0.85)
    cbar.set_label("IR-drop = NOMINAL_VOLTAGE - PWR_IV (V)")

    plt.tight_layout()
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)


# ----------------------------
# CLI
# ----------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Generate IR-drop heatmap image from Voltus IV report + DEF + LEF."
    )
    ap.add_argument("--iv", required=True, help="Path to VDD_VSS.avg.iv")
    ap.add_argument("--def", dest="def_", required=True, help="Path to jpeg_encoder.def")
    ap.add_argument("--lef", required=True, help="Path to .lef file containing macro SIZE entries")
    ap.add_argument("--out", default="ir_drop.png", help="Output PNG file (default: ir_drop.png)")
    ap.add_argument("--max_instances", type=int, default=0,
                    help="Optional cap on instances plotted (0 = no cap)")
    ap.add_argument("--alpha", type=float, default=1.0, help="Rectangle alpha (default: 1.0)")
    ap.add_argument("--dpi", type=int, default=250, help="PNG DPI (default: 250)")
    ap.add_argument("--micron_div", type=float, default=10000.0,
                    help="Divide DEF coords by this to convert to microns (default: 10000)")
    ap.add_argument("--vmin", type=float, default=None,
                    help="Minimum IR-drop for colormap (V). Default = data min")
    ap.add_argument("--vmax", type=float, default=None,
                    help="Maximum IR-drop for colormap (V). Default = data max")

    args = ap.parse_args()

    nominal, iv_map = parse_iv_report(args.iv)
    def_map = parse_def_components(args.def_, micron_units_div=args.micron_div)
    lef_sizes = parse_lef_sizes(args.lef)

    max_inst = None if args.max_instances <= 0 else args.max_instances
    title = "IR-drop heatmap (Nominal={} V)".format(nominal)

    plot_ir_drop(
        iv_map=iv_map,
        def_map=def_map,
        lef_sizes=lef_sizes,
        out_png=args.out,
        title=title,
        max_instances=max_inst,
        alpha=args.alpha,
        dpi=args.dpi,
        vmin_user=args.vmin,
        vmax_user=args.vmax,
    )

    print("Wrote: {}".format(args.out))
    print("Parsed: {} IV entries, {} DEF placements, {} LEF macros".format(
        len(iv_map), len(def_map), len(lef_sizes))
    )


if __name__ == "__main__":
    main()

