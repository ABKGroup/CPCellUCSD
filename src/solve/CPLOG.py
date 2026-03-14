from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import LinearExpr, LiteralT, IntVar
from ortools.sat.cp_model_pb2 import ConstraintProto

_STR_VAR = {
    cp_model.CHOOSE_FIRST: "CHOOSE_FIRST",
    cp_model.CHOOSE_LOWEST_MIN: "CHOOSE_LOWEST_MIN",
    cp_model.CHOOSE_HIGHEST_MAX: "CHOOSE_HIGHEST_MAX",
    cp_model.CHOOSE_MIN_DOMAIN_SIZE: "CHOOSE_MIN_DOMAIN_SIZE",
    cp_model.CHOOSE_MAX_DOMAIN_SIZE: "CHOOSE_MAX_DOMAIN_SIZE",
}
_STR_DOM = {
    cp_model.SELECT_MIN_VALUE: "SELECT_MIN_VALUE",
    cp_model.SELECT_MAX_VALUE: "SELECT_MAX_VALUE",
    cp_model.SELECT_LOWER_HALF: "SELECT_LOWER_HALF",
    cp_model.SELECT_UPPER_HALF: "SELECT_UPPER_HALF",
}


class LoggingConstraint:
    """
    Wraps a cp_model.Constraint and, when OnlyEnforceIf is called,
    emits a single combined log entry.
    """

    def __init__(self, constraint: cp_model.Constraint, model: "LoggingCpModel", ct_str: str):
        self._inner = constraint
        self._model = model
        self._ct_str = ct_str  # remember the original constraint text

    def only_enforce_if(self, *lits: LiteralT) -> "LoggingConstraint":
        # Build literal string
        lit_str = self._model._literal_to_str(lits if len(lits) > 1 else lits[0])
        # Emit one combined log entry
        self._model._log_operation("constraint", f"{self._ct_str} (only_enforce_if) {lit_str}")
        # Delegate to the real Constraint
        self._inner.only_enforce_if(*lits)
        return self

    # Alias so both methods work
    OnlyEnforceIf = only_enforce_if

    def __getattr__(self, name):
        return getattr(self._inner, name)


# Define LoggingCpModel so it can be type-hinted
# Define the class so it can be type-hinted
class LoggingCpModel(cp_model.CpModel):
    """
    A wrapper for cp_model.CpModel that logs model-building operations.

    It uses an internal cache to buffer log messages and writes them to a file
    in batches, significantly improving performance over line-by-line logging.

    This class is best used as a context manager to ensure all logs are
    flushed upon exiting the block.
    """

    def __init__(self, logfile: str = None, cache_limit: int = 1e8):
        """
        Initializes the LoggingCpModel.

        Args:
            logfile: The path to the log file. If None, logs to stdout.
            cache_limit: The number of log messages to cache in memory before
                         flushing to the file.
        """
        super().__init__()
        self._logfile = logfile
        self._cache_limit = cache_limit
        self._log_cache = []  # In-memory cache for log messages
        self._operation_count = 0
        self._comment_count = 0

        # Clear the logfile at the beginning of the session
        if self._logfile:
            with open(self._logfile, "w") as f:
                f.write("LoggingCpModel initialized. Operations will be logged.\n")
        
        # Immediate feedback to the console
        print(f"LoggingCpModel initialized. Logging to '{logfile or 'stdout'}'. Cache limit: {cache_limit}.")
    
    def _flush_log_cache(self):
        """Writes the content of the log cache to the file and clears the cache."""
        if not self._logfile or not self._log_cache:
            return  # Do nothing if logging to stdout or cache is empty

        try:
            with open(self._logfile, "a") as f:
                # Joining a list of strings and writing once is far more efficient
                f.write("\n".join(self._log_cache) + "\n")
            self._log_cache.clear()
        except IOError as e:
            print(f"Error flushing log cache: {e}")

    def _log_operation(self, operation_type: str, details: str):
        """
        Formats and caches a log message, flushing the cache if the limit is reached.
        """
        self._operation_count += 1
        message = f"[CP #{self._operation_count}] Adding {operation_type}:\t{details}"

        if self._logfile:
            self._log_cache.append(message)
            if len(self._log_cache) >= self._cache_limit:
                self._flush_log_cache()
        else:
            # For stdout, logging remains immediate
            # print(message)
            pass

    def log_comment(self, comment: str):
        """
        Logs a descriptive comment, separating it with newlines for readability.
        """
        self._comment_count += 1
        # For readability, comments are separated by a blank line in the log file
        messages = ["", f"[Comment #{self._comment_count}] {comment}"]

        if self._logfile:
            self._log_cache.extend(messages)
            if len(self._log_cache) >= self._cache_limit:
                self._flush_log_cache()
        else:
            # print("\n".join(messages))
            pass
    
    # --- Manual Flush Method ---
    def flush(self):
        """
        Manually flushes any buffered logs to the destination file.

        It is highly recommended to use the context manager ('with' statement)
        for automatic and guaranteed flushing. This method is provided for
        cases where that is not possible.
        """
        if self._logfile:
            print(f"Manual flush requested. Flushing {len(self._log_cache)} logs...")
            self._flush_log_cache()
            print("Flush complete.")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Called when exiting a 'with' block. Ensures the final flush."""
        # This now conveniently calls the public flush method.
        self.flush()

    def _literal_to_str(self, literal_arg) -> str:
        """Helper to convert a literal or list of literals to a string representation."""
        if isinstance(literal_arg, list):
            return str([str(l) for l in literal_arg])
        # elif isinstance(literal_arg, cp_model.BoolVarT):  # BoolVarT is a common LiteralT
        #     return str(literal_arg)
        else:
            # print Warning("[06/20] Literal to string is left unchecked due to unknown error")
            return str(literal_arg)
        # It could be a negated literal cp_model.NotBoolVarT
        # str() should handle it, but being explicit can help.
        # For BoundedLinearExpression that are LiteralTs (e.g. constants):
        if hasattr(literal_arg, "Proto") and literal_arg.Proto().domain == [0, 0]:
            return "False"
        if hasattr(literal_arg, "Proto") and literal_arg.Proto().domain == [1, 1]:
            return "True"

        return str(literal_arg)

    def Proto(self):
        self._log_operation("model_proto", "<raw Proto()>")
        return super().Proto()

    # --- Variable Creation Methods ---
    def NewIntVar(self, lb: int, ub: int, name: str) -> IntVar:
        self._log_operation("IntVar", f"name='{name}', domain=[{lb}, {ub}]")
        return super().NewIntVar(lb, ub, name)

    def NewBoolVar(self, name: str) -> IntVar:  # Returns an IntVar constrained to be boolean
        self._log_operation("BoolVarT", f"name='{name}'")
        return super().NewBoolVar(name)

    def NewIntervalVar(self, start: LinearExpr, size: LinearExpr, end: LinearExpr, name: str) -> cp_model.IntervalVar:
        self._log_operation("IntervalVar", f"name='{name}', start={start}, size={size}, end={end}")
        return super().NewIntervalVar(start, size, end, name)

    def NewIntVarFromDomain(self, domain: cp_model.Domain, name: str) -> IntVar:
        """
        Create an integer variable whose values lie in the given Domain.
        A domain can be a single interval or a union of intervals:
          Domain(lb, ub)
          Domain.FromValues([1,3,4,6])
          Domain.FromIntervals([[1,2],[4,6]])
        """
        # Log the exact domain
        self._log_operation("IntVarFromDomain", f"name='{name}', domain={domain}")
        # Delegate to the real CP-SAT API
        return super().NewIntVarFromDomain(domain, name)

    # --- General Constraint Adding Method ---
    def Add(self, ct) -> LoggingConstraint:
        # 1) record the constraint text
        try:
            constraint_str = str(ct)
        except RecursionError:
            # Handle deeply nested expressions that exceed recursion limit
            constraint_str = "<complex constraint - recursion limit exceeded>"
        # 2) log its addition
        self._log_operation("constraint", constraint_str)
        # 3) create the real Constraint
        real_ct = super().Add(ct)
        # 4) wrap it so we can catch OnlyEnforceIf
        return LoggingConstraint(real_ct, self, constraint_str)

    # --- Specific Constraint Adding Methods ---
    def AddAllDifferent(self, variables: list[IntVar]) -> cp_model.Constraint:
        var_names = [str(v) for v in variables]
        log_detail = f"variables={var_names}"
        self._log_operation("AllDifferent constraint", log_detail)
        return super().AddAllDifferent(variables)

    def AddImplication(self, b1: LiteralT, b2: LiteralT) -> LoggingConstraint:
        # 1) build a nice string for logging
        lhs = self._literal_to_str(b1)
        rhs = self._literal_to_str(b2)
        ct_str = f"{lhs} => {rhs}"

        # 2) log the implication itself
        self._log_operation("Implication constraint", ct_str)

        # 3) add the real implication
        real_ct = super().AddImplication(b1, b2)

        # 4) wrap & return, so that OnlyEnforceIf will be caught
        return LoggingConstraint(real_ct, self, ct_str)

    def AddAtMostOne(self, literals) -> LoggingConstraint:
        # 1) build a nice string for logging
        lit_str = self._literal_to_str(literals)
        ct_str = f"AtMostOne{lit_str}"

        # 2) log the implication itself
        self._log_operation("AtMostOne constraint", ct_str)

        # 3) add the real implication
        real_ct = super().AddAtMostOne(literals)

        # 4) wrap & return, so that OnlyEnforceIf will be caught
        return LoggingConstraint(real_ct, self, ct_str)

    def AddExactlyOne(self, literals) -> LoggingConstraint:
        # 1) build a nice string for logging
        lit_str = self._literal_to_str(literals)
        ct_str = f"ExactlyOne{lit_str}"

        # 2) log the implication itself
        self._log_operation("ExactlyOne constraint", ct_str)

        # 3) add the real implication
        real_ct = super().AddExactlyOne(literals)

        # 4) wrap & return, so that OnlyEnforceIf will be caught
        return LoggingConstraint(real_ct, self, ct_str)

    def AddAllDifferent(self, variables: list[IntVar]) -> "LoggingConstraint":
        # 1) build a readable constraint string
        var_names = [str(v) for v in variables]
        ct_str = f"AllDifferent({var_names})"
        # 2) log its addition
        self._log_operation("AllDifferent constraint", ct_str)
        # 3) add the real constraint
        real_ct = super().AddAllDifferent(variables)
        # 4) wrap & return so OnlyEnforceIf will be caught
        return LoggingConstraint(real_ct, self, ct_str)

    def AddMaxEquality(self, max_var: IntVar, exprs: list[LinearExpr]) -> LoggingConstraint:
        # 1) build the human-readable representation
        expr_strs = [str(e) for e in exprs]
        ct_str = f"{max_var} == max({', '.join(expr_strs)})"
        # 2) log it
        self._log_operation("MaxEquality constraint", ct_str)
        # 3) call the real method
        real_ct = super().AddMaxEquality(max_var, exprs)
        # 4) wrap it so OnlyEnforceIf is captured
        return LoggingConstraint(real_ct, self, ct_str)

    def AddMinEquality(self, min_var: IntVar, exprs: list[LinearExpr]) -> LoggingConstraint:
        # 1) build the human-readable representation
        expr_strs = [str(e) for e in exprs]
        ct_str = f"{min_var} == min({', '.join(expr_strs)})"
        # 2) log it
        self._log_operation("MinEquality constraint", ct_str)
        # 3) call the real method
        real_ct = super().AddMinEquality(min_var, exprs)
        # 4) wrap it so OnlyEnforceIf is captured
        return LoggingConstraint(real_ct, self, ct_str)

    def AddLinearConstraint(self, expr: LinearExpr, lb: int, ub: int) -> cp_model.Constraint:
        log_detail = f"{lb} <= {expr} <= {ub}"
        self._log_operation("Linear constraint", log_detail)
        return super().AddLinearConstraint(expr, lb, ub)

    def AddNoOverlap(self, interval_vars: list[cp_model.IntervalVar]) -> cp_model.Constraint:
        var_names = [str(v) for v in interval_vars]
        log_detail = f"intervals={var_names}"
        self._log_operation("NoOverlap constraint", log_detail)
        return super().AddNoOverlap(interval_vars)

    def AddCircuit(self, arcs: list[tuple[int, int, LiteralT]]) -> cp_model.Constraint:
        arc_strs = [f"({t},{h},{self._literal_to_str(l)})" for t, h, l in arcs]
        log_detail = f"arcs=[{', '.join(arc_strs)}]"
        self._log_operation("Circuit constraint", log_detail)
        return super().AddCircuit(arcs)

    def AddCumulative(
        self, intervals: list[cp_model.IntervalVar], demands, capacity
    ) -> cp_model.Constraint:
        interval_names = [str(v) for v in intervals]
        demand_strs = [str(d) for d in demands]
        log_detail = f"intervals={interval_names}, demands={demand_strs}, capacity={capacity}"
        self._log_operation("Cumulative constraint", log_detail)
        return super().AddCumulative(intervals, demands, capacity)

    def AddBoolOr(self, literals) -> LoggingConstraint:
        lit_str = self._literal_to_str(literals)
        # log it
        self._log_operation("BoolOr constraint", f"literals={lit_str}")
        # create the real constraint
        real_ct = super().AddBoolOr(literals)
        # build a human‐readable ct_str
        ct_str = f"BoolOr{lit_str}"
        return LoggingConstraint(real_ct, self, ct_str)

    def AddBoolAnd(self, literals) -> LoggingConstraint:
        lit_str = self._literal_to_str(literals)
        self._log_operation("BoolAnd constraint", f"literals={lit_str}")
        real_ct = super().AddBoolAnd(literals)
        ct_str = f"BoolAnd{lit_str}"
        return LoggingConstraint(real_ct, self, ct_str)

    def AddMultiplicationEquality(self, target: IntVar, factors: list[LinearExpr]) -> LoggingConstraint:
        # Build a readable representation: "t == f1 * f2 * …"
        factor_strs = [str(f) for f in factors]
        ct_str = f"{target} == {' * '.join(factor_strs)}"
        self._log_operation("MultiplicationEquality constraint", ct_str)
        real_ct = super().AddMultiplicationEquality(target, factors)
        return LoggingConstraint(real_ct, self, ct_str)

    def NewConstant(self, value: int) -> IntVar:
        # Logs creation of a pure constant term
        self._log_operation("Constant", f"value={value}")
        return super().NewConstant(value)

    def AddDecisionStrategy(self, variables, var_strategy: int, domain_strategy: int):
        var_names = [str(v) for v in variables]
        vs = _STR_VAR.get(var_strategy, str(var_strategy))
        ds = _STR_DOM.get(domain_strategy, str(domain_strategy))
        self._log_operation("DecisionStrategy", f"vars={var_names}, var_strategy={vs}, domain_strategy={ds}")
        return super().AddDecisionStrategy(variables, var_strategy, domain_strategy)

    # --- Objective Methods ---
    def Minimize(self, expr: LinearExpr):
        self._log_operation("Objective", f"Minimize({expr})")
        super().Minimize(expr)
        # auto flush after setting the objective
        self.flush()

    def Maximize(self, expr: LinearExpr):
        self._log_operation("Objective", f"Maximize({expr})")
        super().Maximize(expr)
        # auto flush after setting the objective
        self.flush()

    # --- Hints ---
    def AddHint(self, var: IntVar, value: int):
        self._log_operation("Hint", f"{var} = {value}")
        super().AddHint(var, value)

    # --- Logging for OnlyEnforceIf ---
    def AddEnforcementLiteralT(self, ct_proto: ConstraintProto, literal_arg):
        # This method is called by a Constraint's OnlyEnforceIf.
        constraint_name = ct_proto.name if ct_proto.name else f"constraint_idx_{len(self.Proto().constraints)-1}"
        self._log_operation(
            "Enforcement LiteralT", f"Constraint (name/approx_idx: '{constraint_name}') is enforced by {self._literal_to_str(literal_arg)}"
        )
        return super().AddEnforcementLiteralT(ct_proto, literal_arg)
