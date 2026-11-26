# Data model v1

Status: v1 reviewed and approved by Onuralp and Melike in the team chat (recorded 2026-11-22, S0-03).
Update 2026-11-23: vector storage and read budget changed after the S0-10 decisions. Collections and links are unchanged, only fields and notes.

Collection names, document ids and the links between collections are fixed. Fields can change: update this file in the same PR that changes them, and Serhan approves.

## Principles

- Firestore is accessed only from `apps/web/src/features/*/api.ts`. The AI service uses the Admin SDK.
- Skills, departments and courses are slugs from `shared/*.json`. Documents store slugs, never labels.
- Each skill in `shared/skills.json` has `slug`, `label` and `category`. Categories are a fixed set: `frontend`, `backend`, `mobile`, `data-ai`, `design`, `devops`, `product`, `content-media`, `business`, `soft-skills`, `hardware`, `game-dev`. New skills can be added, but a slug never changes once in use.
- Timestamps are Firestore `Timestamp`. `createdAt` is set once, `updatedAt` on every change.
- Vectors live in separate collections so normal reads never download them and clients never see them.
- Firestore is schemaless, so adding a field is cheap. Renaming or removing one needs a note in the PR and a reseed.

## Free plan constraints (Spark)

- No Cloud Functions. Anything that would be a trigger must be done another way:
  - Counters (`applicantCount`, `likeCount`, `reportCount`) are updated by the client in the same batched write as the action, and security rules check the pair with `getAfter()`.
  - Embeddings are refreshed by the client calling the AI service after a save. `POST /reindex` on the AI service catches the misses.
  - Listings are not closed automatically at `deadline`. Queries and the UI filter by `deadline` instead.
- Spark has daily read and write quotas. Always paginate lists and never fetch whole collections.
- Similarity search does not use Firestore vector search. The AI service loads the vectors into memory and computes cosine similarity itself (decision of 2026-11-23). Vectors are plain number arrays, so no vector index is needed and the emulator behaves like production.
- The free quota is 50,000 reads per day per project, reset at midnight Pacific time (about 11:00 in Istanbul in winter). When it is used up, requests fail until the reset. Plan for 40 to 60 reads per active user per day: lists use one-time queries with a client-side cache instead of listeners, and a page size of 10. Reads made by security rules (`get()`, `getAfter()`) and by the AI service count too. Previews and tests use the separate `civienta-dev` project, not the production one.
- If the daily reads stay above about 35,000 for several days, the order is: more optimization first (data bundles, AI service cache), then a free move to another database (Supabase or Cloudflare D1), and a paid plan only as a temporary last resort. Keep Firestore access inside `features/*/api.ts` so such a move stays cheap.

## Collections

### `users/{uid}`
`uid` is the Firebase Auth uid.

| Field | Type | Notes |
|---|---|---|
| displayName | string | from the school account |
| email | string | from the auth token, never editable |
| department | string | slug from `departments.json` |
| classYear | number | 1 to 6 |
| bio | string | free text, max 500 chars |
| skills | string[] | slugs from `skills.json` |
| links | map | `github`, `linkedin`, `portfolio`, all optional |
| role | string | `student` (default), `moderator`, `admin`. Clients cannot write it. |
| onboarded | boolean | false until the profile form is completed |
| createdAt, updatedAt | timestamp | |

Public profile pages must not show `email`.

### `listings/{listingId}`

| Field | Type | Notes |
|---|---|---|
| ownerId | string | uid of the poster |
| ownerType | string | `startup`, `club`, `social` |
| orgName | string | startup, club or project name |
| title, description | string | |
| requiredSkills | string[] | slugs |
| niceToHaveSkills | string[] | slugs |
| duration | string | `short` (under a month), `semester`, `long` |
| weeklyHours | number | expected hours per week |
| slots | number | how many people are needed |
| deadline | timestamp? | optional application deadline |
| status | string | `draft`, `open`, `closed` |
| applicantCount | number | maintained in the apply batch |
| createdAt, updatedAt | timestamp | |

### `applications/{listingId}_{uid}`
The id is `listingId` + `_` + applicant uid. This makes a second application to the same listing impossible.

| Field | Type | Notes |
|---|---|---|
| listingId | string | |
| applicantId | string | |
| listingOwnerId | string | copied from the listing, used by security rules |
| listingTitle | string | copied from the listing, so "My applications" needs no extra reads |
| message | string | short note from the applicant |
| status | string | `pending`, `accepted`, `rejected`, `withdrawn`, `completed` |
| completion | map? | `approvedAt`, `roleTitle`, `note`. Set only by the owner when status becomes `completed`. |
| createdAt, updatedAt | timestamp | |

Allowed status changes:
- Applicant: `pending` to `withdrawn`.
- Listing owner: `pending` to `accepted` or `rejected`, `accepted` to `completed` (with `completion`).

The verified profile is built from two queries: the user's applications with status `completed`, and the user's published notes. There is no separate collection for it.

### `notes/{noteId}`
Notes are links in the MVP. No file upload, so no Storage.

| Field | Type | Notes |
|---|---|---|
| uploaderId | string | |
| uploaderName | string | copied for display |
| department | string | slug |
| courseCode | string | from `courses.json` |
| title, description | string | |
| type | string | `note`, `summary`, `resource`, `exam` |
| url | string | must start with `https://` |
| source | string | `onedrive`, `drive`, `other` |
| likeCount, reportCount | number | maintained in the like and report batches |
| status | string | `published`, `hidden`, `removed` |
| createdAt | timestamp | |

Subcollections (the document id is the user uid, so one like and one report per user):
- `notes/{noteId}/likes/{uid}`: `createdAt`
- `notes/{noteId}/reports/{uid}`: `reason`, `createdAt`

### `listingVectors/{listingId}` and `userVectors/{uid}`
Written and read only by the AI service.

| Field | Type | Notes |
|---|---|---|
| embedding | number[] | plain array of numbers, not the Firestore vector type. The dimension depends on the local model chosen in S0-10. |
| model | string | model name, so old vectors can be detected after a model change |
| updatedAt | timestamp | |

## Security rules (summary)

| Collection | Read | Write |
|---|---|---|
| users | signed-in school account | owner only, never `role` or `email` |
| listings | signed-in school account (`draft` only by owner) | owner create and update, owner or admin delete |
| applications | applicant and listing owner | applicant creates and withdraws, listing owner changes status |
| notes | signed-in school account (`published` only, moderators see all) | uploader creates and edits own, moderators change `status` |
| notes likes and reports | owner of the doc | create and delete own, with the matching counter change in the same batch |
| listingVectors, userVectors | nobody (clients) | nobody (clients), Admin SDK only |

Every rule gets at least one allow test and one deny test. The school account check (`@stu.istinye.edu.tr`) is enforced in the rules, not only in the UI.

## Queries and indexes

- Listing feed: `status == open`, order by `createdAt` descending, paginated.
- Filters: `ownerType`, `duration` as equality filters. Skills with `array-contains-any` on `requiredSkills`. Only one `array-contains-any` is allowed per query, and it accepts a limited number of values.
- Each filter combination used by the UI needs a composite index in `firebase/firestore.indexes.json`.
- My applications: `applicantId == uid`, order by `createdAt`.
- Incoming applications: `listingOwnerId == uid`, optionally by `listingId`.
- Notes: `department` and `courseCode` equality filters, order by `createdAt` or `likeCount`. Title search must not download a whole course into the client: keep results limited (course filter plus a page limit) or search in the AI service. Decide in Sprint 2.

## Open questions

1. Hiding a note after N reports without Cloud Functions: filter on `reportCount` at query time, or a rules-validated batch that also sets `status`. Decide in Sprint 2.
2. Which local embedding model to use and its vector dimension (S0-10 benchmark). Gemini is only used in the benchmark, on synthetic data.
3. Where the AI service runs for free (S0-10). It holds all vectors in memory and should read as few documents as possible on start (only changed ones, by `updatedAt`).
