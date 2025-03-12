import logging


class Completion:
    """Represents a well completion.

    A completion defines a connection between a well and a grid cell.  It stores
    information about the completion's location, status (open or shut), and
    flow direction.

    Attributes:
        id (int): Completion ID.
        I (int): I-index of the grid cell (1-based).
        J (int): J-index of the grid cell (1-based).
        K (int): K-index of the grid cell (1-based).
        status (str): Completion status ("OPEN" or "SHUT").
        IJK (int): Linear index of the grid cell (1-based).  This is set using the
            `set_ijk` method.
        flow_rate (float): Flow rate at the completion. Positive: injection,
            negative: production. This is set using the `set_out_flow_rate` method.
    """


    def __init__(self, I: int, J: int, K: int, stat: int) -> None:
        """Initializes a Completion object.

        Args:
            I (int): I-index of the grid cell (1-based).
            J (int): J-index of the grid cell (1-based).
            K (int): K-index of the grid cell (1-based).
            stat (int): Completion status ID (positive for open, other values for shut).
        """
        self.I = I
        self.J = J
        self.K = K
        self._set_status(stat)


    def set_ijk(self, ijk: int) -> None:
        """Sets the linear grid cell index (IJK).

        Args:
            ijk (int): Linear index of the grid cell (0-based).
        """
        self.IJK = ijk


    def set_flow_rate(self, val: float) -> None:
        """Sets the flow rate at the completion.

        Args:
            val (float): Flow rate. Positive: injection, negative: production.
        """
        self.flow_rate = val # positive: injection, negative: production


    # ---- Private Methods ---------------------------------------------------------------------------------------------


    def _set_status(self, stat_id: int) -> None:
        """Sets the completion status.

        Args:
            stat_id (int): Status ID (positive for open, other values for shut).
        """
        self.status = "OPEN" if stat_id > 0 else "SHUT"


class Well:
    """Represents a well.

    A well has a name, type (producer or injector), and a list of completions.

    Attributes:
        name (str): Name of the well.
        type (str): Type of well ("PRD" or "INJ").
        completions (list[Completion]): List of Completion objects associated with the well.
        num_active_completions (int): Number of active (open) completions.
    """

    def __init__(self, name: str,  type_id: int) -> None:
        """Initializes a Well object.

        Args:
            name (str): Name of the well.
            type_id (int): Well type ID.
        """
        self.name = name
        self._set_type(type_id)
        self.completions = []
        self.num_active_completions = 0
        self.status = "OPEN"

    def add_completion(self, I: int, J: int, K: int, stat: int) -> None:
        """Adds a completion to the well.

        Args:
            I (int): I-index of the grid cell (1-based).
            J (int): J-index of the grid cell (1-based).
            K (int): K-index of the grid cell (1-based).
            stat (int): Completion status ID (positive for open, other values for shut).
        """
        self.completions.append(Completion(I, J, K, stat))
        if self.completions[-1].status == "OPEN":
            self.num_active_completions += 1


    def set_status(self) -> None:
        """Set well status based on completion status"""
        self.status = "SHUT" if self.num_active_completions == 0 else "OPEN"


    # ---- Private Methods ---------------------------------------------------------------------------------------------


    def _set_type(self, type_id: int) -> None:
        """Sets the well type.

        Args:
            type_id (int):
            - Well type ID - 1 for PRD, 2 for OILINJ, 3 for WATINJ, 4 for GASINJ (ECL)
            - 5 for injector identifier for CMG (unclear how to get different injector types in CMG)
        """
        if type_id == 1:
            self.type = "PRD"
        elif type_id in [2,3,4,5]:
            self.type = "INJ"
        else:
            self.type = "UNKNOWN"
            logging.warning((f"Unknown well type: {type_id} found at well: {self.name}"))
