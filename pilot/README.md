# Official debate review

This branch builds ten review images in the public records repository. The record importer and Worker never read from this branch. The publication job has no dependency on the review workflow.

The pilot uses a fixed ballot sample drawn from the app's 119th Congress vote archive in descending passage date and roll number. The sample includes only bills with attributed passages from members on both recorded sides. The House Clerk or Senate XML is rechecked before any model call. The Senate crosswalk uses the app's Bioguide and LIS identifiers.

GovInfo MODS metadata identifies the bill, chamber, official speaker marker and Bioguide ID. Text outside a recognized speaker turn is excluded. Explicit floor-manager designations take priority. A recorded vote alone does not establish that a particular paragraph argues the case for that vote. Both the selection and verification prompts check this.

Each result includes the bill, roll call, original source URLs and hashes, exact quotations and offsets, the member's ID and vote, and a neutral one-paragraph-source summary. Whitespace is normalized only for display. Each side receives the same number of distinct speakers, up to three per side. When the evidence runs out on either side, the longer list is shortened. A bill with no verified pair receives an empty-state review image.

A trusted maintainer can start a review after configuring the project-restricted GitHub Actions secret by changing only the review branch's `pilot/preview-request` marker. The workflow renders its images into `pilot/review` and commits each verified bill before proceeding. Repeating the run reuses results for unchanged debate passages. Records publication continues independently if the model, billing, evidence verification or screenshot rendering fails. The pilot does not activate an hourly AI job. Public delivery and app integration require review of the actual images.
