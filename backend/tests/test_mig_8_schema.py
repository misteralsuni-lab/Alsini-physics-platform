"""
Schema and SQL contract verification tests for Migration 8:
`migrations/mig_8_chapter1_learning_blocks_and_unified_rag.sql`

Validates:
- Non-destructive & strictly idempotent DDL/DML guards
- `public.resources` extensions & backfill from `specification_points`
- `public.lessons`, `public.learning_blocks`, and `public.student_block_progress`
  schema, constraints, `updated_at` triggers, and flat `xp_awarded` (no `xp_events`)
- `public.resource_chunks` extensions & non-destructive Chapter 1 backfill
  (`nvidia/nemotron-3.5-embed-1b`, without mutating existing embeddings)
- Redundant B-tree index drops (`idx_resource_chunks_resource_id`, `idx_spec_points_code`)
  and non-duplicative new indexes
- `public.match_chapter_chunks` RPC signature, model-tagged filter, citation return columns,
  and preservation of legacy 3-arg `public.match_resource_chunks`
- Row Level Security (RLS) enablement and policies on all new tables
"""

from pathlib import Path
import re

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_8_PATH = REPO_ROOT / "migrations" / "mig_8_chapter1_learning_blocks_and_unified_rag.sql"
MIG_0_PATH = REPO_ROOT / "migrations" / "mig_0_verify_and_harden_rls.sql"
MIG_7_PATH = REPO_ROOT / "migrations" / "mig_7_match_function.sql"

CH1_CHAPTER_ID = "b95f8fac-355e-4037-bc1f-2d3b2bf77140"
CH1_LEGACY_RESOURCE_ID = "5729d034-a6c7-4f35-b81c-fcac447289c7"
ACTIVE_EMBED_MODEL = "nvidia/nemotron-3.5-embed-1b"


def _strip_sql_comments(sql: str) -> str:
    """Remove `--` line comments and `/* ... */` block comments for structural parsing."""
    without_block = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    lines = []
    for line in without_block.splitlines():
        # Strip -- comments while preserving content inside single-quoted literals.
        in_quote = False
        cleaned = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "'":
                in_quote = not in_quote
                cleaned.append(ch)
                i += 1
            elif not in_quote and line[i : i + 2] == "--":
                break
            else:
                cleaned.append(ch)
                i += 1
        lines.append("".join(cleaned))
    return "\n".join(lines)


def _extract_table_block(sql_clean: str, table_name: str) -> str:
    """Extract the CREATE TABLE IF NOT EXISTS public.<table> (...) body."""
    pattern = re.compile(
        rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+public\.{re.escape(table_name)}\s*\(",
        re.IGNORECASE,
    )
    match = pattern.search(sql_clean)
    assert match is not None, f"Missing CREATE TABLE IF NOT EXISTS public.{table_name}"
    start = match.end() - 1
    depth = 0
    for idx in range(start, len(sql_clean)):
        if sql_clean[idx] == "(":
            depth += 1
        elif sql_clean[idx] == ")":
            depth -= 1
            if depth == 0:
                return sql_clean[start : idx + 1]
    pytest.fail(f"Unclosed parentheses in CREATE TABLE public.{table_name}")


def _extract_function_block(sql_clean: str, func_name: str) -> str:
    """Extract a CREATE OR REPLACE FUNCTION public.<func_name> ... $$; block."""
    pattern = re.compile(
        rf"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.{re.escape(func_name)}\s*\(.*?\$\$.*?\$\$;",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(sql_clean)
    assert match is not None, f"Missing CREATE OR REPLACE FUNCTION public.{func_name}"
    return match.group(0)


@pytest.fixture(scope="module")
def mig8_raw() -> str:
    assert MIG_8_PATH.exists(), f"Migration file not found: {MIG_8_PATH}"
    return MIG_8_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def mig8_clean(mig8_raw: str) -> str:
    return _strip_sql_comments(mig8_raw)


# ---------------------------------------------------------------------------
# 1. Structure, Transaction Safety, and Non-Destructive Guarantees
# ---------------------------------------------------------------------------

class TestNonDestructiveAndIdempotentStructure:
    def test_wrapped_in_transaction_and_balanced_delimiters(self, mig8_clean: str):
        assert re.search(r"^\s*BEGIN\s*;", mig8_clean, re.IGNORECASE | re.MULTILINE)
        assert re.search(r"^\s*COMMIT\s*;", mig8_clean, re.IGNORECASE | re.MULTILINE)
        assert mig8_clean.count("$$") % 2 == 0, "Unbalanced dollar-quote ($$) delimiters"
        assert mig8_clean.count("(") == mig8_clean.count(")"), "Unbalanced parentheses"

    def test_strictly_non_destructive_no_table_data_or_embedding_loss(self, mig8_clean: str):
        forbidden = [
            r"\bDROP\s+TABLE\b",
            r"\bTRUNCATE\b",
            r"\bDELETE\s+FROM\b",
            r"\bDROP\s+COLUMN\b",
            r"\bDROP\s+FUNCTION\b",
            r"\bSET\s+embedding\s*=",
        ]
        for pat in forbidden:
            assert not re.search(pat, mig8_clean, re.IGNORECASE), (
                f"Destructive or embedding-mutating SQL matched: {pat}"
            )

    def test_no_xp_events_ledger_table(self, mig8_clean: str):
        assert not re.search(r"\bxp_events\b", mig8_clean, re.IGNORECASE), (
            "ADR-0003 forbids a separate xp_events ledger table"
        )

    def test_all_create_table_statements_are_idempotent(self, mig8_clean: str):
        all_creates = re.findall(r"CREATE\s+TABLE\b[^(\n]*", mig8_clean, re.IGNORECASE)
        assert len(all_creates) == 3, f"Expected 3 CREATE TABLE statements, got {all_creates}"
        for stmt in all_creates:
            assert re.search(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\b", stmt, re.IGNORECASE), (
                f"Non-idempotent CREATE TABLE: {stmt}"
            )

    def test_all_add_column_statements_are_idempotent(self, mig8_clean: str):
        add_cols = re.findall(r"ADD\s+COLUMN\b[^;]*", mig8_clean, re.IGNORECASE)
        assert len(add_cols) >= 8
        for stmt in add_cols:
            assert re.search(r"ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\b", stmt, re.IGNORECASE), (
                f"Non-idempotent ADD COLUMN: {stmt}"
            )

    def test_all_index_operations_are_idempotent(self, mig8_clean: str):
        create_idxs = re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX\b[^;]*", mig8_clean, re.IGNORECASE)
        assert len(create_idxs) >= 6
        for stmt in create_idxs:
            assert re.search(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\b", stmt, re.IGNORECASE), (
                f"Non-idempotent CREATE INDEX: {stmt}"
            )
        drop_idxs = re.findall(r"DROP\s+INDEX\b[^;]*", mig8_clean, re.IGNORECASE)
        assert len(drop_idxs) == 2
        for stmt in drop_idxs:
            assert re.search(r"DROP\s+INDEX\s+IF\s+EXISTS\b", stmt, re.IGNORECASE), (
                f"Non-idempotent DROP INDEX: {stmt}"
            )

    def test_policies_constraints_and_triggers_guarded_in_do_blocks(self, mig8_clean: str):
        # Remove all DO $$ ... END $$; blocks; none of CREATE POLICY / CREATE TRIGGER /
        # ALTER TABLE ... ADD CONSTRAINT should appear unguarded outside them.
        outside_do = re.sub(r"DO\s*\$\$.*?END\s*\$\$;", "", mig8_clean, flags=re.IGNORECASE | re.DOTALL)
        assert not re.search(r"\bCREATE\s+POLICY\b", outside_do, re.IGNORECASE)
        assert not re.search(r"\bCREATE\s+TRIGGER\b", outside_do, re.IGNORECASE)
        assert not re.search(r"ALTER\s+TABLE\b[^;]*\bADD\s+CONSTRAINT\b", outside_do, re.IGNORECASE)


# ---------------------------------------------------------------------------
# 2. `public.resources` Extensions and Backfill
# ---------------------------------------------------------------------------

class TestResourcesExtension:
    def test_resources_columns_added(self, mig8_clean: str):
        assert re.search(
            r"ALTER\s+TABLE\s+public\.resources\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+"
            r"chapter_id\s+UUID\s+REFERENCES\s+public\.chapters\(id\)",
            mig8_clean,
            re.IGNORECASE,
        )
        assert re.search(
            r"ALTER\s+TABLE\s+public\.resources\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+"
            r"resource_type\s+VARCHAR\(\d+\)\s+NOT\s+NULL\s+DEFAULT\s+'worksheet'",
            mig8_clean,
            re.IGNORECASE,
        )
        assert re.search(
            r"ALTER\s+TABLE\s+public\.resources\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+"
            r"spec_refs\s+TEXT\[\]\s+NOT\s+NULL\s+DEFAULT\s+'\{\}'::text\[\]",
            mig8_clean,
            re.IGNORECASE,
        )

    def test_resources_resource_type_constraint_exact_values(self, mig8_clean: str):
        match = re.search(
            r"ADD\s+CONSTRAINT\s+chk_resources_resource_type\s+CHECK\s*\(\s*resource_type\s+IN\s*\(([^)]+)\)\s*\)",
            mig8_clean,
            re.IGNORECASE,
        )
        assert match is not None, "Missing chk_resources_resource_type CHECK constraint"
        allowed = set(re.findall(r"'([^']+)'", match.group(1)))
        assert allowed == {"worksheet", "lesson", "practical", "examiner_note"}

    def test_resources_chapter_id_backfilled_from_specification_points(self, mig8_clean: str):
        assert re.search(
            r"UPDATE\s+public\.resources\s+r\s+"
            r"SET\s+chapter_id\s*=\s*sp\.chapter_id\s+"
            r"FROM\s+public\.specification_points\s+sp\s+"
            r"WHERE\s+r\.specification_point_id\s*=\s*sp\.id\s+"
            r"AND\s+r\.chapter_id\s+IS\s+NULL",
            mig8_clean,
            re.IGNORECASE,
        )


# ---------------------------------------------------------------------------
# 3. `public.lessons`, `public.learning_blocks`, and `public.student_block_progress`
# ---------------------------------------------------------------------------

class TestLearningTablesSchema:
    def test_lessons_table_columns_and_constraints(self, mig8_clean: str):
        body = _extract_table_block(mig8_clean, "lessons")
        for required in [
            r"\bchapter_id\s+UUID\s+NOT\s+NULL\s+REFERENCES\s+public\.chapters\(id\)",
            r"\bresource_id\s+UUID\s+REFERENCES\s+public\.resources\(id\)",
            r"\bslug\s+VARCHAR\(\d+\)\s+NOT\s+NULL",
            r"\btitle\s+VARCHAR\(\d+\)\s+NOT\s+NULL",
            r"\bspec_refs\s+TEXT\[\]",
            r"\bupdated_at\s+TIMESTAMP\s+WITH\s+TIME\s+ZONE",
            r"UNIQUE\s*\(\s*chapter_id\s*,\s*slug\s*\)",
        ]:
            assert re.search(required, body, re.IGNORECASE), f"lessons missing pattern: {required}"

    def test_learning_blocks_table_columns_and_constraints(self, mig8_clean: str):
        body = _extract_table_block(mig8_clean, "learning_blocks")
        for required in [
            r"\blesson_id\s+UUID\s+NOT\s+NULL\s+REFERENCES\s+public\.lessons\(id\)",
            r"\bchapter_id\s+UUID\s+NOT\s+NULL\s+REFERENCES\s+public\.chapters\(id\)",
            r"\bblock_index\s+INTEGER\s+NOT\s+NULL",
            r"\bslug\s+VARCHAR\(\d+\)\s+NOT\s+NULL",
            r"\btitle\s+VARCHAR\(\d+\)\s+NOT\s+NULL",
            r"\bspec_refs\s+TEXT\[\]",
            r"\bcontent_markdown\s+TEXT",
            r"\bguided_practice\s+JSONB",
            r"\bself_check\s+JSONB",
            r"\bexaminer_alerts\s+JSONB",
            r"\banalogies\s+JSONB",
            r"\breflection_prompt\s+TEXT",
            r"\bwidgets\s+JSONB",
            r"\bxp_value\s+INTEGER",
            r"\bupdated_at\s+TIMESTAMP\s+WITH\s+TIME\s+ZONE",
            r"UNIQUE\s*\(\s*lesson_id\s*,\s*block_index\s*\)",
            r"UNIQUE\s*\(\s*lesson_id\s*,\s*slug\s*\)",
        ]:
            assert re.search(required, body, re.IGNORECASE), f"learning_blocks missing pattern: {required}"

    def test_student_block_progress_columns_and_flat_xp(self, mig8_clean: str):
        body = _extract_table_block(mig8_clean, "student_block_progress")
        for required in [
            r"\bstudent_id\s+UUID\s+NOT\s+NULL\s+REFERENCES\s+auth\.users\(id\)\s+ON\s+DELETE\s+CASCADE",
            r"\bchapter_id\s+UUID\s+NOT\s+NULL\s+REFERENCES\s+public\.chapters\(id\)",
            r"\blesson_id\s+UUID\s+NOT\s+NULL\s+REFERENCES\s+public\.lessons\(id\)",
            r"\bblock_id\s+UUID\s+NOT\s+NULL\s+REFERENCES\s+public\.learning_blocks\(id\)",
            r"\bstatus\s+VARCHAR\(\d+\)\s+NOT\s+NULL\s+DEFAULT\s+'not_started'",
            r"\bis_completed\s+BOOLEAN\s+NOT\s+NULL\s+DEFAULT\s+false",
            r"\bcompleted_at\s+TIMESTAMP\s+WITH\s+TIME\s+ZONE",
            r"\bxp_awarded\s+INTEGER\s+NOT\s+NULL\s+DEFAULT\s+0\s+CHECK\s*\(\s*xp_awarded\s*>=\s*0\s*\)",
            r"\bself_check_score\s+NUMERIC",
            r"\bself_check_attempts\s+INTEGER",
            r"\bself_check_results\s+JSONB",
            r"\bremediation_triggered\s+BOOLEAN",
            r"\breflection_text\s+TEXT",
            r"\bupdated_at\s+TIMESTAMP\s+WITH\s+TIME\s+ZONE",
            r"UNIQUE\s*\(\s*student_id\s*,\s*block_id\s*\)",
        ]:
            assert re.search(required, body, re.IGNORECASE), (
                f"student_block_progress missing pattern: {required}"
            )

    def test_updated_at_triggers_installed_for_all_three_tables(self, mig8_clean: str):
        assert re.search(
            r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.set_updated_at\s*\(\s*\)\s+RETURNS\s+TRIGGER",
            mig8_clean,
            re.IGNORECASE,
        )
        for table in ("lessons", "learning_blocks", "student_block_progress"):
            assert re.search(
                rf"CREATE\s+TRIGGER\s+trg_{table}_set_updated_at\s+BEFORE\s+UPDATE\s+ON\s+public\.{table}",
                mig8_clean,
                re.IGNORECASE,
            ), f"Missing updated_at trigger for public.{table}"


# ---------------------------------------------------------------------------
# 4. `public.resource_chunks` Extensions & Chapter 1 Backfill
# ---------------------------------------------------------------------------

class TestResourceChunksExtensionAndBackfill:
    def test_resource_chunks_columns_added(self, mig8_clean: str):
        expected_cols = [
            r"chapter_id\s+UUID\s+REFERENCES\s+public\.chapters\(id\)",
            r"source_type\s+VARCHAR\(40\)\s+NOT\s+NULL\s+DEFAULT\s+'worksheet'",
            r"block_id\s+UUID\s+REFERENCES\s+public\.learning_blocks\(id\)\s+ON\s+DELETE\s+SET\s+NULL",
            r"spec_refs\s+TEXT\[\]\s+NOT\s+NULL\s+DEFAULT\s+'\{\}'::text\[\]",
            r"embedding_model\s+VARCHAR\(120\)",
        ]
        for col_pat in expected_cols:
            assert re.search(
                rf"ALTER\s+TABLE\s+public\.resource_chunks\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+{col_pat}",
                mig8_clean,
                re.IGNORECASE,
            ), f"resource_chunks missing column pattern: {col_pat}"

    def test_resource_chunks_chapter_and_ch1_embedding_model_backfill(self, mig8_clean: str):
        # Chapter backfill via resources / specification_points
        assert re.search(
            r"UPDATE\s+public\.resource_chunks\s+rc\s+"
            r"SET\s+chapter_id\s*=\s*COALESCE\(r\.chapter_id\s*,\s*sp\.chapter_id\)\s+"
            r"FROM\s+public\.resources\s+r",
            mig8_clean,
            re.IGNORECASE,
        )
        # Non-destructive Chapter 1 embedding_model backfill (21 existing rows)
        ch1_backfill = re.search(
            rf"UPDATE\s+public\.resource_chunks\s+"
            rf"SET\s+embedding_model\s*=\s*'{re.escape(ACTIVE_EMBED_MODEL)}'\s+"
            rf"WHERE\s+embedding_model\s+IS\s+NULL\s+AND\s*\([^;]+\);",
            mig8_clean,
            re.IGNORECASE | re.DOTALL,
        )
        assert ch1_backfill is not None, "Missing non-destructive Chapter 1 embedding_model backfill"
        clause = ch1_backfill.group(0)
        assert CH1_CHAPTER_ID in clause, "Chapter 1 UUID missing from embedding_model backfill"
        assert CH1_LEGACY_RESOURCE_ID in clause, "Legacy Ch1 resource UUID missing from embedding_model backfill"


# ---------------------------------------------------------------------------
# 5. Redundant Index Drops & Targeted New Indexes
# ---------------------------------------------------------------------------

class TestIndexes:
    def test_redundant_btree_indexes_dropped(self, mig8_clean: str):
        assert re.search(
            r"DROP\s+INDEX\s+IF\s+EXISTS\s+public\.idx_resource_chunks_resource_id\s*;",
            mig8_clean,
            re.IGNORECASE,
        )
        assert re.search(
            r"DROP\s+INDEX\s+IF\s+EXISTS\s+public\.idx_spec_points_code\s*;",
            mig8_clean,
            re.IGNORECASE,
        )

    def test_match_chapter_chunks_and_progress_indexes_present(self, mig8_clean: str):
        required_indexes = [
            ("idx_resource_chunks_chapter_model_source", r"public\.resource_chunks\s*\(\s*chapter_id\s*,\s*embedding_model\s*,\s*source_type\s*\)"),
            ("idx_resource_chunks_spec_refs_gin", r"public\.resource_chunks\s+USING\s+gin\s*\(\s*spec_refs\s*\)"),
            ("idx_resource_chunks_block_id", r"public\.resource_chunks\s*\(\s*block_id\s*\)"),
            ("idx_student_block_progress_student_chapter", r"public\.student_block_progress\s*\(\s*student_id\s*,\s*chapter_id\s*\)"),
            ("idx_student_block_progress_student_lesson", r"public\.student_block_progress\s*\(\s*student_id\s*,\s*lesson_id\s*\)"),
            ("idx_learning_blocks_chapter_order", r"public\.learning_blocks\s*\(\s*chapter_id\s*,\s*block_index\s*\)"),
        ]
        for idx_name, target_pat in required_indexes:
            assert re.search(
                rf"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+{idx_name}\s+ON\s+{target_pat}",
                mig8_clean,
                re.IGNORECASE,
            ), f"Missing expected index {idx_name}"

    def test_no_duplicate_indexes_mirroring_unique_constraints(self, mig8_clean: str):
        forbidden_dupes = [
            r"CREATE\s+INDEX\b[^;]*ON\s+public\.student_block_progress\s*\(\s*student_id\s*,\s*block_id\s*\)",
            r"CREATE\s+INDEX\b[^;]*ON\s+public\.learning_blocks\s*\(\s*lesson_id\s*,\s*block_index\s*\)",
            r"CREATE\s+INDEX\b[^;]*ON\s+public\.learning_blocks\s*\(\s*lesson_id\s*,\s*slug\s*\)",
            r"CREATE\s+INDEX\b[^;]*ON\s+public\.lessons\s*\(\s*chapter_id\s*,\s*slug\s*\)",
        ]
        for pat in forbidden_dupes:
            assert not re.search(pat, mig8_clean, re.IGNORECASE), (
                f"Redundant index duplicates a UNIQUE constraint: {pat}"
            )


# ---------------------------------------------------------------------------
# 6. `public.match_chapter_chunks` RPC & Legacy `match_resource_chunks` Preservation
# ---------------------------------------------------------------------------

class TestMatchChapterChunksRPC:
    def test_rpc_signature_and_defaults(self, mig8_clean: str):
        fn = _extract_function_block(mig8_clean, "match_chapter_chunks")
        expected_args = [
            r"query_embedding\s+vector\(1024\)",
            r"filter_chapter_id\s+UUID",
            rf"filter_embedding_model\s+TEXT\s+DEFAULT\s+'{re.escape(ACTIVE_EMBED_MODEL)}'",
            r"filter_source_types\s+TEXT\[\]\s+DEFAULT\s+NULL",
            r"filter_spec_refs\s+TEXT\[\]\s+DEFAULT\s+NULL",
            r"match_threshold\s+FLOAT\s+DEFAULT\s+0\.0",
            r"match_count\s+INTEGER\s+DEFAULT\s+10",
        ]
        for arg_pat in expected_args:
            assert re.search(arg_pat, fn, re.IGNORECASE), f"RPC missing argument: {arg_pat}"

    def test_rpc_returns_citation_metadata_columns(self, mig8_clean: str):
        fn = _extract_function_block(mig8_clean, "match_chapter_chunks")
        ret_match = re.search(r"RETURNS\s+TABLE\s*\((.*?)\)\s*LANGUAGE", fn, re.IGNORECASE | re.DOTALL)
        assert ret_match is not None, "RPC missing RETURNS TABLE (...) definition"
        ret_block = ret_match.group(1)
        for col in [
            "id",
            "resource_id",
            "resource_title",
            "resource_type",
            "chapter_id",
            "block_id",
            "block_index",
            "block_slug",
            "block_title",
            "source_type",
            "chunk_index",
            "chunk_text",
            "chunk_type",
            "source_refs",
            "spec_refs",
            "embedding_model",
            "token_count",
            "similarity",
        ]:
            assert re.search(rf"\b{col}\b", ret_block, re.IGNORECASE), (
                f"match_chapter_chunks RETURNS TABLE missing column: {col}"
            )

    def test_rpc_filters_strictly_by_chapter_and_embedding_model(self, mig8_clean: str):
        fn = _extract_function_block(mig8_clean, "match_chapter_chunks")
        assert re.search(r"rc\.chapter_id\s*=\s*filter_chapter_id", fn, re.IGNORECASE)
        assert re.search(r"rc\.embedding_model\s+IS\s+NOT\s+NULL", fn, re.IGNORECASE)
        assert re.search(r"rc\.embedding_model\s*=\s*filter_embedding_model", fn, re.IGNORECASE)
        assert re.search(r"rc\.source_type\s*=\s*ANY\s*\(\s*filter_source_types\s*\)", fn, re.IGNORECASE)
        assert re.search(r"rc\.spec_refs\s*&&\s*filter_spec_refs", fn, re.IGNORECASE)
        assert re.search(
            r"\(?\s*1\s*-\s*\(\s*rc\.embedding\s*<=>\s*query_embedding\s*\)\s*\)?\s*>=\s*match_threshold",
            fn,
            re.IGNORECASE,
        )
        assert re.search(r"\bSTABLE\b", fn, re.IGNORECASE)
        assert re.search(r"SET\s+search_path\s*=\s*public", fn, re.IGNORECASE)

    def test_rpc_execute_grant_present(self, mig8_clean: str):
        assert re.search(
            r"GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+public\.match_chapter_chunks\s*\(\s*"
            r"vector\(1024\)\s*,\s*UUID\s*,\s*TEXT\s*,\s*TEXT\[\]\s*,\s*TEXT\[\]\s*,\s*FLOAT\s*,\s*INTEGER\s*"
            r"\)\s+TO\s+anon\s*,\s*authenticated\s*;",
            mig8_clean,
            re.IGNORECASE,
        )

    def test_legacy_match_resource_chunks_preserved_untouched(self, mig8_clean: str):
        # mig_8 must not modify or drop match_resource_chunks
        assert not re.search(r"\bmatch_resource_chunks\b", mig8_clean, re.IGNORECASE), (
            "mig_8 must leave legacy 3-arg match_resource_chunks untouched"
        )
        # Verify legacy 3-arg RPC still exists intact in mig_0 and mig_7
        for legacy_path in (MIG_0_PATH, MIG_7_PATH):
            legacy_sql = _strip_sql_comments(legacy_path.read_text(encoding="utf-8"))
            assert re.search(
                r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.match_resource_chunks\s*\(\s*"
                r"query_embedding\s+vector\(1024\)\s*,\s*"
                r"match_count\s+INTEGER\s+DEFAULT\s+10\s*,\s*"
                r"filter_resource_id\s+UUID\s+DEFAULT\s+NULL\s*\)",
                legacy_sql,
                re.IGNORECASE,
            ), f"Legacy 3-arg match_resource_chunks missing in {legacy_path.name}"


# ---------------------------------------------------------------------------
# 7. Row Level Security (RLS) Policies
# ---------------------------------------------------------------------------

class TestRLSPolicies:
    @pytest.mark.parametrize("table", ["lessons", "learning_blocks", "student_block_progress"])
    def test_rls_enabled_on_all_new_tables(self, mig8_clean: str, table: str):
        assert re.search(
            rf"ALTER\s+TABLE\s+public\.{table}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY\s*;",
            mig8_clean,
            re.IGNORECASE,
        ), f"RLS not enabled on public.{table}"

    @pytest.mark.parametrize("table", ["lessons", "learning_blocks"])
    def test_catalog_tables_have_read_only_authenticated_rls(self, mig8_clean: str, table: str):
        assert re.search(
            rf"CREATE\s+POLICY\s+\"Enable read access for authenticated users only\"\s+"
            rf"ON\s+public\.{table}\s+FOR\s+SELECT\s+TO\s+authenticated\s+USING\s*\(\s*true\s*\)\s*;",
            mig8_clean,
            re.IGNORECASE,
        )
        # No browser write policies on catalog tables
        assert not re.search(
            rf"CREATE\s+POLICY\b[^;]*ON\s+public\.{table}\s+FOR\s+(?:INSERT|UPDATE|DELETE|ALL)\b",
            mig8_clean,
            re.IGNORECASE,
        )

    def test_student_block_progress_owner_scoped_rls_policies(self, mig8_clean: str):
        assert re.search(
            r"ON\s+public\.student_block_progress\s+FOR\s+SELECT\s+TO\s+authenticated\s+"
            r"USING\s*\(\s*auth\.uid\(\)\s*=\s*student_id\s*\)",
            mig8_clean,
            re.IGNORECASE,
        )
        assert re.search(
            r"ON\s+public\.student_block_progress\s+FOR\s+INSERT\s+TO\s+authenticated\s+"
            r"WITH\s+CHECK\s*\(\s*auth\.uid\(\)\s*=\s*student_id\s*\)",
            mig8_clean,
            re.IGNORECASE,
        )
        assert re.search(
            r"ON\s+public\.student_block_progress\s+FOR\s+UPDATE\s+TO\s+authenticated\s+"
            r"USING\s*\(\s*auth\.uid\(\)\s*=\s*student_id\s*\)\s+"
            r"WITH\s+CHECK\s*\(\s*auth\.uid\(\)\s*=\s*student_id\s*\)",
            mig8_clean,
            re.IGNORECASE,
        )
        assert re.search(
            r"ON\s+public\.student_block_progress\s+FOR\s+DELETE\s+TO\s+authenticated\s+"
            r"USING\s*\(\s*auth\.uid\(\)\s*=\s*student_id\s*\)",
            mig8_clean,
            re.IGNORECASE,
        )
