from src.utility.entity import LayerStack

class FinFET_Tech:
    def __init__(
        self,
        lib_name,
        num_fin,
        num_rt_track,
        unit_width,
        layer_stack: LayerStack,
        height_config="SH",
        num_sites=1,                    # ← newly added
        diffusion_break_type="SDB",
        allow_diffusion_height_mixing=True,
        allow_lisd_merging=True,
        allowable_min_gate_cut_cpp=2,
    ):
        # (decide which lib_name‐format you actually want)
        self.lib_name = lib_name
        self.TECHNOLOGY = "FinFET"
        self.num_fin = num_fin
        self.num_rt_track = num_rt_track
        self.layer_stack = layer_stack
        self.unit_width = unit_width
        self.height_config = height_config
        self.num_sites = num_sites
        self.diffusion_break_type = diffusion_break_type
        self.allow_diffusion_height_mixing = allow_diffusion_height_mixing
        self.allow_lisd_merging = allow_lisd_merging
        self.allowable_min_gate_cut_cpp = allowable_min_gate_cut_cpp

        self.enforce_diffusion_alignment = True
        self.allowable_diffusion_break_cols = "ALL"
        
        self.num_sites = self.validate_height_config(
            height_config, num_rt_track, num_sites
        )

        # power rail defaults
        self.power_config = "M0BPR"
        self.wall_thickness = 0.019
        self.power_rail_thickness = 0.026
        self.m0_pitch = 0.024

        self.gate_width = 0.016
        self.gate_height = 0.154
        self.gate_pitch = 0.045

        self.active_height = 0.046
        self.active_width = 0.059
        self.active_overlap = 0.014
        self.active_gap = 0.014

    def get_pitch(self, layer_name):
        for layer in self.layer_stack.metal_layers:
            if layer.layer_name == layer_name:
                return layer.pitch
        raise ValueError(f"Layer {layer_name} not found in the technology stack.")

    def get_offset(self, layer_name):
        for layer in self.layer_stack.metal_layers:
            if layer.layer_name == layer_name:
                return layer.offset
        raise ValueError(f"Layer {layer_name} not found in the technology stack.")

    def get_width(self, layer_name):
        for layer in self.layer_stack.metal_layers:
            if layer.layer_name == layer_name:
                return layer.width
        raise ValueError(f"Layer {layer_name} not found in the technology stack.")
    
    def validate_height_config(self, height_config, num_rt_track, num_sites):
        """
        Validates the height configuration settings and adjusts num_sites if needed.
        
        Args:
            height_config (str): The height configuration ("SH", "PNNP", or "NPPN")
            num_rt_track (int): Number of routing tracks
            num_sites (int): Number of sites
            
        Returns:
            int: Validated (and potentially adjusted) num_sites
            
        Raises:
            AssertionError: If the configuration is invalid and cannot be adjusted
        """
        if height_config == "SH" or height_config == "DHMH":
            assert num_rt_track in [2, 3, 4], (
                f"Height configuration {height_config} is only supported for 2, 3, or 4 routing tracks."
            )
            assert num_sites == 1, (
                f"Height configuration {height_config} must have 1 site per standard cell."
            )
        elif height_config == "PNNP" or height_config == "NPPN":
            assert num_rt_track == 4 or num_rt_track == 3, (
                f"Height configuration {height_config} is only supported for 3 or 4 routing tracks."
            )
            if num_sites != 2:
                # Auto-adjust num_sites to 2 for PNNP/NPPN configurations
                adjusted_num_sites = 2
                print(f"Adjusted num_sites to {adjusted_num_sites} for height configuration {height_config}.")
                return adjusted_num_sites
        else:
            raise ValueError(f"Unknown height configuration: {height_config}")
            
        # If we get here, num_sites is already correct
        return num_sites
