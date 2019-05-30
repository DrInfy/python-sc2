from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from sc2.game_state import GameState

import logging

logger = logging.getLogger(__name__)

from scipy.spatial.distance import cdist, pdist
import math
import numpy as np

try:
    from numba import njit

    _numba_imported = True
except:
    logger.error(
        f"Could not import numba in file {__file__}. Please install numba to have faster distance calculations using command 'pip install numba'"
    )
    _numba_imported = False

from typing import List, Dict, Tuple, Iterable, Generator


class DistanceCalculation:
    def __init__(self):
        self.state: GameState = None
        self._generated_frame = -100
        self._generated_frame2 = -100
        # A Dictionary with a dict positions: index of the pdist condensed matrix
        self._cached_unit_index_dict: Dict[Tuple[float, float], int] = None
        # Pdist condensed vector generated by scipy pdist, half the size of the cdist matrix as 1d array
        self._cached_pdist: np.ndarray = None

    @property
    def _units_count(self) -> int:
        return len(self.all_units)

    @property
    def _unit_index_dict(self) -> Dict[Tuple[float, float], int]:
        """ As property, so it will be recalculated each time it is called, or return from cache if it is called multiple times in teh same game_loop. """
        if self._generated_frame != self.state.game_loop:
            return self.generate_unit_indices()
        return self._cached_unit_index_dict

    @property
    def _pdist(self):
        """ As property, so it will be recalculated each time it is called, or return from cache if it is called multiple times in teh same game_loop. """
        if self._generated_frame2 != self.state.game_loop:
            return self.calculate_distances()
        return self._cached_pdist

    def generate_unit_indices(self):
        if self._generated_frame != self.state.game_loop:
            self._cached_unit_index_dict = {unit.tag: index for index, unit in enumerate(self.all_units)}
            self._generated_frame = self.state.game_loop
        return self._cached_unit_index_dict

    def calculate_distances(self):
        if self._generated_frame2 != self.state.game_loop:
            # Converts tuple [(1, 2), (3, 4)] to flat list like [1, 2, 3, 4]
            flat_positions = (coord for unit in self.all_units for coord in unit.position_tuple)
            # Converts to numpy array, then converts the flat array back to [[1, 2], [3, 4]]
            positions_array: np.ndarray = np.fromiter(
                flat_positions, dtype=np.float, count=2 * self._units_count
            ).reshape((self._units_count, 2))
            assert len(positions_array) == self._units_count
            self._generated_frame2 = self.state.game_loop
            # See performance benchmarks
            self._cached_pdist = pdist(positions_array, "sqeuclidean")

            # # Distance check of all units
            # for unit1 in self.all_units:
            #     for unit2 in self.all_units:
            #         if unit1.tag == unit2.tag:
            #             # Is zero
            #             continue
            #         try:
            #             index1 = self._unit_index_dict[unit1.tag]
            #             index2 = self._unit_index_dict[unit2.tag]
            #             condensed_index = self.square_to_condensed(index1, index2)
            #             assert condensed_index < len(self._pdist)
            #             pdist_distance = self._pdist[condensed_index]
            #             correct_dist = self._distance_pos_to_pos(unit1.position_tuple, unit2.position_tuple) ** 2
            #             error_margin = 1e-5
            #             assert (abs(pdist_distance - correct_dist) < error_margin), f"Actual distance is {correct_dist} but calculated pdist distance is {pdist_distance}"
            #         except:
            #             print(
            #                 f"Error caused by unit1 {unit1} and unit2 {unit2} with positions {unit1.position_tuple} and {unit2.position_tuple}"
            #             )
            #             raise

        return self._cached_pdist

    def _get_index_of_two_units(self, unit1: Unit, unit2: Unit):
        assert unit1.tag in self._unit_index_dict, f"Unit1 {unit1} is not in index dict"
        assert unit2.tag in self._unit_index_dict, f"Unit2 {unit2} is not in index dict"
        index1 = self._unit_index_dict[unit1.tag]
        index2 = self._unit_index_dict[unit2.tag]
        condensed_index = self.square_to_condensed(index1, index2)
        return condensed_index

    # Helper functions

    def square_to_condensed(self, i, j):
        # Converts indices of a square matrix to condensed matrix
        # https://stackoverflow.com/a/36867493/10882657
        assert i != j, "No diagonal elements in condensed matrix! Diagonal elements are zero"
        if i < j:
            i, j = j, i
        return self._units_count * j - j * (j + 1) // 2 + i - 1 - j

    def convert_tuple_to_numpy_array(self, pos: Tuple[float, float]):
        """ Converts a single position to a 2d numpy array with 1 row and 2 columns. """
        return np.fromiter(pos, dtype=float, count=2).reshape((1, 2))

    # Fast calculation functions

    def distance_math_hypot(self, p1: Tuple[float, float], p2: Tuple[float, float]):
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    # Distance calculation using the pre-calculated matrix above

    def _distance_squared_unit_to_unit(self, unit1: Unit, unit2: Unit):
        assert unit1.tag != unit2.tag, f"unit1 is unit2: {unit1} == {unit2}, do not check distance for the same unit to save performance"
        # Calculate dict and distances and cache them
        self._unit_index_dict
        self._pdist
        # Calculate index, needs to be after pdist has been calculated and cached
        condensed_index = self._get_index_of_two_units(unit1, unit2)
        # assert self._unit_index_dict[unit1.position_tuple] < self._units_count, f"Index of unit1 {unit1} is larger than amount of units calculated: {self._unit_index_dict[unit1.position_tuple]} < {self._units_count}"
        # assert self._unit_index_dict[unit2.position_tuple] < self._units_count, f"Index of unit2 {unit2} is larger than amount of units calculated: {self._unit_index_dict[unit2.position_tuple]} < {self._units_count}"
        assert condensed_index < len(
            self._cached_pdist
        ), f"Condensed index is larger than amount of calculated distances: {condensed_index} < {len(self._cached_pdist)}, units that caused the assert error: {unit1} and {unit2}"
        distance = self._pdist[condensed_index]
        return distance

    def _distance_squared_pos_to_pos(self, pos1: Tuple[float, float], pos2: Tuple[float, float]):
        # Calculate dict and distances
        self._unit_index_dict
        self._pdist
        assert pos1 in self._unit_index_dict
        assert pos2 in self._unit_index_dict
        condensed_index = self._get_index_of_two_positions(pos1, pos2)
        distance = self._pdist[condensed_index]
        return distance

    # Distance calculation using the fastest distance calculation functions

    def _distance_pos_to_pos(self, pos1: Tuple[float, float], pos2: Tuple[float, float]):
        return self.distance_math_hypot(pos1, pos2)

    def _distance_units_to_pos(self, units: Units, pos: Tuple[float, float]) -> Generator[float, None, None]:
        """ This function does not scale well, if len(units) > 100 it gets fairly slow """
        return (self.distance_math_hypot(u.position_tuple, pos) for u in units)

    def _distance_unit_to_points(
        self, unit: Unit, points: Iterable[Tuple[float, float]]
    ) -> Generator[float, None, None]:
        """ This function does not scale well, if len(points) > 100 it gets fairly slow """
        pos = unit.position_tuple
        return (self.distance_math_hypot(p, pos) for p in points)