Goal: Improve Admin Dashboard (Dashboard Vietnamese + Latest Orders improvements + Stock bulk ops + Admin 1-1 chat with Telegram users).
Success Criteria:
- Dashboard cards show Vietnamese labels.
- "Don hang gan nhat" table has a "Username" column showing the username for the row's user_id.
- Product column shows the product's name (not id/other field).
- "Thoi gian" displays correctly for timezone Asia/Ho_Chi_Minh.
- Stocks page:
  - "Danh sach Stock" table supports selecting multiple rows and bulk delete and/or bulk edit.
  - "Them Stock moi" form has an additional tab to bulk delete stocks by pasted multiline content (1 entry per line) with a confirm modal showing how many rows will be deleted.
  - Tab switcher and multi-select checkboxes look polished and consistent with the dashboard theme.
  - Stock add/delete forms use a consistent 2/3 (input) + 1/3 (button) layout.
- Users page:
  - Each user row has a "Nhắn tin" button that opens a dedicated chat page.
  - Chat page shows message history between bot and that user and supports 1-1 messaging in a Telegram-like UI.
Constraints/Assumptions:
- Work within this repo only.
- Admin dashboard code lives under `admin-dashboard/`. (confirmed)
- Dashboard can read `users.username` and `products.name` via Supabase queries with the current auth/RLS setup. **UNCONFIRMED**
- Telegram Bot API does not provide a general "fetch chat history" endpoint; message history must be captured/stored by the bot when updates are received. **ASSUMED**
- Stocks are stored in Supabase table `stock` with at least `id`, `product_id`, `content`, `sold` (per `supabase_schema.sql`). (confirmed)
- Matching logic for bulk delete-by-text: delete rows where `stock.content` contains the entered line as a substring (case-insensitive), unless clarified otherwise. **UNCONFIRMED**
Key Decisions:
- Use Asia/Ho_Chi_Minh for display formatting in the dashboard (not server-wide changes), unless the code already supports per-user timezone. **ASSUMED**
Progress State:
- Done:
  - Read repo root; confirmed `admin-dashboard/` exists.
  - Updated `admin-dashboard/app/(admin)/page.tsx`:
    - Vietnamese labels for dashboard stat cards.
    - Latest Orders table: added `Username` column (looked up from `users` table via `user_id`).
    - Product column now displays product `name` (looked up from `products` table via `product_id`).
    - Time column formatted in `Asia/Ho_Chi_Minh` using `Intl.DateTimeFormat`.
  - Ran `npm -C admin-dashboard run build` successfully.
- Done:
  - Updated `admin-dashboard/app/(admin)/stock/page.tsx`:
    - "Danh sach stock" supports multi-select via checkboxes + bulk edit (sold status) + bulk delete with confirm modal.
    - "Them stock moi" form now has 2 tabs: Them and Xoa (delete-by-text). Delete tab supports multiline input, previews match count in confirm modal, then deletes matching stocks.
  - Ran `npm -C admin-dashboard run build` successfully after Stock changes.
- Done:
  - Improved Stocks UI polish:
    - Added a segmented tab switcher style (instead of primary/danger buttons) and styled table checkboxes + center alignment + indeterminate state.
    - Updated `admin-dashboard/app/globals.css` with `.segmented`, `.segmented-button`, `.checkbox`, `.checkbox-cell`.
  - Ran `npm -C admin-dashboard run build` successfully.
- Done:
  - Made Stock add/delete forms consistent: input 2/3 width + button 1/3 width using `.form-split` in `admin-dashboard/app/globals.css` and `admin-dashboard/app/(admin)/stock/page.tsx`.
  - Ran `npm -C admin-dashboard run build` successfully.
- Done:
  - Implemented admin 1-1 chat UI:
    - `admin-dashboard/app/(admin)/users/page.tsx`: "Nhắn tin" now opens a dedicated chat page per user.
    - `admin-dashboard/app/(admin)/users/[userId]/page.tsx`: chat-style history view + polling + send box.
    - `admin-dashboard/app/globals.css`: added chat UI styles.
    - `admin-dashboard/app/api/telegram/send/route.ts`: best-effort logging for 1-1 sends into `telegram_messages` (broadcasts are not logged here).
  - Added message storage + bot-side logging:
    - `supabase_schema.sql`: added `public.telegram_messages` + RLS policy for admins.
    - `database/supabase_db.py` + `database/db.py`: added `log_telegram_message(...)`.
    - `handlers/chat_logger.py` + `run.py`: log incoming private messages and wrap outgoing `send_message/send_document/send_photo`.
  - Ran `npm -C admin-dashboard run build` successfully.
  - Verified Python files compile (`python3 -m py_compile`) using `PYTHONPYCACHEPREFIX` to avoid cache permission errors.
- Now:
  - Apply Supabase migration for `telegram_messages` and verify chat history end-to-end with real Telegram updates.
- Next:
  - Verify updated UI on the Stocks page in the browser (tab styling + checkbox alignment/indeterminate + form layout).
  - Verify Stocks bulk actions and delete-by-text behavior against real data (RLS + matching behavior + pagination edge cases).
  - Verify in UI with real data that username/product name resolve correctly and that timestamps match Asia/Ho_Chi_Minh expectations.
  - If needed, apply the same timezone/date formatting helper to other admin tables (orders/deposits/withdrawals/usdt).
Open Questions:
- What field should be shown as "Username" (Telegram username, app username, or phone/email)? **UNCONFIRMED**
- Stocks bulk edit: currently implemented as changing `sold` status for selected rows; confirm if you also want bulk edit for other fields. **UNCONFIRMED**
- Do you already store Telegram messages anywhere (DB table) for history? If not, history can only be shown going forward after adding logging. **UNCONFIRMED**

Notes:
- `npm -C admin-dashboard run lint` prompts for initial ESLint setup (interactive), so it was not run.
- Chat UI: fixed a transient duplicate render when sending from Admin Dashboard by preventing overlapping polls and deduping by `message_id`.
