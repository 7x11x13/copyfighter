CREATE TABLE IF NOT EXISTS "Claims" ( "Id" CHAR(11) PRIMARY KEY, "Title" TEXT, "Fake" BOOLEAN, "Claimed" BOOLEAN DEFAULT 0, "Score" INTEGER, "Claim" TEXT);
CREATE INDEX IF NOT EXISTS pending_disputes ON Claims(Id) WHERE Fake AND NOT(Claimed);
