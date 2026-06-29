-- Drop the old table and function since the dimensions were wrong
drop table if exists documents cascade;
drop function if exists match_documents cascade;

-- Enable the pgvector extension
create extension if not exists vector;

-- Create the table with 3072 dimensions
create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  content text, 
  metadata jsonb, 
  embedding vector(3072) -- 3072 dimensions for Google models/gemini-embedding-2
);

-- Create a function to search for documents
create or replace function match_documents (
  query_embedding vector(3072),
  match_count int DEFAULT null,
  filter jsonb DEFAULT '{}'
) returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
#variable_conflict use_column
begin
  return query
  select
    id,
    content,
    metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where metadata @> filter
  order by documents.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Index creation skipped because pgvector HNSW does not support >2000 dimensions.
-- Exact KNN search will be used instead, which is perfect for this bot!
