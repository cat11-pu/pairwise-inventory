"""背包与交易内核的验收测试。"""

import unittest

from inventory.core import Container, trade


def state(container):
    """把容器状态转成可比较的纯数据。"""
    return [
        (slot.stack.item_id, slot.stack.qty, slot.stack.bound, slot.stack.durability)
        for slot in container.slots
    ]


class CoreTests(unittest.TestCase):
    def test_basic_flow_keeps_state_consistent(self):
        bag = Container(size=3, capacity=40)
        self.assertTrue(bag.add_item("potion", 5))
        self.assertTrue(bag.add_item("gem", 3))
        self.assertTrue(bag.remove_item("potion", 2))
        self.assertEqual(bag.count("potion"), 3)
        self.assertEqual(bag.count("gem"), 3)
        self.assertEqual(bag.total_units(), 6)
        with self.assertRaises(ValueError):
            bag.add_item("potion", 0)
        with self.assertRaises(ValueError):
            bag.remove_item("potion", -1)
        self.assertTrue(bag.add_item("potion", 1))
        trader = Container(size=2, capacity=40)
        self.assertTrue(trade(bag, trader, [("potion", 1)], []))
        self.assertEqual(bag.count("potion"), 3)
        self.assertEqual(trader.count("potion"), 1)
        self.assertEqual(bag.total_units() + trader.total_units(), 7)

    def test_add_overflow_uses_another_slot(self):
        bag = Container(size=3, capacity=40)
        self.assertTrue(bag.add_item("potion", 16))
        self.assertTrue(bag.add_item("potion", 8))
        self.assertEqual(bag.count("potion"), 24)
        self.assertEqual([slot.stack.qty for slot in bag.slots], [20, 4, 0])

    def test_has_counts_items_in_every_slot(self):
        bag = Container(size=3, capacity=40)
        bag.put(0, "gem", 4)
        bag.put(1, "gem", 4)
        self.assertTrue(bag.has("gem", 6))
        self.assertFalse(bag.has("gem", 9))
        self.assertEqual(bag.count("gem"), 8)

    def test_remove_reaches_all_slots_without_going_negative(self):
        bag = Container(size=3, capacity=40)
        bag.put(0, "gem", 4)
        bag.put(1, "gem", 4)
        self.assertTrue(bag.remove_item("gem", 6))
        self.assertEqual(bag.count("gem"), 2)
        for slot in bag.slots:
            self.assertGreaterEqual(slot.stack.qty, 0)

    def test_split_rejects_out_of_range_amount(self):
        bag = Container(size=3, capacity=40)
        bag.put(0, "potion", 6)
        with self.assertRaises(ValueError):
            bag.split(0, 0)
        with self.assertRaises(ValueError):
            bag.split(0, -2)
        with self.assertRaises(ValueError):
            bag.split(0, 6)
        with self.assertRaises(ValueError):
            bag.split(0, 7)
        self.assertEqual(bag.count("potion"), 6)
        new_index = bag.split(0, 2)
        self.assertEqual(bag.slots[0].stack.qty, 4)
        self.assertEqual(bag.slots[new_index].stack.item_id, "potion")
        self.assertEqual(bag.slots[new_index].stack.qty, 2)
        self.assertEqual(bag.count("potion"), 6)

    def test_compact_leaves_no_gaps(self):
        bag = Container(size=6, capacity=40)
        bag.put(0, "potion", 5)
        bag.put(3, "arrow", 12)
        bag.put(4, "gem", 3)
        bag.compact()
        self.assertEqual(
            [slot.stack.item_id for slot in bag.slots],
            ["potion", "arrow", "gem", None, None, None],
        )
        self.assertEqual([slot.stack.qty for slot in bag.slots], [5, 12, 3, 0, 0, 0])
        self.assertEqual(bag.total_units(), 20)

    def test_transfer_is_all_or_nothing(self):
        src = Container(size=3, capacity=40)
        src.put(0, "gem", 4)
        src.put(1, "gem", 4)
        dst = Container(size=2, capacity=40)
        self.assertTrue(src.transfer_to(dst, "gem", 6))
        self.assertEqual(src.count("gem"), 2)
        self.assertEqual(dst.count("gem"), 6)

        src2 = Container(size=3, capacity=40)
        src2.put(0, "gem", 4)
        src2.put(1, "gem", 4)
        full = Container(size=1, capacity=40)
        full.put(0, "gem", 4)
        before_src = state(src2)
        before_full = state(full)
        self.assertFalse(src2.transfer_to(full, "gem", 6))
        self.assertEqual(state(src2), before_src)
        self.assertEqual(state(full), before_full)

    def test_swap_rejects_stacks_that_do_not_fit(self):
        bag = Container(size=2, capacity=40)
        bag.set_slot_capacity(1, 10)
        bag.put(0, "arrow", 25)
        bag.put(1, "arrow", 4)
        before = state(bag)
        self.assertFalse(bag.swap(0, 1))
        self.assertEqual(state(bag), before)

        other = Container(size=2, capacity=40)
        other.put(0, "potion", 5)
        other.put(1, "gem", 3)
        self.assertTrue(other.swap(0, 1))
        self.assertEqual(other.slots[0].stack.item_id, "gem")
        self.assertEqual(other.slots[1].stack.item_id, "potion")

    def test_trade_rejects_bound_or_worn_items(self):
        left = Container(size=3, capacity=40)
        left.put(0, "potion", 5, bound=True, durability=100)
        right = Container(size=2, capacity=40)
        before_left = state(left)
        before_right = state(right)
        self.assertFalse(trade(left, right, [("potion", 5)], []))
        self.assertEqual(state(left), before_left)
        self.assertEqual(state(right), before_right)

        left.put(0, "potion", 5, durability=0)
        before_left = state(left)
        self.assertFalse(trade(left, right, [("potion", 5)], []))
        self.assertEqual(state(left), before_left)

    def test_failed_trade_leaves_both_sides_untouched(self):
        left = Container(size=2, capacity=40)
        left.put(0, "potion", 12)
        right = Container(size=1, capacity=40)
        right.put(0, "potion", 16)
        before_left = state(left)
        before_right = state(right)
        self.assertFalse(trade(left, right, [("potion", 8)], []))
        self.assertEqual(state(left), before_left)
        self.assertEqual(state(right), before_right)


if __name__ == "__main__":
    unittest.main()
