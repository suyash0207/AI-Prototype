-- The entity-linking bridge between the two worlds: informal chat mentions
-- ("Supplier B", "supp B", "the blue thread guys") and the exact ERP record
-- they mean (SUP-1043). Created empty here in Phase 2 so Phase 3's linking
-- logic is pure code, not a migration. Run this after schema.sql.

-- Which kind of ERP record a knowledge_base row's canonical_id points at.
-- Needed because canonical_id alone is just a UUID -- without this, there's
-- no way to know which table to look it up in.
CREATE TYPE entity_type AS ENUM (
    'supplier',
    'customer',
    'purchase_order',
    'order',
    'inventory_item'
);

-- How a chat-to-ERP name mapping came to exist. Only reviewed/user_confirmed
-- rows are ever trusted silently -- an llm_suggested row is a pending
-- proposal a person hasn't looked at yet.
CREATE TYPE knowledge_source AS ENUM (
    'reviewed',        -- a human (including whoever set up the demo data) vouched for it
    'llm_suggested',   -- the model proposed it, not yet confirmed by a person
    'user_confirmed'   -- a user picked this from an ask_clarification question
);

-- A learned or confirmed mapping from an informal chat name to the exact ERP record it means.
-- e.g. chat says "Supplier B" or "supp B" -- this row says that means SUP-1043.
-- Only rows with source = reviewed or user_confirmed are ever trusted silently;
-- an llm_suggested row is a pending proposal, never used until a person confirms it.
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,                       -- which business this mapping belongs to
    alias_text TEXT NOT NULL,                      -- the informal phrase as written in chat, e.g. "supp B"
    canonical_type entity_type NOT NULL,           -- which kind of ERP record this points to
    canonical_id UUID NOT NULL,                    -- the id of that exact ERP record (no single FK possible -- it can point at any table)
    confidence NUMERIC(3, 2) NOT NULL DEFAULT 1.0,  -- how sure we are this mapping is correct, 0 to 1
    source knowledge_source NOT NULL                -- how this mapping came to exist (reviewed, model-suggested, user-confirmed)
);
