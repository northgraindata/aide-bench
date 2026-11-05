# Events pipeline

Two partner feeds write `event_date`. Feed A uses ISO dates (`2026-10-30`), feed B uses `30/10/2026`.
`clean_events` normalizes them into `events_clean`.
