-- The ERP side of the "two worlds": structured, authoritative business records.
-- Every table below carries tenant_id so two unrelated businesses can share
-- one database without ever seeing each other's rows. Run this before
-- knowledge_base.sql (that file adds the bridge to the chat/"unstructured" side).

-- Where a purchase order (an order we placed with a supplier) currently stands.
CREATE TYPE purchase_order_status AS ENUM (
    'open',                 -- placed, nothing has arrived yet
    'partially_received',   -- some units arrived, but not all
    'received',             -- everything we ordered has arrived
    'cancelled'              -- the order was called off
);

-- Where a customer's order currently stands.
CREATE TYPE order_status AS ENUM (
    'pending',    -- placed, not yet on its way
    'shipped',    -- on its way to the customer
    'delayed',    -- running later than promised
    'delivered',  -- customer has received it
    'cancelled'   -- the order was called off
);

-- A company that sells raw materials to us. We buy things from suppliers.
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- random unique id, internal only, never shown to the model
    tenant_id TEXT NOT NULL,        -- which business this row belongs to (keeps businesses separate)
    reference_code TEXT NOT NULL,   -- the short id people actually say out loud, e.g. "SUP-1043"
    name TEXT NOT NULL              -- the supplier's full name, e.g. "Supplier B Ltd."
);

-- A company that buys goods from us. We sell things to customers.
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    reference_code TEXT NOT NULL,   -- e.g. "CUST-0078"
    name TEXT NOT NULL              -- e.g. "Sharma Fabrics"
);

-- An order we placed with a supplier to buy goods. Tracks whether it has arrived yet.
CREATE TABLE purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    reference_code TEXT NOT NULL,          -- e.g. "PO-4812"
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    status purchase_order_status NOT NULL, -- where the order stands right now
    quantity INT NOT NULL,                 -- how many units we ordered in total
    received_quantity INT NOT NULL DEFAULT 0, -- how many units have actually shown up so far
    due_date DATE,                         -- the date the supplier promised delivery by
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- An order a customer placed with us to buy goods. Tracks whether we've shipped it.
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    reference_code TEXT NOT NULL,        -- e.g. "ORD-2201"
    customer_id UUID NOT NULL REFERENCES customers(id),
    status order_status NOT NULL,        -- where the order stands right now
    promised_date DATE,                  -- the date we told the customer to expect it
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- A bill we sent a customer for goods they bought. What they owe us.
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    reference_code TEXT NOT NULL,        -- e.g. "INV-9931"
    customer_id UUID NOT NULL REFERENCES customers(id),
    amount NUMERIC(14, 2) NOT NULL,      -- the total amount billed on this invoice
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Money a customer actually paid against one of our invoices.
-- outstanding for a customer = sum(their invoices.amount) - sum(their payments.amount).
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    invoice_id UUID NOT NULL REFERENCES invoices(id),
    amount NUMERIC(14, 2) NOT NULL,   -- how much was paid in this one payment
    paid_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Raw materials or goods physically sitting in our warehouse right now.
CREATE TABLE inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    sku TEXT NOT NULL,           -- the stock-keeping code for this item, e.g. "DYE-BLU-40"
    description TEXT NOT NULL,   -- plain-English name of the item, e.g. "Blue dye, 40kg drum"
    quantity INT NOT NULL        -- how many units of this item we currently have on hand
);
