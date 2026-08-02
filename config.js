// TRIVIUM test-deployment config.
// The anon key is public by design: Row-Level Security in sql/schema.sql
// restricts it to insert-your-result and read-the-board (rows immutable).
window.TRIVIUM_CONFIG = {
  SUPABASE_URL: "https://kyraqgmumfdxvcplwqge.supabase.co",
  SUPABASE_ANON_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt5cmFxZ211bWZkeHZjcGx3cWdlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU2Njg5NzgsImV4cCI6MjEwMTI0NDk3OH0.ZKzV3XfeTVoL9bSAPLtpWLq4Fyrtu-eNsNSgyfa6VL8",
};
