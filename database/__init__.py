import os

use_supabase = os.getenv("USE_SUPABASE", "true").lower() in ("1", "true", "yes")
if use_supabase and os.getenv("SUPABASE_URL"):
    from .supabase_db import *  # noqa: F401,F403
else:
    from .db import *  # noqa: F401,F403
