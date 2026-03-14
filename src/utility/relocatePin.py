import argparse
import os
import klayout.db as pya

class TextShape:
    """Helper class to store text shape information."""
    def __init__(self, textstring, x, y):
        self.textstring = textstring
        self.x = x
        self.y = y

    def pyatext_obj(self):
        return pya.Text(self.textstring, self.x, self.y)

def xtract_layer_text_helper(cell, layer_idx):
    """Extract all text shapes from a layer."""
    tx_objs = []
    for shape_itr in cell.begin_shapes_rec(layer_idx):
        if shape_itr.shape().is_text():
            tmp_tx_shape = TextShape(
                textstring=shape_itr.shape().text_string,
                x=shape_itr.shape().bbox().center().x,
                y=shape_itr.shape().bbox().center().y,
            )
            tx_objs.append(tmp_tx_shape)
    return tx_objs

def relocate_pin(input_gds, output_gds):
    """
    Relocate independent M1 pins to M0 layer.

    An independent M1 pin is one that:
    - Has a label on M1 layer
    - Has exactly one V0 via connection
    - The via connects to an M0 metal

    For such pins, the label is moved from M1 to M0.
    """
    if os.path.isfile(input_gds):
        layout = pya.Layout()
        layout.read(input_gds)
    else:
        print(f"[ERROR] GDS PATH is not valid: {input_gds}")
        exit(1)

    # Process all top cells
    for cell in layout.top_cells():
        cell_name = cell.name
        print(f"[INFO] Processing cell: {cell_name}")

        ### Critical Layer Extraction
        # M1 drawing layer and text layer
        m1_dr_layer_idx = layout.layer(19, 0)
        m1_dr_region = pya.Region(cell.begin_shapes_rec(m1_dr_layer_idx))
        m1_tx_layer_idx = layout.layer(19, 251)
        m1_tx_objs = xtract_layer_text_helper(cell, m1_tx_layer_idx)
        # V0 drawing layer
        v0_dr_layer_idx = layout.layer(18, 0)
        v0_dr_region = pya.Region(cell.begin_shapes_rec(v0_dr_layer_idx))
        # V1 drawing layer (21/0) - must check before removing M1
        v1_dr_layer_idx = layout.layer(21, 0)
        v1_dr_region = pya.Region(cell.begin_shapes_rec(v1_dr_layer_idx))
        # M0 drawing layer and text layer
        m0_dr_layer_idx = layout.layer(15, 0)
        m0_dr_region = pya.Region(cell.begin_shapes_rec(m0_dr_layer_idx))
        m0_tx_layer_idx = layout.layer(15, 251)

        # Track which M1 shapes and labels to keep vs relocate
        m1_shapes_to_keep = pya.Shapes()
        moved_text_labels = []
        moved_v0_region = pya.Region()

        for m1_poly in m1_dr_region.each():
            # Check if this M1 metal has a pin label
            FLAG_LABELED = False
            text_label = ""
            for m1_tx_obj in m1_tx_objs:
                if pya.Region(m1_poly).interacting(m1_tx_obj.pyatext_obj()):
                    text_label = m1_tx_obj.textstring
                    FLAG_LABELED = True
                    break

            # Check if it has exactly one V0 via connection
            FLAG_CONNECTION = False
            tmp_v0_region = v0_dr_region & pya.Region(m1_poly)
            # Filter to uniform size vias only (3136 = 56x56)
            new_tmp_v0_region = pya.Region()
            for v0_poly in tmp_v0_region.each():
                if int(v0_poly.bbox().area()) == 3136:
                    new_tmp_v0_region += pya.Region(v0_poly)
            tmp_v0_region = new_tmp_v0_region

            m0_polys = None
            if len(tmp_v0_region) == 0:
                if FLAG_LABELED:
                    print(f"[WARNING] No V0 connection found for labeled M1 pin: {text_label}")
            elif len(tmp_v0_region) == 1:
                FLAG_CONNECTION = True
                m0_polys = m0_dr_region.interacting(tmp_v0_region)
                if len(m0_polys) != 1:
                    print(f"[WARNING] Expected 1 M0 poly, got {len(m0_polys)} for {text_label}")
                    FLAG_CONNECTION = False

            # Check if this M1 metal has any V1 via connection
            FLAG_HAS_V1 = False
            tmp_v1_region = v1_dr_region & pya.Region(m1_poly)
            if len(tmp_v1_region) > 0:
                FLAG_HAS_V1 = True
                if FLAG_LABELED:
                    print(f"[INFO] M1 pin {text_label} has V1 connection, cannot remove")

            # If labeled with single V0 connection, relocate pin to M0
            # BUT only if there's no V1 connection on this M1 metal
            if FLAG_LABELED and FLAG_CONNECTION and not FLAG_HAS_V1:
                moved_text_labels.append(text_label)
                moved_v0_region += tmp_v0_region
                cx = m0_polys.bbox().center().x
                cy = m0_polys.bbox().center().y
                tmp_tx_shape = TextShape(
                    textstring=text_label,
                    x=cx,
                    y=cy,
                )
                cell.shapes(m0_tx_layer_idx).insert(tmp_tx_shape.pyatext_obj())
                print(f"  [RELOCATED] {text_label}: M1 -> M0")
            else:
                # Keep this M1 shape
                m1_shapes_to_keep.insert_box(m1_poly.bbox())

        # Update M1 shapes (remove relocated ones)
        cell.shapes(m1_dr_layer_idx).assign(m1_shapes_to_keep)

        # Update M1 text labels (remove relocated ones)
        m1_text_to_keep = pya.Shapes()
        for m1_tx_obj in m1_tx_objs:
            if m1_tx_obj.textstring not in moved_text_labels:
                m1_text_to_keep.insert_text(m1_tx_obj.pyatext_obj())
        cell.shapes(m1_tx_layer_idx).assign(m1_text_to_keep)

        # Update V0 vias (remove relocated ones)
        v0_region_to_keep = v0_dr_region ^ moved_v0_region
        v0_shapes_to_keep = pya.Shapes()
        for v0_poly in v0_region_to_keep.each():
            v0_shapes_to_keep.insert_box(v0_poly.bbox())
        cell.shapes(v0_dr_layer_idx).assign(v0_shapes_to_keep)

        print(f"  [DONE] Relocated {len(moved_text_labels)} pins: {moved_text_labels}")
    layout.write(output_gds)
    print(f"[INFO] Output written to: {output_gds}")


def main():
    parser = argparse.ArgumentParser(description='Relocate independent M1 pins to M0 layer')
    parser.add_argument('--input_gds', type=str, required=True, help='Input GDS file path')
    parser.add_argument('--output_gds', type=str, required=True, help='Output GDS file path')
    args = parser.parse_args()
    relocate_pin(args.input_gds, args.output_gds)
    

if __name__ == '__main__':
    main()