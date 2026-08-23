-- The entity-linking bridge between the two worlds: informal chat mentions
-- ("Supplier B", "supp B", "the blue thread guys") and the exact ERP record
-- they mean (SUP-1043). Created empty here in Phase 2 so Phase 3's linking
-- logic is pure code, not a migration. Run this after schema.sql.

-- A learned or confirmed mapping from an informal chat name to the exact ERP record it means.
-- e.g. chat says "Supplier B" or "supp B" -- this row says that means SUP-1043.
-- Only rows with source = reviewed or user_confirmed are ever trusted silently;
-- an llm_suggested row is a pending proposal, never used until a person confirms it.
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,                       -- which business this mapping belongs to
    alias_text TEXT NOT NULL,                      -- the informal phrase as written in chat, e.g. "supp B"
    -- which kind of ERP record this points to: supplier | customer | purchase_order | order | inventory_item
    -- (see app/domain/enums.py's CanonicalEntityType -- the sole source of truth for these values)
    -- needed because canonical_id alone is just a UUID -- without this, there's no way to know which table to look it up in
    canonical_type TEXT NOT NULL,
    canonical_id UUID NOT NULL,                    -- the id of that exact ERP record (no single FK possible -- it can point at any table)
    confidence NUMERIC(3, 2) NOT NULL DEFAULT 1.0,  -- how sure we are this mapping is correct, 0 to 1
    -- how this mapping came to exist: reviewed | llm_suggested | user_confirmed
    -- (see app/domain/enums.py's KnowledgeSource -- the sole source of truth for these values)
    -- only reviewed/user_confirmed rows are ever trusted silently -- an llm_suggested row is a pending proposal
    -- a person hasn't looked at yet
    source TEXT NOT NULL
);
