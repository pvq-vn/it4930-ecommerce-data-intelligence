# Gold v2 validation

Read-only validation of Gold v2 table grains and joins.

- Counts: {'dim_source_parents': 7051, 'fact_listings': 10316, 'fact_reviews': 15805, 'fact_review_replies': 108}
- Unique keys: {'source_parent_id': True, 'listing_record_id': True, 'review_record_id': True, 'reply_record_id': True}
- Reviews with source-scoped parent: 15805/15805
- Hypothetical rows if every review joins every listing of its parent: 45651

The expanded count is diagnostic; it is not a canonical review count.
