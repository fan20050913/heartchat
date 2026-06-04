"""
RAG 知识库引擎
从 .xlsx 加载问答对，通过千问 text-embedding-v3 生成向量，
存入本地 ChromaDB，在对话前检索相关知识注入 AI 的 system prompt。
"""

import sys
from pathlib import Path

import pandas as pd
import chromadb
from chromadb.config import Settings as ChromaSettings
from PySide6.QtCore import QObject, Signal

from config.settings import settings


class RAGEngine(QObject):
    """RAG 知识库引擎：xlsx → 向量 → ChromaDB → 检索。"""

    build_started = Signal()
    build_completed = Signal(int)    # 条目数
    build_error = Signal(str)        # 错误信息

    DEFAULT_TOP_K = 3
    BATCH_SIZE = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._collection = None
        self._client = None

        self._collection_name = settings.CURRENT_CHARACTER + "_kb"
        self._xlsx_path = Path(settings.XLSX_PATH)
        self._vector_path = Path(settings.VECTOR_STORE_PATH)

        self._init_chromadb()

    # ── 公开接口 ──────────────────────────────────────────

    def initialize(self) -> bool:
        """启动时调用：ChromaDB 已有数据 → 就绪；否则从 xlsx 构建。"""
        if self._ready:
            return True

        if not self._xlsx_path.exists():
            print(f"[RAG] 知识库文件不存在: {self._xlsx_path}，RAG 已禁用")
            return False

        print("[RAG] 开始构建知识库...")
        self.build_started.emit()
        self._build_knowledge_base()
        return self._ready

    def query(self, text: str, top_k: int | None = None) -> str:
        """检索与用户问题最相关的知识，返回格式化上下文文本。"""
        if not self._ready or self._collection is None:
            return ""

        k = top_k or self.DEFAULT_TOP_K
        try:
            vector = self._get_embedding(text)
            count = self._collection.count()
            results = self._collection.query(
                query_embeddings=[vector],
                n_results=min(k, count),
            )

            if not results["documents"] or not results["documents"][0]:
                return ""

            metadatas = results["metadatas"][0] if results.get("metadatas") else []
            documents = results["documents"][0]

            parts = []
            for i, answer in enumerate(documents):
                question = metadatas[i].get("question", f"相关知识 {i+1}") if i < len(metadatas) else f"相关知识 {i+1}"
                parts.append(f"Q: {question}\nA: {answer}")

            return "\n\n".join(parts)

        except Exception as e:
            print(f"[RAG] 检索出错: {e}", file=sys.stderr)
            return ""

    def is_ready(self) -> bool:
        return self._ready

    def collection_count(self) -> int:
        if self._collection is not None:
            try:
                return self._collection.count()
            except Exception:
                pass
        return 0

    def switch_to_character(self, character_id: str, xlsx_path: str):
        """切换角色知识库：已有缓存则加载，否则从 xlsx 构建。"""
        self._collection_name = f"{character_id}_kb"
        self._xlsx_path = Path(xlsx_path)
        self._ready = False
        self._collection = None

        if self._client is None:
            print(f"[RAG] ChromaDB 未初始化，{character_id} 知识库不可用")
            return False

        # 1. 尝试加载本地缓存的 collection
        try:
            self._collection = self._client.get_collection(self._collection_name)
            cached_count = self._collection.count()
            xlsx_count = self._count_xlsx_rows()

            if cached_count > 0 and cached_count == xlsx_count:
                self._ready = True
                print(f"[RAG] 加载本地知识库 ({character_id}): {cached_count} 条")
                return True

            # 数量不匹配 → 缓存过期，重建
            if cached_count > 0 and xlsx_count > 0:
                print(f"[RAG] 知识库数量变化 ({cached_count}→{xlsx_count})，重新构建...")
        except chromadb.errors.NotFoundError:
            pass

        # 2. 没有缓存或缓存过期，从 xlsx 构建
        if self._xlsx_path.exists():
            print(f"[RAG] 构建 {character_id} 知识库...")
            self._build_knowledge_base()
            return self._ready

        print(f"[RAG] {character_id} 无知识库文件，RAG 已禁用")
        return False

    def _count_xlsx_rows(self) -> int:
        """快速统计 xlsx 有效问答行数（用于判断缓存是否过期）。"""
        try:
            import pandas as pd
            df = pd.read_excel(self._xlsx_path, dtype=str)
            if df.empty:
                return 0
            cols = {c.strip().lower(): c for c in df.columns}
            q_col = cols.get("question") or cols.get("问题") or df.columns[0]
            a_col = cols.get("answer") or cols.get("答案") or df.columns[1]
            count = 0
            for _, row in df.iterrows():
                q = str(row[q_col]).strip() if pd.notna(row[q_col]) else ""
                a = str(row[a_col]).strip() if pd.notna(row[a_col]) else ""
                if q and a:
                    count += 1
            return count
        except Exception:
            return 0

    # ── ChromaDB 初始化 ────────────────────────────────────

    def _init_chromadb(self):
        """打开持久化 ChromaDB 存储（不加载任何 collection）。"""
        try:
            self._vector_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self._vector_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        except Exception as e:
            print(f"[RAG] ChromaDB 初始化失败: {e}", file=sys.stderr)
            self._client = None

    # ── 知识库构建 ────────────────────────────────────────

    def _build_knowledge_base(self):
        """完整构建流程：加载 xlsx → 嵌入 → 写入 ChromaDB。"""
        if self._client is None:
            msg = "ChromaDB 未初始化，无法构建知识库"
            print(f"[RAG] {msg}", file=sys.stderr)
            self.build_error.emit(msg)
            return

        try:
            pairs = self._load_xlsx()
            if not pairs:
                msg = "知识库文件为空或格式不正确"
                print(f"[RAG] {msg}", file=sys.stderr)
                self.build_error.emit(msg)
                return

            questions = [q for q, a in pairs]
            answers = [a for q, a in pairs]

            embeddings = self._get_embeddings_batch(questions)
            if not embeddings:
                msg = "Embedding 生成失败"
                self.build_error.emit(msg)
                return

            # 重建 collection
            try:
                self._client.delete_collection(self._collection_name)
            except Exception:
                pass
            self._collection = self._client.create_collection(self._collection_name)

            ids = [f"qa_{i}" for i in range(len(pairs))]
            metadatas = [{"question": q} for q in questions]

            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=answers,
                metadatas=metadatas,
            )

            count = len(pairs)
            self._ready = True
            print(f"[RAG] 知识库构建完成: {count} 条")
            self.build_completed.emit(count)

        except Exception as e:
            msg = f"知识库构建失败: {e}"
            print(f"[RAG] {msg}", file=sys.stderr)
            self.build_error.emit(msg)

    # ── xlsx 加载 ─────────────────────────────────────────

    def _load_xlsx(self) -> list[tuple[str, str]]:
        """读取 xlsx，返回 [(question, answer), ...]。"""
        try:
            df = pd.read_excel(self._xlsx_path, dtype=str)
        except Exception as e:
            print(f"[RAG] 读取 xlsx 失败: {e}", file=sys.stderr)
            return []

        if df.empty:
            return []

        # 列名归一化
        cols = {c.strip().lower(): c for c in df.columns}

        q_col = cols.get("question") or cols.get("问题")
        a_col = cols.get("answer") or cols.get("答案")

        # 如果没匹配到命名列，用前两列
        if q_col is None or a_col is None:
            if len(df.columns) >= 2:
                q_col = df.columns[0]
                a_col = df.columns[1]
                print(f"[RAG] 未识别列名，使用前两列: '{q_col}' / '{a_col}'")
            else:
                print(f"[RAG] xlsx 列数不足（需要至少两列）", file=sys.stderr)
                return []

        pairs = []
        for idx, row in df.iterrows():
            q = str(row[q_col]).strip() if pd.notna(row[q_col]) else ""
            a = str(row[a_col]).strip() if pd.notna(row[a_col]) else ""
            if q and a:
                pairs.append((q, a))

        return pairs

    # ── Embedding API ──────────────────────────────────────

    def _get_embedding(self, text: str) -> list[float]:
        """单条文本 → 向量。"""
        import dashscope
        dashscope.api_key = settings.ALIYUN_API_KEY

        response = dashscope.TextEmbedding.call(
            model=settings.EMBEDDING_MODEL,
            input=text,
        )

        if response.status_code != 200:
            raise RuntimeError(f"Embedding API 返回 {response.status_code}: {response.message}")

        return response.output["embeddings"][0]["embedding"]

    def _get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本 → 向量列表，自动分批。"""
        all_embeddings = []

        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i:i + self.BATCH_SIZE]
            batch_embeddings = self._get_embeddings_single_batch(batch)
            if not batch_embeddings:
                return []
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def _get_embeddings_single_batch(self, texts: list[str]) -> list[list[float]]:
        """调用 dashscope TextEmbedding API 处理一批文本。"""
        try:
            import dashscope
            dashscope.api_key = settings.ALIYUN_API_KEY

            response = dashscope.TextEmbedding.call(
                model=settings.EMBEDDING_MODEL,
                input=texts,
            )

            if response.status_code != 200:
                print(f"[RAG] Embedding API 错误 {response.status_code}: {response.message}", file=sys.stderr)
                return []

            sorted_embeds = sorted(
                response.output["embeddings"],
                key=lambda x: x["text_index"],
            )
            return [item["embedding"] for item in sorted_embeds]

        except ImportError:
            print("[RAG] 缺少 dashscope SDK", file=sys.stderr)
            return []
        except Exception as e:
            print(f"[RAG] Embedding API 异常: {e}", file=sys.stderr)
            return []
