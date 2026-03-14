"""
Objective functions for FinFET circuit layout optimization.
This module contains all objective function implementations used by the CP-SAT solver.
"""

from absl import logging as absl_logging


class Objective:
    """
    Container for objective function implementations.
    Each method takes a FinFET instance and computes a specific objective.
    """

    @staticmethod
    def cpp(finfet):
        """
        Objective: Minimize the cell placement pitch (CPP).
        Returns the maximum column position among all transistors.
        """
        return finfet.cpp_cost

    @staticmethod
    def weighted_wirelength(finfet):
        """
        Objective: Minimize weighted wirelength.
        Computes sum of edge_var * wirelength for all edges.
        """
        weighted_wirelength = 0
        for (u_edge, v_edge), edge_var in finfet.edge_vars.items():
            wire_cost = finfet.edge_to_cost[(u_edge, v_edge)]
            weighted_wirelength += edge_var * wire_cost
        return weighted_wirelength

    @staticmethod
    def gate_sharing(finfet):
        """
        Objective: Maximize gate sharing.
        Counts the number of gate sharing instances between transistor pairs.
        """
        if not hasattr(finfet, "gate_share_pair_vars"):
            absl_logging.error("Gate sharing variables not defined in the model.")
            return 0
        return sum(finfet.gate_share_pair_vars.values())

    @staticmethod
    def lisd_sharing(finfet):
        """
        Objective: Maximize LISD (Local Interconnect Source/Drain) sharing.
        Counts the number of LISD sharing instances between transistor pairs.
        """
        if not hasattr(finfet, "lisd_share_pair_vars"):
            absl_logging.error("LISD sharing variables not defined in the model.")
            return 0
        return sum(finfet.lisd_share_pair_vars.values())

    @staticmethod
    def db_placement(finfet):
        """
        Objective: Encourage diffusion break placement on the right.
        Higher column indices are weighted more heavily.
        """
        db_placement = 0
        for ci, db_var in finfet.db_pmos_cols_vars.items():
            db_placement += db_var * ci
        for ci, db_var in finfet.db_nmos_cols_vars.items():
            db_placement += db_var * ci
        return db_placement

    @staticmethod
    def top_layer_usage(finfet):
        """
        Objective: Minimize top layer usage.
        Counts the number of nets using top layer tracks.
        """
        if not hasattr(finfet, "net_use_top_track"):
            absl_logging.warning("net_use_top_track is not defined. Returning 0 for top layer usage.")
            return 0
        top_layer_usage = 0
        for netname, val in finfet.net_use_top_track.items():
            top_layer_usage += val
        return top_layer_usage
