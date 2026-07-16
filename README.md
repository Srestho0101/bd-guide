# Documentation: Upazila Dataset Extraction & Cleaning for RAG Pipeline

**Project Objective:**
Extract administrative sub-district (Upazila) data from a bloated WordPress XML export (`export.xml`) and convert it into a clean, optimized SQLite database (`upazila_text.db`) suitable for a Retrieval-Augmented Generation (RAG) vectorization pipeline.

---

## 1. Overview of the Process

The initial dataset consisted of a 4.7MB standard WordPress eXtended RSS (WXR) export and a legacy SQLite schema. The goal was to parse the XML, extract specific custom fields (history, geography, travel, and development info) for 495 upazilas, and discard any records that contained empty placeholder text to prevent noise in the vector embeddings.

We achieved this through a two-script pipeline:

1. **`generate_upazila_db.py`**: A parser that filters the XML, maps custom metadata keys, and populates the SQLite schema.
2. **`prune_db.py`**: An automated cleaning algorithm that identifies placeholder text dynamically and wipes non-informative rows, leaving only content-rich records.

---

## 2. The Pitfalls (And How We Solved Them)

The WordPress data structure presented several unexpected challenges that required iterative debugging.

### Pitfall 1: The "NOT NULL" Crash (Hidden WordPress Clutter)

* **The Issue:** The initial database generation crashed with a `NOT NULL constraint failed: upazilas.title` error.
* **The Cause:** WordPress exports everything—including auto-drafts, menu items, and media attachments—which often lack a `<title>` tag. The XML parser fed `None` into the database, violating the schema.
* **The Fix:** Added a fallback mechanism in the Python script to assign `'Unknown Title'` to empty title tags, preventing the crash.

### Pitfall 2: The 1,152 Row Bloat

* **The Issue:** Despite Bangladesh only having 495 upazilas, the script extracted 1,152 records.
* **The Cause:** The script was initially processing every single `<item>` in the XML file (including 592 media attachments and various page revisions).
* **The Fix:** Implemented strict XML gatekeeping. We filtered the parser to exclusively accept items where `<wp:post_type>` was set to `upazila` and `<wp:status>` was `publish`. This successfully reduced the dataset to the exact 495 target records.

### Pitfall 3: The Missing ACF Metadata

* **The Issue:** After running the first pruning attempt, only **1** informative record remained. The other 40+ known informative records were wiped out.
* **The Cause:** The WordPress site utilizes Advanced Custom Fields (ACF), which completely alters metadata keys. We were searching for `history_info`, but ACF had renamed these fields to `upazila-history-data`, `travel-guide-data`, etc. Because the script couldn't find the old keys, it inserted the default 61-character Bengali placeholder for everything.
* **The Fix:** Used terminal `grep` commands to map the frequency of `<wp:meta_key>` tags, identified the new ACF naming conventions, and updated the Python dictionary mapping to route the new ACF keys to the old SQLite columns.

### Pitfall 4: The Database Transaction Lock

* **The Issue:** The pruning script threw an `OperationalError: cannot VACUUM from within a transaction`.
* **The Cause:** The script attempted to compress and optimize the database file (`VACUUM`) before finalizing the bulk deletions (`conn.commit()`).
* **The Fix:** Swapped the execution order. Committed the transaction to memory first, then executed the vacuum.

### Pitfall 5: The "Gap-Based" Algorithm Trap

* **The Issue:** Our first dynamic pruning algorithm sorted records by length and looked for the biggest character difference between two side-by-side records to find the "cliff" between good data and junk data. It failed, leaving only 1 record again.
* **The Cause:** The character variance *within* the good data (e.g., a 6,331-character difference between the largest and second-largest upazila) was mathematically larger than the gap between the smallest good upazila and the placeholder text.

---

## 3. The Final Cleaning Protocol (The Plateau Method)

To successfully isolate the informative records, we discarded the "gap-based" algorithm and implemented a **Frequency-Based (Plateau)** approach.

Instead of looking for a drop-off, the final `prune_db.py` algorithm asks the database to find the *mode* (the most frequently occurring text length).

1. The algorithm detected that exactly **61 characters** (the length of the default placeholder string: `এই উপজেলার উন্নয়ন ও অগ্রযাত্রার তথ্য শীঘ্রই আপডেট করা হচ্ছে।`) appeared a massive **455 times**.
2. It set a dynamic threshold slightly above that length (111 characters).
3. It executed a bulk delete on all records falling at or below that threshold.

## 4. Final State

* **Total Clean Records Extracted:** 495
* **Placeholders Identified & Wiped:** 455
* **Final Informative Records Kept:** 40
* **Database Status:** Vacuumed, optimized, and strictly limited to text-dense records.

The `upazila_text.db` is now fully sanitized and optimized for immediate ingestion into the RAG vectorization pipeline.