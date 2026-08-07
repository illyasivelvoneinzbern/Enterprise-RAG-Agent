向量搜索只能根据语义相似度召回候选文档，不一定代表答案相关性，因此需要 reranker 进行二次排序。
Retriever 返回 top10，而最终只给 LLM top3
第一阶段追求 Recall，第二阶段追求 Precision，减少无关上下文进入 Prompt，降低 token 消耗并提高回答准确率。
Embedding	Reranker
目的	召回	排序
速度	快	慢
输入	query/doc分别编码	query+doc一起
阶段	第一阶段	第二阶段
通过 Loader 抽象统一不同数据源接口，新增格式时只需要增加新的 Loader，不需要修改 RAG 主流程，符合开闭原则。
为什么流式输出完成后还需要保存 Memory？
因为 yield 返回的是分片结果，Memory需要保存完整 assistant response，供下一轮上下文使用。
为什么 RAG 检索不能和 LLM streaming 同时开始？
因为 LLM 生成前需要完整 prompt，而 prompt 依赖检索结果。