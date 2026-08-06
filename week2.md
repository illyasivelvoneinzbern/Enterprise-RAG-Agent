Embedding模型把文本映射到高维向量空间，语义相近的文本在空间中的距离更近，因此可以通过向量相似度计算找到相关内容。
因为LLM本身不知道企业私有数据，而且直接输入大量文档会造成context限制、成本增加和检索效率下降。RAG通过检索相关知识片段增强LLM生成。
文档加载

↓

文本切割

↓

Embedding

↓

向量数据库

↓

用户query

↓

query embedding

↓

向量相似度搜索

↓

top-k chunk

↓

拼接prompt

↓

LLM生成
为什么RAG需要chunk？
因为文档过长无法直接作为LLM上下文，同时整体embedding会降低检索粒度。切分成chunk后，可以针对用户问题检索相关片段。
chunk太大会引入无关信息降低召回精度，太小会导致上下文缺失，需要根据文档类型调整。
overlap:防止重要信息位于切割边界时被分割，保持chunk之间的语义连续性。
FAISS主要存储embedding向量，并通过向量距离计算找到相似向量。实际RAG系统还会额外保存文本和metadata。
top-k：因为一个问题可能对应多个相关片段，选择多个候选chunk可以提高召回率，同时避免把大量无关内容送入LLM。
不同Embedding模型生成的向量空间不同，维度和语义表示方式可能不同。旧向量无法和新模型生成的query embedding进行有效比较，因此需要重新embedding文档。、
Metadata是描述文档片段属性的信息，例如来源文件、页码、时间、作者等，用于追踪来源和增强检索结果。
FAISS本质是向量索引，只负责高效相似度搜索，不负责存储业务数据，因此需要额外维护向量与文档metadata的映射
rag 引用来源在文档加载阶段生成metadata，包括source、page等字段，随后随着chunk一起进入向量库检索流程，生成答案时从metadata中返回来源信息。