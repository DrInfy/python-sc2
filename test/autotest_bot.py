import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import random
import logging

import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer
from sc2.data import Alliance

from sc2.position import Pointlike, Point2, Point3
from sc2.units import Units
from sc2.unit import Unit

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.effect_id import EffectId

from sc2.dicts.unit_trained_from import UNIT_TRAINED_FROM

logger = logging.getLogger(__name__)


class TestBot(sc2.BotAI):
    def __init__(self):
        sc2.BotAI.__init__(self)
        # The time the bot has to complete all tests, here: the number of game seconds
        self.game_time_timeout_limit = 3 * 60  # 3 minutes

        # Check how many test action functions we have
        # At least 4 tests because we test properties and variables
        self.tests_target = 4 + len(
            [True for index in range(1000) if hasattr(getattr(self, f"test_botai_actions{index}", 0), "__call__")]
        )
        self.tests_done_by_name = set()

        # Keep track of the action index and when the last action was started
        self.current_action_index = 1
        self.iteration_last_action_started = 8
        # There will be 20 iterations of the bot doing nothing between tests
        self.iteration_wait_time_between_actions = 20

        self.scv_action_list = ["move", "patrol", "attack", "hold", "scan_move"]

    async def on_start(self):
        await self.distribute_workers()

    async def on_step(self, iteration):
        if iteration == 0:
            await self.chat_send("(glhf)")
        # Test if chat message was sent correctly
        if iteration == 1:
            assert len(self.state.chat) >= 1, self.state.chat

        # Tests at start
        if iteration == 3:
            # No need to use try except as the travis test script checks for "Traceback" in STDOUT
            await self.test_botai_properties()
            await self.test_botai_functions()
            await self.test_game_state_static_variables()
            await self.test_game_info_static_variables()

        # Test actions
        if iteration > 7:
            # Skip and wait because some effects from last action might still be active, e.g. reaper grenade
            if iteration - self.iteration_last_action_started > self.iteration_wait_time_between_actions:

                # Execute actions on even iterations, test if actions were successful on uneven iterations
                if iteration % 2 == 0:
                    action_execute_function_name = f"test_botai_actions{self.current_action_index}"
                    action_execute_function = getattr(self, action_execute_function_name, None)
                    if action_execute_function is not None:
                        await action_execute_function()
                else:
                    action_test_function_name = f"test_botai_actions{self.current_action_index}_successful"
                    action_test_function = getattr(self, action_test_function_name, None)
                    if action_test_function is not None:
                        success = await action_test_function()
                        if success:
                            self.tests_done_by_name.add(f"test_botai_actions{self.current_action_index}_successful")
                            self.current_action_index += 1
                            self.iteration_last_action_started = iteration

        # End when all tests successful
        if len(self.tests_done_by_name) >= self.tests_target:
            print(
                "{}/{} Tests completed after {} seconds: {}".format(
                    len(self.tests_done_by_name), self.tests_target, round(self.time, 1), self.tests_done_by_name
                )
            )
            exit(0)

        # End time reached, cancel testing and report error: took too long
        if self.time >= self.game_time_timeout_limit:
            print(
                "{}/{} Tests completed: {}\nCurrent action index is at {}".format(
                    len(self.tests_done_by_name), self.tests_target, self.tests_done_by_name, self.current_action_index
                )
            )
            print("Not all tests were successful. Timeout reached. Testing was aborted")
            exit(1000)

    # Test BotAI properties, starting conditions
    async def test_botai_properties(self):
        assert 1 <= self.player_id <= 2, self.player_id
        assert self.race == Race.Terran, self.race
        assert 0 <= self.time <= 180, self.time
        assert self.start_location == self.townhalls.random.position, (
            self.start_location,
            self.townhalls.random.position,
        )
        for loc in self.enemy_start_locations:
            assert isinstance(loc, Point2), loc
            assert loc.distance_to(self.start_location) > 20, (loc, self.start_location)
        assert self.main_base_ramp.top_center.distance_to(self.start_location) < 30, self.main_base_ramp.top_center
        assert self.can_afford(UnitTypeId.SCV)
        assert self.owned_expansions == {self.townhalls.first.position: self.townhalls.first}
        # Test if bot start location is in expansion locations
        assert self.townhalls.random.position in set(self.expansion_locations.keys())
        # Test if enemy start locations are in expansion locations
        for location in self.enemy_start_locations:
            assert location in set(self.expansion_locations.keys())

        self.tests_done_by_name.add("test_botai_properties")

    # Test BotAI functions
    async def test_botai_functions(self):
        for location in self.expansion_locations.keys():
            # Can't build on spawn locations, skip these
            if location in self.enemy_start_locations or location == self.start_location:
                continue
            assert await self.can_place(UnitTypeId.COMMANDCENTER, location)
            await self.find_placement(UnitTypeId.COMMANDCENTER, location)
        assert len(await self.get_available_abilities(self.workers)) == self.workers.amount
        self.tests_done_by_name.add("test_botai_functions")

    # Test self.state variables
    async def test_game_state_static_variables(self):
        assert len(self.state.actions) == 0, self.state.actions
        assert len(self.state.action_errors) == 0, self.state.action_errors
        assert len(self.state.chat) == 0, self.state.chat
        assert self.state.game_loop > 0, self.state.game_loop
        assert self.state.score.collection_rate_minerals >= 0, self.state.score.collection_rate_minerals
        assert len(self.state.upgrades) == 0, self.state.upgrades
        self.tests_done_by_name.add("test_game_state_static_variables")

    # Test self._game_info variables
    async def test_game_info_static_variables(self):
        assert len(self._game_info.players) == 2, self._game_info.players
        assert len(self._game_info.map_ramps) >= 2, self._game_info.map_ramps
        assert len(self._game_info.player_races) == 2, self._game_info.player_races
        self.tests_done_by_name.add("test_game_info_static_variables")

    # Test BotAI action: train SCV
    async def test_botai_actions1(self):
        if self.can_afford(UnitTypeId.SCV):
            self.do(self.townhalls.random.train(UnitTypeId.SCV))

    async def test_botai_actions1_successful(self):
        if self.already_pending(UnitTypeId.SCV) > 0:
            return True

    # Test BotAI action: move all SCVs to center of map
    async def test_botai_actions2(self):
        center = self._game_info.map_center
        scv: Unit
        for index, scv in enumerate(self.workers):
            if index > len(self.scv_action_list):
                self.do(scv.stop())
            action = self.scv_action_list[index % len(self.scv_action_list)]
            if action == "move":
                self.do(scv.move(center))
            elif action == "patrol":
                self.do(scv.patrol(center))
            elif action == "attack":
                self.do(scv.attack(center))
            elif action == "hold":
                self.do(scv.hold_position())
            elif action == "scan_move":
                self.do(scv.scan_move(center))

    async def test_botai_actions2_successful(self):
        def temp_filter(unit: Unit):
            return (
                unit.is_moving
                or unit.is_patrolling
                or unit.orders
                and unit.orders[0] == AbilityId.HOLDPOSITION_HOLD
                or unit.is_attacking
            )

        if self.units.filter(lambda unit: temp_filter(unit)).amount >= len(self.scv_action_list):
            return True

    # Test BotAI action: move some scvs to the center, some to minerals
    async def test_botai_actions3(self):
        center = self._game_info.map_center
        scvs = self.workers
        scvs1 = scvs[:6]
        scvs2 = scvs[6:]
        for scv in scvs1:
            self.do(scv.move(center))
        mf = self.mineral_field.closest_to(self.townhalls.random)
        for scv in scvs2:
            self.do(scv.gather(mf))

    async def test_botai_actions3_successful(self):
        if self.units.filter(lambda x: x.is_moving).amount >= 6 and self.units.gathering.amount >= 6:
            return True

    # Test BotAI action: move all SCVs to mine minerals near townhall
    async def test_botai_actions4(self):
        mf = self.mineral_field.closest_to(self.townhalls.random)
        for scv in self.workers:
            self.do(scv.gather(mf))

    async def test_botai_actions4_successful(self):
        if self.units.gathering.amount >= 12:
            logger.warning("Action test 04 successful.")
            return True

    # Test BotAI action: self.expand_now() which tests for get_next_expansion, select_build_worker, can_place, find_placement, build and can_afford
    async def test_botai_actions5(self):
        if self.can_afford(UnitTypeId.COMMANDCENTER) and not self.already_pending(UnitTypeId.COMMANDCENTER):
            await self.get_next_expansion()
            await self.expand_now()

    async def test_botai_actions5_successful(self):
        if self.townhalls(UnitTypeId.COMMANDCENTER).amount >= 2:
            logger.warning("Action test 05 successful.")
            return True

    # Test if reaper grenade shows up in effects
    async def test_botai_actions6(self):
        center = self._game_info.map_center
        if self.units(UnitTypeId.REAPER).amount < 10:
            await self._client.debug_create_unit([[UnitTypeId.REAPER, 10, center, 1]])
        for reaper in self.units(UnitTypeId.REAPER):
            self.do(reaper(AbilityId.KD8CHARGE_KD8CHARGE, center))

    async def test_botai_actions6_successful(self):
        if len(self.state.effects) > 0:
            # print(f"Effects: {self.state.effects}")
            for effect in self.state.effects:
                # print(f"Effect: {effect}")
                pass
            # Cleanup
            logger.warning("Action test 06 successful.")
            await self._client.debug_kill_unit(self.units(UnitTypeId.REAPER))
            return True

    # Test ravager effects
    async def test_botai_actions7(self):
        center = self._game_info.map_center
        if self.units(UnitTypeId.RAVAGER).amount < 10:
            await self._client.debug_create_unit([[UnitTypeId.RAVAGER, 10, center, 1]])
        for reaper in self.units(UnitTypeId.RAVAGER):
            self.do(reaper(AbilityId.EFFECT_CORROSIVEBILE, center))

    async def test_botai_actions7_successful(self):
        success = False
        if len(self.state.effects) >= 1:
            # print(f"Effects: {self.state.effects}")
            for effect in self.state.effects:
                # print(f"Effect: {effect}")
                if effect.id == EffectId.RAVAGERCORROSIVEBILECP:
                    success = True
        if success:
            # Cleanup
            logger.warning("Action test 07 successful.")
            await self._client.debug_kill_unit(self.units(UnitTypeId.RAVAGER))
            return True

    # Test if train function works on hatchery, lair, hive
    async def test_botai_actions8(self):
        center = self._game_info.map_center
        if not self.structures(UnitTypeId.HIVE):
            await self._client.debug_create_unit([[UnitTypeId.HIVE, 1, center, 1]])
        if not self.structures(UnitTypeId.LAIR):
            await self._client.debug_create_unit([[UnitTypeId.LAIR, 1, center, 1]])
        if not self.structures(UnitTypeId.HATCHERY):
            await self._client.debug_create_unit([[UnitTypeId.HATCHERY, 1, center, 1]])
        if not self.structures(UnitTypeId.SPAWNINGPOOL):
            await self._client.debug_create_unit([[UnitTypeId.SPAWNINGPOOL, 1, center, 1]])

        townhalls = self.structures.of_type({UnitTypeId.HIVE, UnitTypeId.LAIR, UnitTypeId.HATCHERY})
        if townhalls.amount == 3 and self.minerals >= 450 and not self.already_pending(UnitTypeId.QUEEN):
            self.train(UnitTypeId.QUEEN, amount=3)
            # Equivalent to:
            # for townhall in townhalls:
            #     self.do(townhall.train(UnitTypeId.QUEEN), subtract_cost=True, subtract_supply=True)

    async def test_botai_actions8_successful(self):
        success = False
        if self.already_pending(UnitTypeId.QUEEN) == 3:
            success = True

        if success:
            # Cleanup
            logger.warning("Action test 08 successful.")
            townhalls = self.structures.of_type({UnitTypeId.HIVE, UnitTypeId.LAIR, UnitTypeId.HATCHERY})
            queens = self.units(UnitTypeId.QUEEN)
            pool = self.structures(UnitTypeId.SPAWNINGPOOL)
            await self._client.debug_kill_unit(townhalls | queens | pool)
            return True

    # Morph an archon from 2 high templars
    async def test_botai_actions9(self):
        center = self._game_info.map_center
        target_amount = 2
        HTs = self.units(UnitTypeId.HIGHTEMPLAR)
        if HTs.amount < target_amount:
            await self._client.debug_create_unit([[UnitTypeId.HIGHTEMPLAR, target_amount - HTs.amount, center, 1]])

        else:
            for ht in HTs:
                self.do(ht(AbilityId.MORPH_ARCHON))

    async def test_botai_actions9_successful(self):
        success = False
        archons = self.units(UnitTypeId.ARCHON)
        if archons.amount == 1:
            success = True

        if success:
            # Cleanup
            logger.warning("Action test 09 successful.")
            await self._client.debug_kill_unit(archons)
            return True

    # Morph 400 banelings from 400 lings in the same frame
    async def test_botai_actions10(self):
        center = self._game_info.map_center
        target_amount = 400
        bane_nests = self.structures(UnitTypeId.BANELINGNEST)
        lings = self.units(UnitTypeId.ZERGLING)
        banes = self.units(UnitTypeId.BANELING)
        bane_cocoons = self.units(UnitTypeId.BANELINGCOCOON)

        # Cheat money, need 10k/10k to morph 400 lings to 400 banes
        if not banes and not bane_cocoons:
            if self.minerals < 10_000:
                await self.client.debug_all_resources()
            elif self.vespene < 10_000:
                await self.client.debug_all_resources()

        # Spawn units
        if not bane_nests:
            await self._client.debug_create_unit([[UnitTypeId.BANELINGNEST, 1, center, 1]])
        if banes.amount + bane_cocoons.amount + lings.amount < target_amount:
            await self._client.debug_create_unit([[UnitTypeId.ZERGLING, target_amount - lings.amount, center, 1]])

        if lings.amount >= target_amount and self.minerals >= 10_000 and self.vespene >= 10_000:
            for ling in lings:
                self.do(ling(AbilityId.MORPHZERGLINGTOBANELING_BANELING), subtract_cost=True)

    async def test_botai_actions10_successful(self):
        success = False
        target_amount = 400
        bane_nests = self.structures(UnitTypeId.BANELINGNEST)
        lings = self.units(UnitTypeId.ZERGLING)
        banes = self.units(UnitTypeId.BANELING)
        bane_cocoons = self.units(UnitTypeId.BANELINGCOCOON)
        if banes.amount >= target_amount:
            success = True

        if success:
            # Cleanup
            logger.warning("Action test 10 successful.")
            await self._client.debug_kill_unit(lings | banes | bane_nests | bane_cocoons)
            return True

    # TODO:
    # self.can_cast function
    # Test client.py debug functions
    # Test if events work (upgrade complete, unit complete, building complete, building started)
    # Test if functions with various combinations works (e.g. already_pending)
    # Test self.train function on: larva, hatchery + lair (queens), 2 barracks (2 marines), 2 nexus (probes)
    # Test self.research function on: ebay, hatchery, forge, evo chamber


def main():
    sc2.run_game(
        sc2.maps.get("Acropolis"), [Bot(Race.Terran, TestBot()), Computer(Race.Zerg, Difficulty.Easy)], realtime=False
    )


if __name__ == "__main__":
    main()
