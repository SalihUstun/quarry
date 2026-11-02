-- migrate:up
CREATE TABLE tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO tenants (id, name) VALUES ('00000000-0000-0000-0000-000000000001', 'Default');

CREATE TABLE documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    file_name text NOT NULL,
    content_type text NOT NULL,
    storage_path text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    error text,
    page_count integer,
    uploaded_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX documents_tenant_created_idx ON documents (tenant_id, created_at DESC);

CREATE TABLE chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    document_id uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    page_number integer NOT NULL CHECK (page_number >= 1),
    content text NOT NULL,
    char_count integer NOT NULL,
    embedding vector(1024) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX chunks_tenant_document_idx ON chunks (tenant_id, document_id);
CREATE INDEX chunks_embedding_hnsw_idx ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE llm_usage (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    user_id text NOT NULL,
    operation text NOT NULL CHECK (operation IN ('chat', 'embedding')),
    provider text NOT NULL,
    model text NOT NULL,
    input_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    cost_usd numeric(14, 8),
    latency_ms integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX llm_usage_tenant_created_idx ON llm_usage (tenant_id, created_at);

-- migrate:down
DROP TABLE llm_usage;
DROP TABLE chunks;
DROP TABLE documents;
DROP TABLE tenants;
