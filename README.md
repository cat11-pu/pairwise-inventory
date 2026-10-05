# pairwise-inventory

背包与交易内核示例，只用 Python 标准库实现。

容器由若干格子组成，每格存放一个物品堆叠：物品有每格堆叠上限，格子另有自己的容量上限。
内核提供添加、取出、拆分、交换、压缩空格、容器之间转移，以及双方同时交付的原子交易。

布局：

    inventory/       内核实现
    tests/           验收测试

运行测试（在项目根目录）：

    python3 -m unittest discover -s tests -v
