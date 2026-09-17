-- משימה א (1.3, חיפוש סמנטי) - ברק, 2026-09-16/17: "בנה את זה
-- במלואו, כולל endpoint... חיפוש היברידי: BM25 על הטקסט + דמיון
-- וקטורי, משולבים". סכמה בלבד כאן - לא כתיבת דאטה (זו חסומה הלילה
-- על SUPABASE_SERVICE_ROLE_KEY חסר, ראו docs/night-report.md).
--
-- text-embedding-3-large (OpenAI) -> vector(1024), *לא* 3072 (ברירת
-- המחדל של המודל) - נתפס בפועל מול ה-DB האמיתי: אינדקס HNSW/IVFFlat
-- ב-pgvector תומך עד 2,000 מימדים בלבד (ניסיון ראשון עם 3072 נכשל,
-- "column cannot have more than 2000 dimensions for hnsw index").
-- 1024 מוקטן דרך פרמטר dimensions הרשמי של OpenAI (packages/llm/
-- embeddings.py) - לא נבדק בפועל מול ה-API עצמו (api.openai.com
-- חסום ברמת ה-proxy של סביבת ה-agent, ראו night-report).
--
-- "BM25" בפועל כאן הוא ts_rank_cd על tsvector('simple', ...) - הקירוב
-- המעשי הזמין ב-Postgres הרגיל (אין BM25 מילולי מובנה) - לא pgroonga/
-- rum (זמינים כתוספים אך לא הותקנו - שינוי תשתית נפרד, לא נדרש כאן).
-- קונפיגורציית 'simple' (לא 'hebrew' - לא קיימת ב-Postgres כברירת
-- מחדל) - טוקניזציה בסיסית בלי stemming עברי.

create extension if not exists vector;

create table if not exists search_chunks (
  id bigint generated always as identity primary key,
  law_id text not null references laws(id) on delete cascade,
  section_number text not null,
  chunk_index int not null,
  node_ids text[] not null,
  context_prefix text not null,
  body text not null,
  contains_raw_block boolean not null default false,
  embedding vector(1024),
  created_at timestamptz not null default now()
);

comment on table search_chunks is
  'chunks לחיפוש סמנטי היברידי (משימה א, 1.3) - packages/corpus/chunking.py בונה,
   packages/llm/embeddings.py מטמיע. embedding=null עד שה-ingest ירוץ (חסום הלילה).';

-- אינדקס וקטורי (HNSW - pgvector 0.8.2, נבדק זמין) לדמיון קוסינוס.
-- לא נבנה על טבלה ריקה בפועל - concurrently לא נדרש כאן (create
-- table חדשה, לא migration על טבלה קיימת עם traffic).
create index if not exists search_chunks_embedding_idx
  on search_chunks using hnsw (embedding vector_cosine_ops);

create index if not exists search_chunks_fts_idx
  on search_chunks using gin (to_tsvector('simple', context_prefix || ' ' || body));

create index if not exists search_chunks_law_id_idx on search_chunks (law_id);

alter table search_chunks enable row level security;
-- בלי policies בכוונה, כמו שאר טבלאות הקורפוס (security_invoker
-- views/service_role-only) - גישה רק דרך service_role בצד השרת,
-- אותה מדיניות בדיוק כמו laws/nodes/law_versions.

-- פונקציית חיפוש היברידי - RPC יחיד דרך REST (POST /rest/v1/rpc/
-- hybrid_search_chunks), לא שתי שאילתות נפרדות מה-API. משקללת
-- full-text (ts_rank_cd) ודמיון וקטורי (1 - cosine distance) לציון
-- משולב אחד. security invoker (לא definer) + search_path נעול -
-- אותה מדיניות שתוקנה הערב לפונקציות אחרות (ראו TASKS.md,
-- SECURITY DEFINER/mutable search_path).
create or replace function hybrid_search_chunks(
  query_text text,
  query_embedding vector(1024),
  match_count int default 10,
  full_text_weight float default 0.5,
  semantic_weight float default 0.5
)
returns table (
  id bigint,
  law_id text,
  section_number text,
  context_prefix text,
  body text,
  full_text_rank float,
  semantic_similarity float,
  combined_score float
)
language sql
stable
security invoker
set search_path = public
as $$
  with fts as (
    select sc.id, ts_rank_cd(to_tsvector('simple', sc.context_prefix || ' ' || sc.body), plainto_tsquery('simple', query_text)) as rank
    from search_chunks sc
    where to_tsvector('simple', sc.context_prefix || ' ' || sc.body) @@ plainto_tsquery('simple', query_text)
  ),
  vec as (
    select sc.id, 1 - (sc.embedding <=> query_embedding) as similarity
    from search_chunks sc
    where sc.embedding is not null
    order by sc.embedding <=> query_embedding
    limit greatest(match_count * 4, 40)
  )
  select
    sc.id, sc.law_id, sc.section_number, sc.context_prefix, sc.body,
    coalesce(fts.rank, 0)::float as full_text_rank,
    coalesce(vec.similarity, 0)::float as semantic_similarity,
    (full_text_weight * coalesce(fts.rank, 0) + semantic_weight * coalesce(vec.similarity, 0))::float as combined_score
  from search_chunks sc
  left join fts on fts.id = sc.id
  left join vec on vec.id = sc.id
  where fts.id is not null or vec.id is not null
  order by combined_score desc
  limit match_count;
$$;
