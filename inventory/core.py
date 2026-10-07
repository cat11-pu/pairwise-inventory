"""背包堆叠与交易原子性内核。

容器由若干格子组成，每格存放一个物品堆叠。每个物品有每格堆叠上限，
每个格子另有自己的容量上限。容器之间转移与双方交易都要求整体生效或整体不生效。
"""

DEFAULT_CAPACITY = 40

MIN_TRADE_DURABILITY = 1

STACK_LIMITS = {
    "potion": 20,
    "arrow": 50,
    "gem": 5,
    "relic": 1,
    "sword": 1,
}


def stack_limit(item_id):
    """返回某物品的每格堆叠上限。"""
    return STACK_LIMITS.get(item_id, 10)


class Stack:
    """一个物品堆叠。"""

    __slots__ = ("item_id", "qty", "bound", "durability")

    def __init__(self, item_id=None, qty=0, bound=False, durability=100):
        self.item_id = item_id
        self.qty = qty
        self.bound = bound
        self.durability = durability

    def is_empty(self):
        """堆叠是否为空。"""
        return self.item_id is None or self.qty <= 0

    def copy(self):
        """返回堆叠的副本。"""
        return Stack(self.item_id, self.qty, self.bound, self.durability)

    def __repr__(self):
        return "Stack(%r, %r)" % (self.item_id, self.qty)


class Slot:
    """容器中的一个格子。"""

    __slots__ = ("capacity", "stack")

    def __init__(self, capacity=DEFAULT_CAPACITY):
        self.capacity = capacity
        self.stack = Stack()

    def is_empty(self):
        """格子是否为空。"""
        return self.stack.is_empty()

    def room(self):
        """格子还剩下的空间。"""
        return self.capacity - self.stack.qty


class Container:
    """一个背包或箱子。"""

    def __init__(self, size=6, capacity=DEFAULT_CAPACITY, name="bag"):
        self.name = name
        self.slots = [Slot(capacity) for _ in range(size)]

    # ---------- 查询 ----------

    def count(self, item_id):
        """统计容器内某物品的总数量。"""
        return sum(s.stack.qty for s in self.slots if s.stack.item_id == item_id)

    def total_units(self):
        """统计容器内的物品总数量。"""
        return sum(s.stack.qty for s in self.slots if not s.is_empty())

    def find(self, item_id):
        """返回第一个匹配的格子。"""
        for slot in self.slots:
            if slot.stack.item_id == item_id:
                return slot
        return None

    def has(self, item_id, qty):
        """判断容器内是否至少有 qty 个该物品。"""
        if qty <= 0:
            return True
        return self.count(item_id) >= qty

    def free_units(self, item_id):
        """统计还能再放入多少个该物品。"""
        limit = stack_limit(item_id)
        room = 0
        for slot in self.slots:
            if slot.is_empty():
                room += min(slot.capacity, limit)
            elif slot.stack.item_id == item_id:
                room += min(max(0, slot.room()), max(0, limit - slot.stack.qty))
        return room

    # ---------- 单容器操作 ----------

    def add_item(self, item_id, qty):
        """放入物品，返回是否全部放入。"""
        if qty <= 0:
            raise ValueError("数量必须为正数")
        if self.free_units(item_id) < qty:
            return False
        remaining = qty
        for slot in self.slots:
            if slot.stack.item_id == item_id:
                take = min(
                    remaining,
                    slot.capacity - slot.stack.qty,
                    stack_limit(item_id) - slot.stack.qty,
                )
                if take > 0:
                    slot.stack.qty += take
                    remaining -= take
                if remaining <= 0:
                    break
        for slot in self.slots:
            if remaining <= 0:
                break
            if slot.is_empty():
                take = min(slot.capacity, stack_limit(item_id), remaining)
                slot.stack = Stack(item_id, take)
                remaining -= take
        return remaining == 0

    def remove_item(self, item_id, qty):
        """取出物品，返回是否成功。"""
        if qty <= 0:
            raise ValueError("数量必须为正数")
        if not self.has(item_id, qty):
            return False
        remaining = qty
        for slot in self.slots:
            if remaining <= 0:
                break
            if slot.stack.item_id == item_id and slot.stack.qty > 0:
                take = min(remaining, slot.stack.qty)
                slot.stack.qty -= take
                remaining -= take
                if slot.stack.qty == 0:
                    slot.stack = Stack()
        return True

    def split(self, index, qty):
        """把某格的一部分拆到另一个空格，返回新格编号。"""
        slot = self.slots[index]
        if slot.is_empty():
            raise ValueError("该格没有可拆分的物品")
        if qty <= 0 or qty >= slot.stack.qty:
            raise ValueError("拆分数必须大于零且小于该格持有量")
        target = -1
        for i, candidate in enumerate(self.slots):
            if candidate.is_empty():
                target = i
                break
        if target < 0:
            raise ValueError("没有空格可以存放拆出的物品")
        target_slot = self.slots[target]
        if qty > min(target_slot.capacity, stack_limit(slot.stack.item_id)):
            raise ValueError("目标格放不下拆出的物品")
        new_stack = Stack(slot.stack.item_id, qty, slot.stack.bound, slot.stack.durability)
        slot.stack.qty -= qty
        target_slot.stack = new_stack
        return target

    def swap(self, i, j):
        """交换两个格子的内容。"""
        if i == j:
            return True
        first = self.slots[i]
        second = self.slots[j]
        if second.stack.qty > first.capacity:
            return False
        if first.stack.qty > second.capacity:
            return False
        first.stack, second.stack = second.stack, first.stack
        return True

    def compact(self):
        """把空格集中到容器末尾。"""
        occupied = [slot.stack.copy() for slot in self.slots if not slot.is_empty()]
        for index, slot in enumerate(self.slots):
            if index < len(occupied):
                slot.stack = occupied[index]
            else:
                slot.stack = Stack()

    # ---------- 容器之间 ----------

    def transfer_to(self, other, item_id, qty):
        """把物品整笔转移到另一个容器。"""
        if qty <= 0:
            raise ValueError("数量必须为正数")
        source_snap = self.snapshot()
        target_snap = other.snapshot()
        if not self.remove_item(item_id, qty):
            self.restore(source_snap)
            other.restore(target_snap)
            return False
        if not other.add_item(item_id, qty):
            self.restore(source_snap)
            other.restore(target_snap)
            return False
        return True

    # ---------- 读写与调整 ----------

    def put(self, index, item_id, qty, bound=False, durability=100):
        """直接写入某格（读档用）。"""
        if not 0 <= index < len(self.slots):
            raise IndexError("格子编号越界")
        if qty <= 0:
            raise ValueError("数量必须为正数")
        self.slots[index].stack = Stack(item_id, qty, bound, durability)

    def set_slot_capacity(self, index, capacity):
        """调整格子的容量上限。"""
        if not 0 <= index < len(self.slots):
            raise IndexError("格子编号越界")
        if capacity <= 0:
            raise ValueError("容量必须为正数")
        self.slots[index].capacity = capacity

    def snapshot(self):
        """返回当前状态的快照。"""
        return [slot.stack.copy() for slot in self.slots]

    def restore(self, snap):
        """恢复到某个快照。"""
        if len(snap) != len(self.slots):
            raise ValueError("快照与容器格数不匹配")
        for slot, stack in zip(self.slots, snap):
            slot.stack = stack.copy()


def is_tradeable(stack):
    """判断堆叠能否参与交易。"""
    if stack.item_id is None or stack.qty <= 0:
        return False
    if stack.bound:
        return False
    if stack.durability < MIN_TRADE_DURABILITY:
        return False
    return True


def _tradeable_count(container, item_id):
    """统计容器内某物品可用于交易的数量。"""
    return sum(
        slot.stack.qty
        for slot in container.slots
        if slot.stack.item_id == item_id and is_tradeable(slot.stack)
    )


def _remove_tradeable(container, item_id, qty):
    """只从未绑定且耐久足够的格子扣减，返回是否成功。"""
    if _tradeable_count(container, item_id) < qty:
        return False
    remaining = qty
    for slot in container.slots:
        if remaining <= 0:
            break
        if slot.stack.item_id == item_id and is_tradeable(slot.stack):
            take = min(remaining, slot.stack.qty)
            slot.stack.qty -= take
            remaining -= take
            if slot.stack.qty == 0:
                slot.stack = Stack()
    return remaining == 0


def trade(left, right, left_offer, right_offer):
    """双方各交出一批物品的原子交易。

    left_offer 与 right_offer 是 (item_id, qty) 的序列。
    """
    for container, offer in ((left, left_offer), (right, right_offer)):
        for item_id, qty in offer:
            if qty <= 0:
                raise ValueError("数量必须为正数")
            if _tradeable_count(container, item_id) < qty:
                return False

    left_snap = left.snapshot()
    right_snap = right.snapshot()

    def rollback():
        left.restore(left_snap)
        right.restore(right_snap)

    for item_id, qty in left_offer:
        if not _remove_tradeable(left, item_id, qty):
            rollback()
            return False
        if not right.add_item(item_id, qty):
            rollback()
            return False
    for item_id, qty in right_offer:
        if not _remove_tradeable(right, item_id, qty):
            rollback()
            return False
        if not left.add_item(item_id, qty):
            rollback()
            return False
    return True
