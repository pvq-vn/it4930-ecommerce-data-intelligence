# Key and grain audit

Read-only audit over staging. No Gold tables or cross-store canonical IDs were created.

- Product rows: 10316; source/category/parent keys: 7051
- Review rows: 15805; review keys unique: True
- Reply rows: 108; reply keys unique: True
- Product listing identity statuses: `{'UNKNOWN': 2022, 'SKU_PRESENT': 8294}`
- Review variant link statuses: `{'PARENT_ONLY': 12849, 'VARIANT_MATCHED': 2405, 'VARIANT_UNRESOLVED': 551}`
- Review parent orphans: 0
- Duplicate SKU groups within parent: 0
- Duplicate SKU groups across parents: 1
- Name/color candidate collisions: 0

## Interpretation

`raw_record_id` is the stable observed-row identifier. Parent keys are source-scoped. A review may be linked to a parent while remaining unresolved at variant level. Candidate keys are audit evidence, not automatic entity resolution.
