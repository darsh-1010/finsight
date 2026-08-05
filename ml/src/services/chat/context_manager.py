"""Context Management for Chat Service."""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Tuple

from weaviate.classes.query import Filter

from config.settings import settings
from src.core.interfaces import IQueryService, IRAGService
from src.core.models import FinancialContext, QueryExpansionResult
from src.services.knowledge_graph.graph_service import GraphService
from src.services.rag.retrieval_grader import RetrievalGrader
from src.utils.logger import get_logger
from src.utils.perf_utils import timed

logger = get_logger(__name__)


class ContextManager:
    """Manages retrieval and assembly of context from various sources."""

    def __init__(
        self,
        query_service: IQueryService,
        rag_service: IRAGService,
        enable_rag: bool = True,
    ):
        self.query_service = query_service
        self.rag_service = rag_service
        self.enable_rag = enable_rag
        self._current_phase1_task = None
        self._retrieval_grader = RetrievalGrader()
        self._graph_service = GraphService()

    @timed("context.get_context", warn_threshold_s=3.0)
    async def get_context(
        self,
        message: str,
        enriched_query: str,
        **kwargs: Any,
    ) -> tuple[
        str | None,
        list[dict[str, Any]],
        bool,
        dict[str, Any] | None,
        list[float] | None,
        list[str],
    ]:
        """Orchestrate fetching and combining context.

        Args:
            message: Raw user message.
            enriched_query: Expanded query.
            **kwargs:
                session_summary: Previous turns summary.
                session_ticker: Resolved ticker.
                features: TierFeatures object.
                user_id: For scoping.
                session_id: For scoping.
        """
        request_id = str(uuid.uuid4())[:8]
        logger.info(
            "[CONTEXT][%s] Orchestrating context retrieval (two-phase RAG)...",
            request_id,
        )

        try:
            raw_query = enriched_query or message
            (
                raw_vector,
                *_,
            ) = await self.rag_service.vector_service.embedding_service.aembed_documents(
                [raw_query]
            )

            # ── PHASE 1 ──
            analysis_data = await self._orchestrate_phase1(
                raw_query,
                raw_vector,
                features=kwargs.get("features"),
                request_id=request_id,
                session_ticker=kwargs.get("session_ticker"),
                user_id=kwargs.get("user_id"),
                session_id=kwargs.get("session_id"),
            )

            # ── PHASE 2 ──
            context_results = await self._orchestrate_phase2(
                message,
                raw_query,
                analysis_data,
                features=kwargs.get("features"),
                request_id=request_id,
                user_id=kwargs.get("user_id"),
                session_id=kwargs.get("session_id"),
            )

            processed = self._process_retrieval_results(
                analysis_data=analysis_data,
                retrieval_results=context_results,
                session_summary=kwargs.get("session_summary", ""),
                request_id=request_id,
            )
            # Prioritize explicit file_ids from the request for "Exact Prompt Mapping"
            file_ids = kwargs.get("file_ids")
            if file_ids is not None:
                # Resolve specific IDs provided in the request
                resolved_files = await self._resolve_specific_file_ids(
                    kwargs.get("session_id"), file_ids, kwargs.get("redis_client")
                )
            elif kwargs.get("redis_client") and kwargs.get("session_id"):
                # Fallback to fetching all files for the session (automatic mode)
                resolved_files = await self._get_openai_file_ids(
                    kwargs["session_id"], kwargs["redis_client"]
                )
            else:
                resolved_files = []

            return (*processed, raw_vector, resolved_files)

        except (
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
            asyncio.TimeoutError,
        ) as e:
            logger.error(
                "[CONTEXT_ERROR] ReqId: %s | Phase: Orchestration | Error: %s",
                request_id,
                e,
            )
            # Return a sentinel so the guard can distinguish "analysis failed"
            # from a valid in-domain empty result. should_search is set False
            # to prevent web search guidance being injected on error paths.
            _failed = {"_analysis_failed": True, "expansion": {}, "contexts": []}
            return None, [], False, _failed, None, []

    async def _get_openai_file_ids(
        self, session_id: str, redis_client: Any
    ) -> list[dict]:
        """Fetch all OpenAI file metadata (id and type) stored for this session."""
        if not redis_client or not session_id:
            return []
        keys = await redis_client.keys(f"openai_file:{session_id}:*")
        file_metadata = []
        for key in keys:
            raw_data = await redis_client.get(key)
            if raw_data:
                meta = self._parse_file_metadata(raw_data)
                if meta:
                    file_metadata.append(meta)
        return file_metadata

    async def _resolve_specific_file_ids(
        self,
        session_id: str | None,
        file_ids: list[str],
        redis_client: Any,
    ) -> list[dict]:
        """Resolve a specific list of IDs to their full metadata from Redis or OpenAI defaults."""
        if not file_ids:
            return []

        resolved = []
        for f_id in file_ids:
            if not f_id:
                continue

            # Check if it's a Redis-backed attachment (attachment_id)
            if session_id and redis_client:
                raw_data = await redis_client.get(f"openai_file:{session_id}:{f_id}")
                if raw_data:
                    meta = self._parse_file_metadata(raw_data)
                    if meta:
                        resolved.append(meta)
                        continue

            # If not in Redis, assume it's a native OpenAI file_id
            resolved.append(
                {
                    "source": "openai",
                    "file_id": f_id,
                    "mime_type": "application/pdf",  # Generic default
                }
            )
        return resolved

    def _parse_file_metadata(self, raw_data: Any) -> dict | None:
        """Parse raw Redis data into a metadata dictionary."""
        data_str = raw_data.decode() if isinstance(raw_data, bytes) else raw_data
        try:
            meta = json.loads(data_str)
            if isinstance(meta, dict):
                # Ensure it has a file_id key at minimum for compatibility
                if "file_id" not in meta:
                    meta["file_id"] = None
                return meta
            # Fallback for plain string (legacy format)
            return {
                "file_id": data_str,
                "source": "openai",
                "mime_type": "application/pdf",
            }
        except (json.JSONDecodeError, ValueError):
            # Backward compatibility: plain string
            return {
                "file_id": data_str,
                "source": "openai",
                "mime_type": "application/pdf",
            }

    async def _orchestrate_phase1(
        self,
        raw_query: str,
        raw_vector: list[float],
        *,
        features: Any,
        request_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Start analysis and initial RAG in parallel."""
        # Financial analysis task
        if features and features.search_depth <= 0:
            analysis_task = asyncio.create_task(self.query_service.analyze(raw_query))
        else:
            analysis_task = asyncio.create_task(
                self.query_service.analyze_and_fetch(
                    raw_query, session_ticker=kwargs.get("session_ticker")
                )
            )

        # Initial RAG task
        doc_phase1_task = asyncio.create_task(
            self._get_document_context(
                raw_query,
                pre_computed_vector=raw_vector,
                features=features,
                user_id=kwargs.get("user_id"),
                session_id=kwargs.get("session_id"),
            )
        )

        # Stash the task so phase-2 can await it
        self._current_phase1_task = doc_phase1_task

        try:
            analysis_data = await analysis_task
            # For Tier 1 (search_depth <= 0), wrap the raw expansion to match analyze_and_fetch format
            if features and features.search_depth <= 0:
                return {"expansion": analysis_data, "contexts": []}
            return analysis_data
        except (
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
            asyncio.TimeoutError,
        ) as exc:
            logger.error("[CONTEXT][%s] Financial analysis failed: %s", request_id, exc)
            # Return a sentinel distinguishable from a valid empty result.
            # The guard in chat_service.py reads _analysis_failed and handles it safely.
            return {"_analysis_failed": True, "expansion": {}, "contexts": []}

    async def _orchestrate_phase2(
        self,
        message: str,
        raw_query: str,
        analysis_data: dict[str, Any],
        *,
        features: Any,
        request_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute supplemental RAG based on analysis results."""
        built_rag_query = self._build_rag_search_query(message, analysis_data)
        should_fetch_articles = self._should_fetch_articles(analysis_data)
        if features and not features.has_web_access:
            should_fetch_articles = False

        query_was_expanded = (
            built_rag_query != raw_query and len(built_rag_query) > len(raw_query) + 20
        )

        expanded_vector = None
        if query_was_expanded or should_fetch_articles:
            queries = [built_rag_query]
            batch_vecs = await self.rag_service.vector_service.embedding_service.aembed_documents(
                queries
            )
            expanded_vector = batch_vecs[0] if batch_vecs else None

        phase2_tasks = [self._current_phase1_task]
        if query_was_expanded:
            phase2_tasks.append(
                asyncio.create_task(
                    self._get_document_context(
                        built_rag_query,
                        pre_computed_vector=expanded_vector,
                        features=features,
                        user_id=kwargs.get("user_id"),
                        session_id=kwargs.get("session_id"),
                    )
                )
            )
        if should_fetch_articles:
            phase2_tasks.append(
                asyncio.create_task(
                    self._get_article_context(
                        built_rag_query,
                        pre_computed_vector=expanded_vector,
                        features=features,
                    )
                )
            )

        await asyncio.gather(*phase2_tasks, return_exceptions=True)

        return await self._run_phase2_retrieval(
            message=message,
            raw_query=raw_query,
            analysis_data=analysis_data,
            doc_phase1_task=self._current_phase1_task,
            features=features,
            user_id=kwargs.get("user_id"),
            session_id=kwargs.get("session_id"),
            request_id=request_id,
        )

    async def _run_phase2_retrieval(
        self,
        message: str,
        raw_query: str,
        analysis_data: dict[str, Any],
        doc_phase1_task: asyncio.Task,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run supplemental retrieval tasks based on analysis."""
        request_id = kwargs.get("request_id", "unknown")
        built_rag_query = self._build_rag_search_query(message, analysis_data)
        should_fetch_articles = self._should_fetch_articles(analysis_data)

        features = kwargs.get("features")
        if features and not features.has_web_access:
            should_fetch_articles = False

        query_was_expanded = (
            built_rag_query != raw_query and len(built_rag_query) > len(raw_query) + 20
        )

        expanded_vector: list[float] | None = None
        if query_was_expanded or should_fetch_articles:
            expanded_vector = await self._get_expanded_vector(built_rag_query)

        phase2_tasks: list = [doc_phase1_task]
        if query_was_expanded:
            logger.info(
                "[CONTEXT_PHASE2] ReqId: %s | Action: SupplementalDocFetch", request_id
            )
            phase2_tasks.append(
                asyncio.create_task(
                    self._get_document_context(
                        built_rag_query,
                        pre_computed_vector=expanded_vector,
                        features=features,
                        user_id=kwargs.get("user_id"),
                        session_id=kwargs.get("session_id"),
                    )
                )
            )

        if should_fetch_articles:
            phase2_tasks.append(
                asyncio.create_task(
                    self._get_article_context(
                        built_rag_query,
                        pre_computed_vector=expanded_vector,
                        features=features,
                    )
                )
            )

        # ── Knowledge Graph query (runs in parallel with RAG tasks) ────
        # Extract primary ticker from analysis for graph context resolution.
        session_ticker = kwargs.get("session_ticker")
        expansion = analysis_data.get("expansion", {})
        graph_ticker_hint = session_ticker
        if not graph_ticker_hint:
            expanded_queries = expansion.get("expanded_queries", [])
            if expanded_queries and isinstance(expanded_queries[0], dict):
                graph_ticker_hint = expanded_queries[0].get("ticker")

        graph_task = asyncio.create_task(self._get_graph_context(message, ticker_hint=graph_ticker_hint))
        phase2_tasks.append(graph_task)

        results = await asyncio.gather(*phase2_tasks, return_exceptions=True)

        # Pop graph result (always last).
        graph_result = results.pop()
        graph_ctx, graph_cits = "", []
        if isinstance(graph_result, tuple) and len(graph_result) == 2:
            graph_ctx = graph_result[0] or ""
            graph_cits = graph_result[1] or []
        elif isinstance(graph_result, Exception):
            logger.warning("[CONTEXT_PHASE2] Graph query failed: %s", graph_result)

        unpacked = self._unpack_phase2_results(
            results, query_was_expanded, should_fetch_articles, request_id
        )
        unpacked["graph_ctx"] = graph_ctx
        unpacked["graph_cits"] = graph_cits
        return unpacked

    @timed("graph.query", warn_threshold_s=3.0)
    async def _get_graph_context(
        self,
        message: str,
        *,
        ticker_hint: str | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Query the knowledge graph for relational context.

        Degrades gracefully: returns (None, []) if Neo4j is unavailable,
        the query doesn't need graph traversal, or any error occurs.
        """
        try:
            return await self._graph_service.query(
                message, ticker_hint=ticker_hint
            )
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            logger.warning("[GRAPH] Graph query failed (non-fatal): %s", exc)
            return None, []

    async def _get_expanded_vector(self, query: str) -> list[float] | None:
        """Utility to get vector for expanded query."""
        batch_vecs = (
            await self.rag_service.vector_service.embedding_service.aembed_documents(
                [query]
            )
        )
        return batch_vecs[0] if batch_vecs else None

    def _unpack_phase2_results(
        self,
        results: list[Any],
        was_expanded: bool,
        fetch_articles: bool,
        request_id: str,
    ) -> dict[str, Any]:
        """Unpack raw gather results into a clean dictionary."""
        doc_res_p1 = results[0]
        idx = 1
        doc_res = doc_res_p1

        if was_expanded:
            doc_res_p2 = results[idx]
            idx += 1
            doc_res = self._merge_doc_results(doc_res_p1, doc_res_p2, request_id)

        article_res = results[idx] if fetch_articles else (None, [])
        return {"doc_res": doc_res, "article_res": article_res}

    def _extract_doc_article_contexts(
        self,
        retrieval_results: dict[str, Any],
        request_id: str,
    ) -> tuple[str, list[dict[str, Any]], str, list[dict[str, Any]]]:
        """Unpack doc and article sub-results from the retrieval dict."""
        doc_ctx, doc_cits = self._handle_sub_result(
            retrieval_results.get("doc_res"), "Document", request_id
        )
        art_ctx, art_cits = self._handle_sub_result(
            retrieval_results.get("article_res"), "Article", request_id
        )
        return doc_ctx, doc_cits, art_ctx, art_cits

    def _process_retrieval_results(
        self,
        analysis_data: dict[str, Any],
        retrieval_results: dict[str, Any],
        session_summary: str,
        request_id: str,
    ) -> tuple[str | None, list[dict[str, Any]], bool, dict[str, Any] | None]:
        """Process results from semantic searches and financial pipelines."""
        doc_ctx, doc_cits, art_ctx, art_cits = self._extract_doc_article_contexts(
            retrieval_results, request_id
        )

        fin_ctx = ""
        fin_cits: list[dict[str, Any]] = []
        if isinstance(analysis_data, dict) and analysis_data.get("contexts"):
            fin_ctx, fin_cits = self._process_financial_context(
                analysis_data, session_summary
            )

        # Knowledge graph context (if available from phase-2).
        graph_ctx = retrieval_results.get("graph_ctx", "")
        graph_cits = retrieval_results.get("graph_cits", [])

        combined_ctx, combined_cits = self._merge_contexts(
            fin_ctx,
            fin_cits,
            doc_ctx=doc_ctx,
            doc_cits=doc_cits,
            art_ctx=art_ctx,
            art_cits=art_cits,
            graph_ctx=graph_ctx,
            graph_cits=graph_cits,
        )

        use_web_search = not (fin_ctx and fin_ctx.strip())
        logger.info(
            "[CONTEXT_COMPLETE] ReqId: %s | WebSearch: %s", request_id, use_web_search
        )

        return combined_ctx, combined_cits, use_web_search, analysis_data

    def _handle_sub_result(
        self, res: Any, lab: str, rid: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Safely unpack retrieval sub-results."""
        if isinstance(res, Exception):
            logger.error(
                "[RETRIEVAL_ERROR] ReqId: %s | Type: %s | Error: %s", rid, lab, res
            )
            return "", []
        if res:
            return res[0] or "", res[1] or []
        return "", []

    @timed("rag.document_retrieval", warn_threshold_s=1.5)
    async def _get_document_context(
        self,
        message: str,
        **kwargs: Any,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Get document context from RAG service."""
        if not self.enable_rag:
            return None, []

        features = kwargs.get("features")
        # Use specialized document depth if available, else fallback to generic search_depth
        if features and features.document_search_depth is not None:
            limit = features.document_search_depth
        else:
            limit = features.search_depth if features else settings.rerank_top_k

        if limit <= 0:
            return None, []

        try:
            logger.info("[RAG] Retrieving document context (depth=%d)...", limit)

            # Build metadata filters for user/session scoping
            filters = []
            if kwargs.get("user_id"):
                filters.append(Filter.by_property("user_id").equal(kwargs["user_id"]))
            if kwargs.get("session_id"):
                filters.append(
                    Filter.by_property("session_id").equal(kwargs["session_id"])
                )

            results = await self.rag_service.retrieve_context(
                query=message,
                limit=limit,
                filters=filters,
                pre_computed_vector=kwargs.get("pre_computed_vector"),
            )

            if not results:
                logger.info("[RAG] No relevant documents found")
                return None, []

            logger.info("[RAG] Found %d raw documents, running relevance grading...", len(results))

            # ── Retrieval Grading ────────────────────────────────────
            # LLM-based relevance filter: drops chunks that are topically
            # adjacent but don't actually help answer the query.
            try:
                results = await self._retrieval_grader.grade_and_filter(message, results)
                logger.info("[RAG] %d documents survived grading", len(results))
            except (ValueError, TypeError, RuntimeError) as grade_exc:
                # Fail-open: if grader breaks, use unfiltered results.
                logger.warning("[RAG] Grading failed, using unfiltered: %s", grade_exc)

            if not results:
                return None, []

            context_parts, citations = [], []
            for position, doc in enumerate(results, 1):
                chunk_text, chunk_cit = self._format_doc_chunk(position, doc)
                context_parts.append(chunk_text)
                citations.append(chunk_cit)

            return "\n\n".join(context_parts), citations

        except (
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
            asyncio.TimeoutError,
        ) as exc:
            logger.warning(
                "[RAG] Failed to get document context: %s", exc, exc_info=True
            )
            return None, []

    def _format_doc_chunk(
        self, position: int, doc: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Format a single document chunk into a display string and its citation."""
        meta = doc.get("metadata", {})
        title = meta.get("title", "Untitled Document")
        content = doc.get("content", "")
        if len(content) > settings.max_document_chunk_chars:
            content = content[: settings.max_document_chunk_chars] + "..."
        chunk_text = f"Document {position}: {title}\n{content}"
        citation = {
            "source": "document",
            "title": title,
            "url": doc.get("source_url"),
            "score": doc.get("score", 0.0),
            "data_type": "document",
        }
        return chunk_text, citation

    def _process_financial_context(
        self, analysis_result: dict[str, Any], session_summary: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Parse QueryService results into strings and citations."""
        contexts = [FinancialContext(**ctx) for ctx in analysis_result["contexts"]]
        expansion = QueryExpansionResult(**analysis_result["expansion"])

        context_str = self.query_service.build_llm_context(expansion, contexts)

        if session_summary:
            context_str = f"{session_summary}\n\n{context_str}"

        citations = [
            {"source": "yfinance", "ticker": c.ticker, "data_type": "financial_data"}
            for c in contexts
        ]

        return context_str, citations

    def _should_fetch_articles(self, analysis_result: dict[str, Any]) -> bool:
        """Check if LLM flagged that we need research/news article context."""
        if not analysis_result or not isinstance(analysis_result, dict):
            return True

        expansion = analysis_result.get("expansion", {})
        # Safety default to True if missing
        return expansion.get("requires_article_context", True)

    def _build_rag_search_query(
        self, message: str, analysis_data: dict[str, Any]
    ) -> str:
        """Combine raw message with LLM expanded queries for richer semantic search."""
        if not analysis_data or not isinstance(analysis_data, dict):
            return message

        expansion_dict = analysis_data.get("expansion")
        if not expansion_dict:
            return message

        try:
            expansion = QueryExpansionResult(**expansion_dict)
            parts = [message]

            if expansion.core_question and expansion.core_question != message:
                parts.append(expansion.core_question)

            # Add specific sub-queries to broaden the semantic footprint
            for eq in expansion.expanded_queries:
                if eq.query:
                    parts.append(eq.query)

            combined_query = " ".join(parts)
            logger.info(
                "[RAG] Built enriched search query (%d chars)", len(combined_query)
            )
            return combined_query
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning("[RAG] Failed to build enriched search query: %s", e)
            return message

    def _merge_doc_results(
        self,
        phase1: Any,
        phase2: Any,
        request_id: str,
    ) -> tuple[str | None, list[dict]]:
        """Merge two doc retrieval results, deduplicated by content hash.

        Phase-1 used the raw query; phase-2 used the LLM-expanded query.
        We union them so no chunk appears twice, keeping highest-score copy.
        """
        ctx1, cits1 = self._unpack_doc_result(phase1)
        ctx2, cits2 = self._unpack_doc_result(phase2)

        if not ctx2:
            return ctx1 or None, cits1

        chunks1 = [c.strip() for c in ctx1.split("\n\n") if c.strip()] if ctx1 else []
        chunks2 = [c.strip() for c in ctx2.split("\n\n") if c.strip()] if ctx2 else []
        merged_chunks = self._deduplicate_chunks(chunks1, chunks2)
        merged_ctx = "\n\n".join(merged_chunks) if merged_chunks else None
        merged_cits = self._deduplicate_citations(list(cits1), cits2)

        logger.info(
            "[RAG][%s] Doc merge: phase1=%d chunks, phase2=%d chunks → merged=%d chunks",
            request_id,
            len(chunks1),
            len(chunks2),
            len(merged_chunks),
        )
        return merged_ctx, merged_cits

    @staticmethod
    def _unpack_doc_result(res: Any) -> tuple[str, list[dict]]:
        """Safely unpack a doc retrieval result tuple, returning empty defaults on failure."""
        if isinstance(res, Exception) or res is None:
            return "", []
        ctx, cits = res
        return ctx or "", cits or []

    @staticmethod
    def _deduplicate_chunks(chunks1: list[str], chunks2: list[str]) -> list[str]:
        """Union two chunk lists, deduplicating by content fingerprint."""
        seen: set[int] = set()
        merged: list[str] = []
        for chunk in chunks1 + chunks2:
            # Use the first 120 chars as a fast fingerprint; full hash would be slower
            fingerprint = hash(chunk[:120])
            if fingerprint not in seen:
                seen.add(fingerprint)
                merged.append(chunk)
        return merged

    @staticmethod
    def _deduplicate_citations(base: list[dict], extra: list[dict]) -> list[dict]:
        """Append citations from extra into base, skipping duplicates by URL or title."""
        seen_keys: set[str] = {cit.get("url") or cit.get("title") or "" for cit in base}
        for cit in extra:
            key = cit.get("url") or cit.get("title") or ""
            if not key or key not in seen_keys:
                base.append(cit)
                seen_keys.add(key)
        return base

    @timed("rag.article_retrieval", warn_threshold_s=1.5)
    async def _get_article_context(
        self,
        message: str,
        **kwargs: Any,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Get scraped article context from RAG service."""
        if not self.enable_rag:
            return None, []

        features = kwargs.get("features")
        # Use specialized article depth if available, else fallback to generic search_depth
        if features and features.article_search_depth is not None:
            limit = features.article_search_depth
        else:
            limit = features.search_depth if features else settings.rerank_top_k

        if limit <= 0:
            return None, []

        try:
            logger.info("[RAG] Retrieving scraped article context (depth=%d)...", limit)
            if not hasattr(self.rag_service, "retrieve_article_context"):
                logger.warning(
                    "[RAG] retrieve_article_context not available on RAG service interface"
                )
                return None, []

            results = await self.rag_service.retrieve_article_context(
                query=message,
                limit=limit,
                pre_computed_vector=kwargs.get("pre_computed_vector"),
            )

            if not results:
                logger.info("[RAG] No relevant scraped articles found")
                return None, []

            logger.info("[RAG] Found %d relevant scraped articles", len(results))

            parts = []
            cits = []
            for idx, doc in enumerate(results, 1):
                content = doc.get("content", "")
                meta = doc.get("metadata", {})
                title = meta.get("title", "Untitled Article")

                if len(content) > settings.max_document_chunk_chars:
                    content = content[: settings.max_document_chunk_chars] + "..."

                parts.append(
                    f"Article {idx} (from {meta.get('source', 'unknown')}): {title}\n{content}"
                )
                cits.append(
                    {
                        "source": "article",
                        "title": title,
                        "url": doc.get("source_url"),
                        "score": doc.get("score", 0.0),
                        "data_type": "article",
                    }
                )

            return "\n\n".join(parts), cits

        except (
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
            asyncio.TimeoutError,
        ) as e:
            logger.warning(f"[RAG] Failed to get article context: {e}", exc_info=True)
            return None, []

    def _merge_contexts(
        self,
        fin_context: str,
        fin_citations: list[dict[str, Any]],
        **kwargs: Any,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Merge contexts and deduplicate citations by URL."""
        doc_context = kwargs.get("doc_ctx")
        doc_citations = kwargs.get("doc_cits", [])
        article_context = kwargs.get("art_ctx")
        article_citations = kwargs.get("art_cits", [])
        graph_context = kwargs.get("graph_ctx")
        graph_citations = kwargs.get("graph_cits", [])

        parts = []
        if fin_context:
            parts.append(fin_context)
        if graph_context:
            parts.append(
                f"\n[Knowledge Graph — Relational Data]\n{graph_context}"
            )
        if doc_context:
            parts.append(
                f"\n[Document Knowledge]\n<untrusted_data>\n{doc_context}\n</untrusted_data>"
            )
        if article_context:
            parts.append(
                f"\n[Research Articles]\n<untrusted_data>\n{article_context}\n</untrusted_data>"
            )

        combined_str = "\n\n".join(parts)

        # Deduplicate citations by URL across all sources
        combined_cits = fin_citations.copy()

        seen_urls = set()
        for cit in combined_cits:
            if url := cit.get("url"):
                seen_urls.add(url)

        for cit_list in [graph_citations, doc_citations, article_citations]:
            for cit in cit_list:
                url = cit.get("url")
                if not url or url not in seen_urls:
                    combined_cits.append(cit)
                    if url:
                        seen_urls.add(url)

        return combined_str, combined_cits
