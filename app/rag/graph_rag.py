"""
graph_rag.py — Day 2: GraphRAG（知识图谱构建 + 图增强检索）

对比传统 RAG（chunk 向量检索）：

        传统 RAG                          GraphRAG
  ┌──────────────────┐            ┌──────────────────────┐
  │ 检索孤立 chunk    │            │ 实体 + 关系构成图谱     │
  │ (文本片段，无关系) │            │ 检索 = 图遍历 (BFS)    │
  │ 擅长单点事实问答   │            │ 擅长多跳关系问答        │
  └──────────────────┘            └──────────────────────┘

核心流程（4 步）：
  1. 实体抽取：从文本提取实体（部门 / 制度 / 时间 / 数字）
  2. 关系抽取：提取实体之间的关系（负责 / 规定 / 发放 / 需要）
  3. 图构建：NetworkX Graph（节点=实体，边=关系）
  4. 图增强检索：问题命中实体 → BFS 遍历 1-2 跳邻居 → 拼接上下文

示例：
  问题: "哪个部门负责审批年假？"
  1. 实体命中: "年假"
  2. BFS 遍历: 年假 → 人事部（边: 负责审批）
  3. 上下文: 包含"人事部负责审批年假"
  4. 传统 RAG 需要措辞完全匹配才能找到这条跨 chunk 的关系链
"""

import re
import networkx as nx

from app.rag.loader.loader_factory import get_loader


# ============================================
# 1. 实体抽取（基于词典 + 规则）
# ============================================

# 预定义实体词典（按类型分类）
ENTITY_DICT = {
    "部门": ["人事部", "财务部", "行政部门", "部门负责人"],
    "制度": ["年假", "病假", "工资", "绩效奖金", "福利补贴", "试用期", "带薪年假"],
    "时间": ["15日", "一个月", "三个月", "7天", "一年"],
    "文档": ["身份证明", "学历证明", "银行卡信息", "医院证明"],
}

# 预定义关系词典（词 → 标准关系名）
RELATION_DICT = {
    "负责": "负责",
    "负责审批": "负责审批",
    "审批": "审批",
    "规定": "规定",
    "发放": "发放",
    "需要": "需要",
    "组成": "组成",
    "享有": "享有",
    "提交": "提交",
}


def extract_entities(text: str) -> list[str]:
    """
    从文本中抽取实体（基于词典匹配）。

    参数:
      text: 原始文本

    返回:
      ["人事部", "年假", "15日", ...] 去重后的实体列表
    """
    entities = []
    for _type, words in ENTITY_DICT.items():
        for word in words:
            if word in text and word not in entities:
                entities.append(word)
    return entities


def extract_relations(text: str, entities: list[str]) -> list[tuple]:
    """
    从文本中抽取实体之间的关系。

    简单规则：若一句话中同时出现两个实体和一个关系词，
    则认为这两个实体之间存在该关系。

    参数:
      text: 原始文本
      entities: extract_entities 抽取的实体列表

    返回:
      [("人事部", "负责审批", "年假"), ...] 关系三元组列表
    """
    relations = []

    # 按句子切分（简单按句号/换行切分）
    sentences = re.split(r"[。\n；;]", text)

    for sentence in sentences:
        # 找出该句中的实体
        sent_entities = [e for e in entities if e in sentence]
        # 找出该句中的关系词
        found_relations = [
            relation for word, relation in RELATION_DICT.items()
            if word in sentence
        ]

        # 若同时有 >=2 个实体和 >=1 个关系词，建立关系
        # 用关系词连接实体对（简化：取句中的前两个实体）
        if len(sent_entities) >= 2 and found_relations:
            # ⭐ 取最长匹配的关系词（更具体）：
            #    "负责审批年假" 同时含 "负责" 和 "负责审批"，
            #    必须选 "负责审批"，否则关系语义不准确
            relation = max(found_relations, key=len)
            # 实体对两两建立关系（简化处理）
            for i in range(len(sent_entities)):
                for j in range(i + 1, len(sent_entities)):
                    relations.append((sent_entities[i], relation, sent_entities[j]))

    # 去重
    return list(dict.fromkeys(relations))


# ============================================
# 2. 图构建（NetworkX）
# ============================================

class KnowledgeGraph:
    """
    知识图谱：基于 NetworkX 封装实体 + 关系。

    用法:
      kg = KnowledgeGraph()
      kg.build_from_text("公司员工福利政策手册...")
      kg.enhanced_retrieve("哪个部门负责审批年假？")
    """

    def __init__(self):
        self.graph = nx.Graph()
        self.entity_type = {}  # 实体 → 类型（用于显示）

    def build_from_text(self, text: str):
        """
        从原始文本构建知识图谱。

        流程: 实体抽取 → 关系抽取 → 建图
        """
        # 1. 实体抽取
        entities = extract_entities(text)
        for e in entities:
            self.graph.add_node(e)
            # 记录实体类型
            for etype, words in ENTITY_DICT.items():
                if e in words:
                    self.entity_type[e] = etype

        # 2. 关系抽取
        relations = extract_relations(text, entities)
        for src, rel, dst in relations:
            # 若节点不存在则添加（关系抽取可能用到词典外实体）
            self.graph.add_node(src)
            self.graph.add_node(dst)
            # 添加带关系的边（属性存关系名）
            self.graph.add_edge(src, dst, relation=rel)

        return self

    def build_from_file(self, file_path: str) -> "KnowledgeGraph":
        """
        从文件构建知识图谱（复用 loader 读取）。
        """
        loader = get_loader(file_path)
        documents = loader.load(file_path)
        full_text = "\n".join(doc["text"] for doc in documents)
        return self.build_from_text(full_text)

    # ---------- 图增强检索 ----------

    def enhanced_retrieve(self, query: str, depth: int = 2, top_k: int = 3) -> list[dict]:
        """
        图增强检索：实体命中 → BFS 图遍历 → 拼接关联上下文。

        参数:
          query: 查询问题
          depth: BFS 遍历深度（1-2 跳）
          top_k: 返回的关联实体数量

        返回:
          [{"entity": "年假", "type": "制度", "neighbors": [...], "text": "..."}, ...]
        """
        # 1. 实体命中：从问题中匹配图谱里的实体
        matched = self._match_entities(query)
        if not matched:
            return []

        # 2. 对每个命中实体做 BFS 图遍历
        results = []
        for entity in matched[:top_k]:
            neighbors = self._bfs_neighbors(entity, depth)
            results.append({
                "entity": entity,
                "type": self.entity_type.get(entity, "未知"),
                "neighbors": neighbors,
                "text": self._entity_to_text(entity, neighbors),
            })

        return results

    def _match_entities(self, query: str) -> list[str]:
        """从问题中匹配图谱中存在的实体。"""
        matched = []
        for node in self.graph.nodes:
            if node in query and node not in matched:
                matched.append(node)
        # 按问题中出现的顺序返回（保持可读性）
        return matched

    def _bfs_neighbors(self, entity: str, depth: int) -> list[dict]:
        """
        BFS 遍历实体的邻居（1-2 跳）。

        返回:
          [{"entity": "人事部", "relation": "负责审批", "depth": 1}, ...]
        """
        if entity not in self.graph:
            return []

        neighbors = []
        visited = {entity}

        # BFS 队列: (节点, 深度)
        queue = [(entity, 0)]
        while queue:
            node, d = queue.pop(0)
            if d >= depth:
                continue
            for neighbor in self.graph.neighbors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    rel = self.graph[node][neighbor].get("relation", "关联")
                    neighbors.append({
                        "entity": neighbor,
                        "relation": rel,
                        "depth": d + 1,
                    })
                    queue.append((neighbor, d + 1))

        return neighbors

    def _entity_to_text(self, entity: str, neighbors: list[dict]) -> str:
        """把实体 + 邻居拼成可读的图检索上下文。"""
        if not neighbors:
            return f"[实体] {entity}（{self.entity_type.get(entity, '未知')}）"

        lines = [f"[实体] {entity}（{self.entity_type.get(entity, '未知')}）"]
        for n in neighbors:
            lines.append(f"  → ({n['relation']}) {n['entity']}（{self.entity_type.get(n['entity'], '未知')}）")
        return "\n".join(lines)

    # ---------- 图统计 ----------

    def stats(self) -> dict:
        """返回图的统计信息。"""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": {
                etype: sum(1 for e in self.entity_type.values() if e == etype)
                for etype in set(self.entity_type.values())
            },
        }


# ============================================
# 3. 便捷函数
# ============================================

def build_knowledge_graph(file_path: str) -> KnowledgeGraph:
    """
    一键构建知识图谱。

    用法:
      kg = build_knowledge_graph("data/employee_policy.txt")
      kg.stats()  # 查看图统计
      results = kg.enhanced_retrieve("哪个部门负责审批年假？")
    """
    return KnowledgeGraph().build_from_file(file_path)


def demo_graph_rag():
    """演示：构建图谱 + 图增强检索。"""
    kg = build_knowledge_graph("data/employee_policy.txt")

    print("=" * 60)
    print("知识图谱统计:", kg.stats())
    print("=" * 60)

    # 测试多个查询
    for query in ["哪个部门负责审批年假？", "工资什么时候发放？", "试用期多久？"]:
        print(f"\n问题: {query}")
        results = kg.enhanced_retrieve(query)
        if not results:
            print("  → 未命中实体")
        for r in results:
            print(f"  命中实体: {r['entity']}（{r['type']}）")
            print(f"  {r['text']}")


if __name__ == "__main__":
    demo_graph_rag()
