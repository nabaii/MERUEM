# Meruem Manual

Current-state manual based on code inspection of this repository on 2026-04-01.

This document explains:

- what Meruem is
- how the system is assembled
- why the code is structured the way it is
- how data moves through the platform
- where the current implementation is strong
- where the current implementation is still incomplete or internally inconsistent

The goal is not marketing language. The goal is operational truth.

## 1. What Meruem Is

Meruem is a Nigerian audience intelligence platform.

At a high level, it tries to do six things:

1. Collect public profile and post data from social platforms.
2. Normalize that data into a common internal schema.
3. Enrich it with NLP and embedding-based intelligence.
4. Turn profiles into audience segments and cross-platform identity links.
5. Package audiences into campaigns and export formats.
6. Produce deeper psychographic and lead-scoring assessments for outreach.

The product is clearly built in phases. You can see that in:

- Alembic migration names
- route comments
- Celery task comments
- frontend page coverage

That phased history matters because Meruem is not one single monolith with one single interaction pattern. It is a layered platform that grew like this:

- Phase 1: core schema, auth, collection jobs, profiles
- Phase 2: processing pipeline
- Phase 3: clustering, lookalike, identity resolution
- Phase 4: React dashboard
- Phase 5: campaigns, exports, notifications
- Phase 6: observability, scale-minded indexes, monitoring
- Phase 7: multi-source ingestion and bot scraping
- Phase 8: LLM-based profiling and lead scoring

That explains a lot of the design decisions. Meruem is not just a CRUD app. It is an orchestration system wrapped in a dashboard.

## 2. The Main Product Idea

Meruem takes noisy public social data and tries to convert it into marketing-grade audience knowledge.

The internal product logic is:

- Raw platform data is too platform-specific.
- Marketers need a platform-agnostic audience layer.
- That means profiles must be normalized into a shared schema.
- Once normalized, the system can enrich them with embeddings, interests, clusters, and identity matches.
- Once those abstractions exist, campaigns and exports become simple views over the enriched dataset.
- Once the intelligence layer is strong enough, LLM profiling can produce higher-order judgments like persona, purchase intent, and best outreach channel.

This is why Meruem stores both:

- low-level data like posts, counts, bios, and raw API responses
- high-level derived data like interests, clusters, identity links, assessments, and lead scores

The entire repo is organized around that transformation pipeline.

## 3. System Topology

Meruem runs as a multi-service Docker Compose stack.

### Core services

| Service | Role | Default Port |
| --- | --- | --- |
| `postgres` | primary relational database, plus `pgvector` | `5432` |
| `redis` | Celery broker, result backend, cache backend, slowapi storage | `6379` |
| `api` | FastAPI application | `8000` |
| `worker` | Celery worker for background jobs | none |
| `beat` | Celery beat scheduler | none |
| `frontend` | production React build served by Nginx | `80` |
| `frontend-dev` | Vite dev server with HMR | `3000` |
| `prometheus` | metrics scraping | `9090` |
| `grafana` | dashboards | `3001` in dev compose |

### Why the system is split this way

Meruem separates request handling from heavy processing on purpose.

FastAPI is used for:

- authentication endpoints
- dashboard reads
- job creation
- simple query endpoints

Celery is used for:

- collection
- NLP processing
- clustering
- identity resolution
- campaign export generation
- profiling and scoring

That split exists for good reasons:

- collection can be slow, rate-limited, or flaky
- NLP model loading is expensive
- clustering is batch oriented
- LLM profiling is slow and quota sensitive
- export generation is asynchronous by nature

If all of that happened inside request-response handlers, the API would be brittle and slow. Meruem avoids that by treating the API as control-plane code and the worker as execution-plane code.

## 4. Local Startup and Development Flow

The repo provides:

- `start-project.cmd`
- `start-project.ps1`
- `stop-project.cmd`
- `stop-project.ps1`

### What the startup script does

`start-project.ps1`:

1. Verifies Docker is installed and running.
2. Creates `.env` from `.env.example` if needed.
3. Starts `postgres`, `redis`, and `api`.
4. Waits for the API root to respond.
5. Runs Alembic migrations inside the API container.
6. Starts the remaining services:
   - `worker`
   - `beat`
   - either `frontend-dev` or built `frontend`
7. Waits for the frontend to respond.

This is a well-chosen sequence.

Why it is done this way:

- the API depends on Postgres and Redis
- migrations should happen after the API container exists and DB is reachable
- the frontend is less useful if the API is not ready
- workers should start after the datastore layer is healthy

### Frontend modes

The script supports two frontend modes:

- default: `frontend-dev` on `http://localhost:3000`
- built frontend: `frontend` on `http://localhost`

That is useful because it allows:

- fast UI iteration with HMR during development
- quick validation against the containerized production-style frontend

## 5. Repository Structure

The repo is organized by function, not by framework only.

### Top-level directories

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI app, models, tasks, collectors, migrations, tests |
| `frontend/` | React dashboard |
| `monitoring/` | Prometheus config |
| `backend/raw_data` or Docker volume `raw_data` | raw collector payloads and generated exports |

### Backend application directories

| Path | Purpose |
| --- | --- |
| `backend/app/api/` | HTTP dependencies and versioned routes |
| `backend/app/core/` | settings, security, metrics, cache, Celery |
| `backend/app/db/` | session, base, SQLAlchemy models |
| `backend/app/collectors/` | platform-specific ingestion logic |
| `backend/app/processing/` | NLP and embedding pipeline |
| `backend/app/intelligence/` | clustering, identity resolution, lookalike, topic rules |
| `backend/app/tasks/` | Celery task entry points |
| `backend/app/services/` | business logic for profiling, scoring, export shaping |
| `backend/app/notifications/` | in-app and email notification helpers |
| `backend/app/export/` | campaign export file generation |
| `backend/app/prompts/` | LLM prompt templates |
| `backend/app/schemas/` | Pydantic request/response models |

### Frontend directories

| Path | Purpose |
| --- | --- |
| `frontend/src/api/` | typed API wrappers |
| `frontend/src/pages/` | route-level screens |
| `frontend/src/components/` | layout, UI, charts, cards, filters |
| `frontend/src/store/` | Zustand auth state |
| `frontend/src/lib/` | utilities and display helpers |

The structure shows a strong preference for layered boundaries. That is good architecture for a platform like this because each layer has a clear job.

## 6. Backend Runtime Model

The backend has four major layers:

1. API layer
2. Task orchestration layer
3. Domain logic layer
4. Persistence layer

### 6.1 API layer

The API layer lives in `backend/app/api/v1/routes`.

Its responsibilities are intentionally narrow:

- validate input with Pydantic schemas
- read or write simple rows
- enqueue background work
- return query results

The API layer generally does not do expensive work directly.

This is the right choice because Meruem has a lot of tasks that are:

- slow
- retryable
- rate-limited
- batch-oriented

### 6.2 Task layer

The task layer lives in `backend/app/tasks`.

Its responsibilities are:

- pick up asynchronous work
- manage status updates and retries
- bridge queued jobs to collector or service modules
- commit durable results

This layer is where Meruem behaves like a workflow engine.

### 6.3 Domain logic layer

The domain logic is split across three areas:

- `collectors/` for source-specific ingestion
- `processing/` for NLP and embedding enrichment
- `intelligence/` and `services/` for higher-order inference and exports

This keeps the code easier to evolve because:

- collectors change when platforms change
- processing changes when models change
- services change when product logic changes

Those are different change vectors, so separating them is sensible.

### 6.4 Persistence layer

Persistence uses:

- SQLAlchemy ORM for structured domain rows
- PostgreSQL as the source of truth
- `pgvector` for embedding storage and similarity search
- Redis for cache, queue, and rate-limit storage

This is a pragmatic stack:

- Postgres handles structured entities and relations very well
- `pgvector` makes lookalikes and embedding workflows possible without a separate vector DB
- Redis fits queueing and ephemeral coordination

## 7. Core Configuration Philosophy

Settings are centralized in `backend/app/core/config.py`.

The settings model covers:

- database
- Redis and Celery
- auth
- social API credentials
- object storage
- Sentry
- SMTP
- Anthropic profiling
- bot proxy and headless behavior
- basic app metadata

### Why this matters

Meruem is highly integration-driven. A lot of functionality is only available when a specific credential exists.

Examples:

- Twitter collection requires `twitter_bearer_token`
- Instagram collection requires `instagram_access_token`
- LinkedIn API path requires LinkedIn credentials
- profiling requires `anthropic_api_key`
- email requires SMTP settings

This means Meruem is designed to degrade feature-by-feature rather than all-or-nothing. That is why many modules fail gracefully when configuration is missing.

Examples of graceful degradation:

- email notifications no-op if SMTP is not configured
- embeddings return `None` if the model is unavailable
- sentiment returns `0.0` if the model is unavailable
- spaCy-based NER falls back to rule-based extraction if the model is unavailable
- profiling endpoint rejects requests with `503` when Anthropic is not configured

That is a useful design for a platform still evolving across environments.

## 8. Data Model

The data model is the heart of Meruem.

The key design decision is that Meruem stores a platform-agnostic audience model on top of platform-specific ingestion.

### 8.1 Accounts

`Account` is the operator or customer using Meruem, not the social profile being analyzed.

Fields include:

- `email`
- `hashed_password`
- `full_name`
- `role`
- `api_key`
- `is_active`

Why this is separate from `SocialProfile`:

- Meruem users are product users
- social profiles are target audience records
- confusing those two would break the product model

### 8.2 Social graph entities

#### `SocialProfile`

This is the central audience entity.

A `SocialProfile` represents one social account on one platform.

Important fields:

- platform identity: `platform`, `platform_user_id`, `username`
- descriptive info: `display_name`, `bio`, `profile_image_url`
- location: `location_raw`, `location_inferred`
- audience stats: `follower_count`, `following_count`, `tweet_count`
- intelligence: `embedding`, `cluster_id`, `affinity_score`
- provenance: `source_method`, `last_collected`
- identity resolution link: `unified_user_id`

Why this model exists:

- it lets all platform collectors write into one common schema
- everything downstream can operate without caring where the profile came from

That one abstraction enables the rest of the product.

#### `Post`

Posts are attached to a `SocialProfile`.

The schema is deliberately generic enough to represent:

- tweets
- Instagram media captions
- Facebook page posts
- TikTok videos
- LinkedIn posts

Key fields:

- `platform_post_id`
- `content`
- `post_type`
- engagement counts
- `entities`
- `sentiment_score`
- `language`
- `posted_at`
- `is_processed`

Why the model is generic:

- Meruem wants cross-platform enrichment, not five separate downstream pipelines
- a shared post shape makes processing and analytics reusable

### 8.3 Interest and identity entities

#### `ProfileInterest`

Represents derived interest labels for a profile.

Each row is:

- one profile
- one topic
- one confidence score

Why row-per-topic instead of JSON on `SocialProfile`:

- easier filtering in SQL
- easier joins for explorer screens
- easier replacement during reclassification

#### `ProfileLink`

Represents a possible or confirmed identity match between two profiles on different platforms.

Stores:

- source and target profiles
- confidence
- contributing method signals
- status: `pending`, `confirmed`, `rejected`
- optional `unified_user_id`

Why this table exists:

- identity resolution should be auditable
- manual review is a first-class workflow
- the system needs to distinguish proposed links from confirmed ones

#### `UnifiedUser`

Represents a merged cross-platform person.

This is the canonical identity layer above social accounts.

Why separate `UnifiedUser` from `ProfileLink`:

- links are evidence
- unified users are the consolidated identity object

That distinction is important.

### 8.4 Cluster entities

#### `Cluster`

Represents an audience segment discovered by HDBSCAN.

Stores:

- `label`
- `description`
- `member_count`
- `top_interests`
- `last_updated`

#### `ClusterMetric`

Stores a time-stamped snapshot of cluster metrics.

Stores:

- `avg_engagement`
- `avg_followers`
- `interest_distribution`
- `computed_date`

Why split metrics from cluster:

- the cluster is the current segment identity
- metrics are snapshot history

That makes analytics easier later.

### 8.5 Campaign and export entities

#### `Campaign`

Represents a saved marketing audience definition.

Stores:

- name
- owner
- status
- saved filter JSON

#### `CampaignAudience`

Intended to represent selected audience members for a campaign.

Important note:

- the checked-in model stores `cluster_id`
- the routes and export task refer to `profile_id`

This is one of the clearest current inconsistencies in the repo and is discussed later in the caveats section.

#### `CampaignExport`

Represents an asynchronous export generation job and its output file.

Stores:

- format
- status
- profile_count
- file_key
- error_message

This is a clean pattern because export generation is not immediate and can fail independently of campaign creation.

### 8.6 Notification entity

`Notification` stores in-app notifications for accounts.

Supported types include:

- export ready
- export failed
- campaign activated
- campaign completed
- system

This gives the frontend a straightforward inbox model.

### 8.7 Profiling entities

#### `ProfileAssessment`

Stores the structured LLM assessment for a social profile.

Fields include:

- persona
- interests
- sentiment tone
- purchase intent
- influence tier
- engagement style
- psychographic driver
- recommended channel
- recommended message angle
- industry fit
- confidence
- raw LLM response

#### `LeadScore`

Stores the deterministic numeric score derived from an assessment and profile context.

Why this is separate from `ProfileAssessment`:

- assessment is interpretive output
- lead score is a deterministic product scoring layer

That separation is good because it lets scoring weights change without re-running the LLM.

#### `ProfilingJob`

Stores profiling batch execution metadata.

This is necessary because LLM profiling is:

- asynchronous
- rate limited
- potentially partially successful

The job table captures those realities.

## 9. API Surface

The API router includes these route groups:

- health
- auth
- profiles
- collection jobs
- processing
- clusters
- lookalike
- identity
- stats
- campaigns
- notifications
- import
- profiling

### Why the route split makes sense

These route groups map directly to product capabilities and background systems.

That keeps the codebase mentally navigable:

- if it is about ingestion, go to collection or import
- if it is about enrichment, go to processing or intelligence-backed routes
- if it is about activation, go to campaigns and exports
- if it is about psychographics, go to profiling

## 10. Authentication and Authorization

Meruem includes:

- registration
- login
- JWT creation helpers
- API key generation
- role support (`admin`, `client`)

### Intended model

The intended model is:

- `register` creates an account
- `login` returns a JWT
- `me` returns the authenticated account
- `api-key` creates a long-lived API key
- admin-only routes use a role check

### Actual current-state behavior

The checked-in dependency in `backend/app/api/deps.py` currently returns a singleton in-memory dev admin account from `get_current_account`, regardless of the bearer token.

That means:

- most protected backend routes are effectively in dev bypass mode
- the frontend only needs any token string in local storage to render protected pages
- the "Skip login (dev)" flow works because the frontend stores a fake token and the backend does not enforce real decoding in `get_current_account`

### Why this may exist

This was almost certainly added to speed up dashboard development before auth hardening was finished.

That is understandable during active development, but it materially changes runtime behavior.

## 11. Collection and Ingestion Architecture

Meruem supports three ingestion styles:

1. API-based platform collection
2. bot-based scraping
3. manual file import plus URL enrichment

This is one of the strongest parts of the design because it does not depend on a single fragile data acquisition strategy.

### 11.1 Collection jobs

The generic collection entry point is `CollectionJob`.

Flow:

1. API route creates a `CollectionJob` row.
2. The route enqueues a Celery task.
3. The task marks the job `running`.
4. It dispatches to a platform collector.
5. The collector returns normalized parsed profiles.
6. Profiles and posts are upserted.
7. Newly collected profile IDs are queued for NLP processing.
8. The job is marked `completed` or `failed`.

Why use a job table:

- the frontend needs something pollable
- collection can take time
- failure and retry status should be visible

### 11.2 API collectors

#### Twitter

Twitter collection uses Tweepy and bearer token auth.

What it does:

- fetches users by username
- fetches recent tweets
- persists raw API payloads
- parses users and tweets into Meruem records

Why it is built this way:

- Twitter has a mature API path
- rate limits are explicit
- recent post content is essential for downstream enrichment

The collector uses exponential backoff on `TooManyRequests`, which is exactly what you want for a rate-limited source.

#### Instagram

Instagram collection uses the Facebook Graph API.

What it does:

- finds users by username or known user IDs
- fetches profile fields and recent media
- computes engagement rate from likes/comments and follower count

Why API-first here:

- official access is cleaner than scraping where available
- business and creator accounts are accessible through the Graph ecosystem

#### Facebook

Facebook collection also uses Graph API.

What it does:

- fetches pages by username or page ID
- collects page posts
- computes engagement approximations

Why this matters:

- Facebook page data is still relevant for brand and publisher audience analysis

### 11.3 Bot collectors

#### TikTok

TikTok collection is browser-based.

It prefers:

- page hydration JSON (`SIGI_STATE` or `__UNIVERSAL_DATA_FOR_REHYDRATION__`)

and falls back to:

- DOM scraping

Why this is smart:

- hydration JSON is more stable and structured than the visible DOM
- DOM fallback gives the system a backup path when hydration changes

#### LinkedIn

LinkedIn uses a two-path strategy:

- API path for company pages when credentials exist
- bot scraping path for public profiles and fallback

Why this hybrid approach exists:

- official LinkedIn access is limited
- personal profile access is often only realistically possible through scraping
- company data may be cleaner through API when available

This is a good example of Meruem favoring capability over purity.

### 11.4 Bot stealth layer

`BotScraper` is a reusable Playwright wrapper that tries to look like a Nigerian mobile browser.

It does several things:

- rotates user agents biased toward common Nigerian Android devices
- uses mobile viewports
- sets `en-NG` locale and `Africa/Lagos` timezone
- injects stealth JS to mask automation fingerprints
- optionally injects cookies from a session pool
- optionally launches with rotated proxies
- uses ghost cursor movement, scrolling, and random delays

### Why the bot layer is designed this way

Because the product is Nigerian-market focused, it makes sense to mimic Nigerian browsing conditions rather than generic desktop Chrome.

That is not cosmetic. It can affect:

- localization
- content variants
- anti-bot risk signals
- session survivability

This is one of the most product-specific technical choices in the repo.

### 11.5 Proxy pool and session pool

Meruem stores bot infrastructure state in Redis.

Proxy pool features:

- add proxies by URL
- LRU rotation
- failure counting
- deactivation after repeated failures
- carrier tagging (`mtn`, `airtel`, `glo`, `9mobile`, etc.)

Session pool features:

- store authenticated browser cookies
- reuse sessions per platform
- invalidate sessions after challenges or bans

Why this exists:

- scraping reliability depends on session and network health
- that state should survive individual request lifecycles
- Redis is a natural fit for small mutable operational pools

### 11.6 Manual import

Manual import is a strong product bridge between automated collection and real operator workflows.

It supports:

- CSV upload
- Excel upload
- flexible column alias mapping
- platform inference from URLs
- optional enrichment through the bot layer

This is a practical design because real users often already have spreadsheets.

Instead of forcing all ingestion through APIs or bots, Meruem accepts partially structured human-curated data and then normalizes it.

That is good product engineering.

### 11.7 Raw payload storage

Collectors persist raw platform payloads through `RawStorage`.

Storage modes:

- local filesystem in development
- S3-compatible object storage in production

Why raw storage is important:

- debugging collector issues
- auditing parsing behavior
- reprocessing later without recollecting if needed

Meruem stores both the normalized data and the original source payloads, which is a mature ingestion pattern.

## 12. NLP Processing Pipeline

The processing pipeline lives in `backend/app/processing/pipeline.py`.

For each profile, it processes unprocessed posts and then updates profile-level derived fields.

### Pipeline steps

1. skip native retweets
2. clean text
3. detect language
4. extract entities
5. score sentiment
6. infer location
7. generate profile embedding

### Why this order is sensible

The order is not arbitrary.

- Retweets are skipped first because they are often low-signal repetition.
- Cleaning happens before language detection and sentiment so model inputs are cleaner.
- Entity extraction uses raw text so hashtags and mentions are preserved.
- Location inference consumes bio, raw location, and extracted entities.
- Embeddings happen at the end because they need the cleaned text and collected hashtags.

That is a coherent enrichment pipeline.

### 12.1 Text cleaning

The text cleaner:

- fixes encoding with `ftfy`
- normalizes Unicode
- strips URLs
- strips mentions
- preserves hashtags
- detects retweets
- detects language

The Pidgin-aware language logic is especially important.

It uses `langdetect`, but refines `"en"` to `"pcm"` if enough Nigerian Pidgin markers are present.

Why this matters:

- Nigerian social text often mixes English, Pidgin, and local-language influences
- raw language detection alone would miss that nuance

This is a good example of domain adaptation through lightweight heuristics.

### 12.2 Entity extraction

Entity extraction combines:

- regex for hashtags and mentions
- rule-based Nigerian brand and location detection
- optional spaCy NER

Why this hybrid approach exists:

- spaCy alone will not reliably capture Nigeria-specific brands and places
- hand-authored lists let the system encode local market knowledge
- spaCy still adds general named-entity coverage when available

This is a pattern Meruem uses repeatedly: combine general ML tools with market-specific rules.

### 12.3 Sentiment

Sentiment uses the multilingual Twitter XLM-R sentiment model.

Why this model:

- it is trained on social-style text
- it is multilingual
- it is better aligned to noisy short-form content than generic sentiment models

Meruem turns model labels into signed numeric scores:

- positive -> positive float
- negative -> negative float
- neutral -> `0.0`

### 12.4 Location inference

Location inference uses priority order:

1. bio
2. raw profile location
3. extracted locations from posts

Why this order:

- self-described bio location is usually deliberate and high-value
- raw platform location is helpful but noisy
- post-derived location is weakest and most indirect

This is a simple heuristic system, but it is appropriate for the current phase.

### 12.5 Embeddings

Embeddings use `all-MiniLM-L6-v2`, producing 384-dimensional vectors stored in `pgvector`.

Profile text is built from:

- bio
- recent cleaned posts
- deduplicated hashtags

Why build a combined profile text instead of embedding each post separately:

- the product cares about profile-level audience similarity
- one profile vector is cheaper to store and search
- centroid-like profile meaning is sufficient for clustering and lookalikes

This is a good tradeoff for a first production embedding layer.

### 12.6 Lazy loading

Processing modules import heavy models lazily inside workers.

Why this is important:

- API startup stays lighter
- worker memory is where model cost belongs
- model initialization happens only when actually needed

This is a strong operational choice.

## 13. Intelligence Layer

The intelligence layer is where Meruem stops being a collector and becomes an audience platform.

It has four main capabilities:

- topic classification
- clustering
- identity resolution
- lookalike search

### 13.1 Topic classification

The topic classifier is currently rule-based and multi-label.

Signals and weights:

- bio keyword matches: strongest
- hashtag matches: medium
- content mentions: weaker and capped

Why a rule engine instead of a trained classifier:

- faster to ship
- easier to debug
- easier to encode Nigeria-specific vocabulary
- low operational complexity

The code explicitly says it is intentionally swappable later. That is a good sign that the team saw this as a first implementation, not the end state.

### 13.2 Clustering

Clustering uses HDBSCAN over profile embeddings.

Why HDBSCAN:

- it handles uneven densities better than k-means
- it can label outliers as noise
- it does not require a fixed number of clusters

Those are all good properties for audience discovery where the number and shape of segments are unknown.

Cluster generation flow:

1. fetch all profiles with embeddings
2. run HDBSCAN
3. clear old assignments
4. recreate cluster rows
5. assign `cluster_id` on profiles
6. create cluster metric snapshots

Why Meruem rebuilds clusters instead of trying to surgically update them:

- clustering is batch inference, not stable identity
- full replacement is simpler and more deterministic
- HDBSCAN output may shift globally as data grows

This choice favors simplicity and consistency over historical cluster continuity.

### 13.3 Identity resolution

Identity resolution compares profiles across platforms using:

- display-name similarity
- username similarity
- shared bio URLs
- bio text similarity

Why these signals:

- they are cheap
- they are interpretable
- they work reasonably well for public-profile matching

Confidence thresholds:

- high confidence -> auto confirm and optionally create a `UnifiedUser`
- medium confidence -> create a pending review item
- low confidence -> ignore

This is a good human-in-the-loop design. Identity resolution is too risky to fully automate at marginal confidence.

The current implementation is `O(n^2)` across platform pairs, which the code comments acknowledge. That is acceptable for early datasets but not for long-term scale.

### 13.4 Lookalike search

Lookalike search:

- takes seed profiles or a seed cluster
- computes an embedding centroid
- uses `pgvector` cosine distance in SQL
- optionally applies filters before ranking

Why centroid search:

- it turns a seed set into one semantic query vector
- it is cheap and easy to explain
- it works well enough for initial audience expansion

Why use Postgres plus `pgvector` rather than a separate vector store:

- simpler operations
- enough for current scale
- closer coupling between vectors and relational filters

This is a very pragmatic architecture choice.

## 14. Task Orchestration and Scheduling

Meruem uses Celery in two ways:

- on-demand async work from API routes
- scheduled recurring work from Celery Beat

### Queues

The worker is configured with queues:

- `collection`
- `processing`
- `intelligence`
- `default`

Task routing maps families of tasks to these queues.

Why queue separation matters:

- collection and processing have very different performance profiles
- intelligence jobs are batchy and heavier
- export and generic tasks can stay on a general queue

### Beat schedule

Scheduled tasks include:

- hourly Twitter collection
- hourly Instagram collection
- nightly NLP processing
- nightly intelligence pipeline

Why this matters

Meruem combines event-driven updates and periodic reconciliation.

That is the right pattern because:

- not all data arrives from user-triggered actions
- some intelligence should be recomputed on a schedule
- nightly pipelines reduce pressure during active usage windows

### Chained workflows

The intelligence pipeline is explicitly chained:

- classify
- cluster
- resolve identities
- profile unassessed
- score new assessments

This shows a clear dependency graph:

- interests help characterize clusters
- clusters and embeddings gate profiling eligibility
- profiling generates assessments
- assessments feed scoring

That sequencing is thoughtful and product-aware.

## 15. Campaigns, Exports, and Notifications

Campaigns are Meruem's activation layer.

The conceptual product flow is:

1. define or discover an audience
2. save it as a campaign
3. activate the campaign
4. export it to a destination-friendly format
5. notify the user when the export is ready

### 15.1 Campaign model

A campaign stores:

- owner
- name
- status
- filter JSON

Why save filter JSON:

- it captures the audience definition used at creation time
- it is simple to render in the UI
- it allows future rehydration or recomputation

### 15.2 Exports

Export generation is asynchronous.

Supported formats:

- Meta custom audience style CSV
- Twitter tailored audience style CSV
- generic CSV

Why asynchronous:

- exporting depends on reading a campaign audience
- file generation and notification can fail independently
- the user should not wait on a request thread

### 15.3 Notifications

Meruem sends notifications through two channels:

- in-app notifications
- optional SMTP email

Why both:

- in-app is immediate and product-native
- email is useful for long-running exports and inactive users

The email layer gracefully skips when SMTP is missing, which fits the repo's general degrade-gracefully philosophy.

## 16. Profiling and Lead Scoring

Profiling is the highest-level intelligence subsystem in Meruem.

It turns a social profile into a psychographic marketing assessment.

### 16.1 Eligibility and selection

Profiles selected for profiling must currently have:

- an embedding
- a cluster assignment

Optional filters include:

- platform
- cluster
- location
- minimum followers
- unassessed only

Why these gates exist:

- profiling is expensive
- the system wants reasonably enriched profiles before spending LLM budget
- cluster membership implies the profile already passed core intelligence stages

### 16.2 Prompt construction

The profiling prompt includes:

- platform and handle
- bio
- follower/following counts
- stated and inferred location
- recent posts
- detected entities
- average sentiment
- cluster membership
- notable hashtags

Why include both raw and derived context:

- raw text preserves nuance
- derived context gives the model structured hints
- this reduces the risk of under-informed assessments

The prompt is explicitly tuned for Nigerian market context, including:

- Pidgin
- code-switching
- local consumer behavior

That is very aligned with the product thesis.

### 16.3 Structured output

The service expects exact JSON and contains cleanup plus retry logic when the first response is not valid JSON.

Why this matters:

- product workflows need machine-readable outputs
- invalid JSON would poison downstream storage and scoring

The retry with stricter instructions is a sensible operational guardrail.

### 16.4 Rate limiting and job control

Profiling jobs honor `profiling_rate_limit_per_minute`.

The job executor sleeps between items to stay within budget.

Why throttle inside the worker:

- external LLM APIs are quota-sensitive
- a queue alone does not solve provider-side rate limits

### 16.5 Deterministic scoring

After an assessment is created, `ScoringService` converts it into a lead score.

Factors include:

- purchase intent
- engagement style
- influence tier
- sentiment alignment
- follower count
- profile completeness
- cluster quality
- confidence

Why use deterministic scoring after LLM assessment:

- easier to tune
- easier to explain
- easier to recalculate with different weights

This is a good separation of concerns:

- LLM for semantic interpretation
- deterministic formula for commercial prioritization

### 16.6 Profiling exports

Profiling exports support:

- generic lead CSV
- HubSpot-shaped CSV

This shows the profiling subsystem is meant for sales and CRM workflows, not just audience analysis.

## 17. Frontend Architecture

The frontend is a React 18 SPA with:

- React Router
- TanStack Query
- Zustand
- Tailwind CSS
- Recharts
- React Hot Toast

### 17.1 Why this stack fits the product

This is a data-heavy dashboard, not a content site.

That means the frontend mostly needs:

- route-based screens
- query caching and refetching
- lightweight global auth state
- reusable cards, tables, and charts

React Query plus Zustand is a reasonable split:

- server state in Query
- tiny client state in Zustand

### 17.2 Routing

Public routes:

- `/login`
- `/register`

Protected routes under `AppShell`:

- `/dashboard`
- `/explorer`
- `/profiles/:id`
- `/clusters`
- `/clusters/:id`
- `/campaigns`
- `/campaigns/new`
- `/campaigns/:id`
- `/import`
- `/settings`

Why `AppShell` exists:

- shared layout
- sidebar
- auth gate
- consistent container width and spacing

### 17.3 Auth model in the frontend

The frontend stores:

- `token`
- `account`

in Zustand with persistence.

The API client reads the token from `localStorage` and attaches it as a bearer token.

Why this is simple:

- enough for an internal-style dashboard
- no refresh-token complexity
- easy to support the dev bypass flow

### 17.4 API client philosophy

The shared API client is intentionally minimal.

It:

- prefixes requests with `/api/v1`
- attaches bearer tokens
- throws a typed `ApiError`
- handles `204` responses

This is adequate because the frontend does not need sophisticated transport behavior yet.

## 18. Frontend Pages and Their Purpose

### 18.1 Dashboard

The dashboard shows:

- total profiles
- total posts
- total clusters
- active jobs
- platform distribution
- top clusters bubble chart
- recent collection jobs

Why this screen exists:

- it is the operator's health and value snapshot
- it answers "is the machine alive and useful?"

### 18.2 Audience Explorer

The explorer lets users search profiles by:

- text query
- platform
- interest
- cluster
- location
- follower range

Why this is important:

- Meruem's raw value only becomes usable when the audience can be searched interactively

This page is the main browse surface for normalized audience data.

### 18.3 Profile Detail

The profile detail page surfaces:

- identity information
- inferred location
- interests
- radar chart
- recent posts
- linked profiles

Why this screen matters:

- it turns a row in a table into a usable audience story
- it also demonstrates the value of enrichment and identity linking

### 18.4 Clusters and Cluster Detail

These pages expose the clustering subsystem.

They show:

- discovered segments
- cluster sizes
- top interests
- representative members

This is how ML output becomes explainable to a user.

### 18.5 Campaign pages

Campaign pages cover:

- campaign listing
- campaign creation
- reach estimation
- activation
- export history

Conceptually, this is the commercialization layer of the audience data.

### 18.6 Import page

The import page surfaces:

- CSV and Excel import
- single URL enrichment
- bulk URL enrichment
- recent manual-import jobs
- proxy pool stats
- session pool stats

This is an unusually operational page for a product UI, but it fits Meruem because ingestion reliability is part of the product.

### 18.7 Settings

Settings currently supports:

- account display
- API key generation and rotation

This is minimal, but appropriate for the current phase.

## 19. Frontend UX and Styling Choices

The UI uses:

- a dark slate-based theme
- brand blue accents
- Inter typography
- card-based layouts

Why this likely happened:

- fast to ship
- easy to keep consistent
- works well for analytics dashboards

There is no deep design system abstraction here. The UI is intentionally lightweight and practical.

That matches the product stage.

## 20. Observability and Operations

Meruem includes several operational layers.

### 20.1 Health checks

Endpoints:

- `/`
- `/api/v1/health`
- `/api/v1/health/db`
- `/metrics`

Why this is good:

- supports local sanity checks
- supports container readiness
- exposes pgvector status

### 20.2 Prometheus metrics

The API collects:

- HTTP request counts
- HTTP latency histograms
- Celery task counts

The middleware normalizes dynamic paths to avoid label-cardinality explosions.

That is a thoughtful detail and shows real operational awareness.

### 20.3 Rate limiting

SlowAPI is configured with Redis storage.

The limiter key attempts to prioritize:

- authenticated account ID
- API key hash
- IP address fallback

This is a good design because it avoids punishing shared IPs when real account identity exists.

### 20.4 Sentry

Sentry initialization is optional and only enabled if `sentry_dsn` exists.

Again, the repo prefers optional production hardening rather than hard dependencies.

### 20.5 Monitoring stack

The compose files support:

- Prometheus
- Grafana

This is a sign that the team expects the system to run continuously, not just as a developer playground.

## 21. Database and Migration History

The Alembic versions tell a story:

- `0001_initial_schema`
- `0002_phase2_processing_columns`
- `0003_phase3_vector_index`
- `0004_phase5_campaigns_export`
- `0005_phase6_indexes_columns`
- `0006_phase7_ingestion`
- `0007_phase8_profiling`

Why this matters

You can use the migration history to understand the product's real growth path:

- first collect and store
- then enrich
- then cluster and search
- then export and notify
- then harden for scale
- then broaden ingestion
- then add LLM-driven profiling

That phased buildup makes sense and the codebase still reflects it.

## 22. Testing Philosophy

Backend tests use:

- pytest
- FastAPI TestClient
- SQLite for smoke and unit tests

The test setup compiles JSONB and `pgvector` types into SQLite-compatible stand-ins.

Why this is useful:

- tests run without a live Postgres dependency
- logic can be validated cheaply

The tests focus mostly on:

- helper logic
- route mounting
- scoring math
- clustering behavior
- entity and location heuristics
- profiling prompt handling

This is a reasonable unit-heavy strategy for a repo with many external integrations.

It also means some integration seams are less exercised than the pure logic.

## 23. Why Meruem Works the Way It Does

This section answers the "why" more directly.

### 23.1 Heavy work is offloaded

Meruem does not trust request-response flows for expensive jobs.

Why:

- collection can block on rate limits
- ML models are slow to load
- clustering is batch work
- LLM calls are slow and quota-bound

So the system moves heavy work into Celery.

### 23.2 The normalized audience model comes first

Everything important depends on `SocialProfile` and `Post`.

Why:

- once every platform maps into one shared shape, the rest of the product can be platform-agnostic

That decision is what makes:

- explorer filters
- clustering
- lookalikes
- campaigns
- profiling

possible without five separate implementations.

### 23.3 Nigerian context is first-class

This is not a globally generic audience engine with Nigeria slapped on top.

Evidence:

- Pidgin-aware language detection
- Nigerian brands and cities in entity extraction
- Nigerian mobile fingerprints in bot scraping
- profiling prompt explicitly tuned to Nigerian consumer behavior

Why this matters:

- local context is part of the product moat
- off-the-shelf global heuristics would miss real signal

### 23.4 Rules plus ML plus LLM

Meruem does not choose one intelligence approach.

It uses:

- rules for known deterministic patterns
- embeddings for semantic similarity
- clustering for emergent groups
- LLMs for psychographic interpretation

Why this blend is appropriate:

- rules are cheap and reliable
- embeddings capture semantics
- clustering gives discovery
- LLMs add narrative interpretation

Each tool is used where it makes the most sense.

### 23.5 The product is operator-facing

Many pages are not end-user consumer UX. They are operator tooling.

Evidence:

- import jobs
- proxy/session pools
- recent job status
- API key rotation

Why this matters:

- Meruem is part product, part operational control panel
- ingestion reliability is itself a product requirement

## 24. Current-State Caveats and Inconsistencies

This is the most important section if you need to work on the repo honestly.

### 24.1 Auth is currently bypassed in backend dependencies

`get_current_account` always returns a dev admin account.

Impact:

- backend route protection is mostly not real right now
- the frontend token check is mostly a UI gate, not real backend auth
- test expectations around auth may no longer match runtime code

### 24.2 Campaign audience code appears mid-refactor

The `CampaignAudience` model and initial migration define `cluster_id`.

But campaign routes and export tasks use `profile_id`.

Impact:

- adding profiles to campaigns likely fails at runtime
- deleting profiles from campaigns likely fails
- export generation likely fails or returns empty results

Interpretation:

This looks like a partially completed shift from cluster-based campaign audiences to profile-based campaign audiences.

### 24.3 Campaign reach estimate uses a nonexistent field

The reach estimate route filters on `SocialProfile.location`, but the model only has:

- `location_raw`
- `location_inferred`

Impact:

- reach estimation with a location filter is likely broken

### 24.4 Celery app include list omits `import_tasks`

The Celery app includes:

- collection
- processing
- intelligence
- campaigns
- profiling tasks

But not `app.tasks.import_tasks`.

Impact:

- manual import and URL enrichment tasks may not be registered in workers depending on import behavior

### 24.5 Profiling backend exists without a frontend workflow

The backend has a substantial profiling subsystem.

The frontend currently has no profiling page set.

Impact:

- Phase 8 exists mainly as API capability right now, not a full dashboard feature

### 24.6 Lookalike search is implemented but not surfaced in the UI

There is a frontend API wrapper for lookalikes, but no clear page or control currently uses it.

Impact:

- a meaningful backend feature is present but not yet exposed to users

### 24.7 Frontend platform support is narrower than backend platform support

Examples:

- explorer filters expose only a subset of platforms
- campaign builder includes `youtube` even though collection support is not really present in the backend collector set

This suggests the UI and backend are not fully synchronized on capability boundaries.

### 24.8 There are visible encoding issues in the repo

Several files contain mojibake in comments or UI strings.

Impact:

- readability suffers
- some user-visible labels may look corrupted
- file encoding hygiene likely needs cleanup

### 24.9 Some tests likely reflect earlier auth behavior

The checked-in tests still assume stricter auth semantics than the current dependency implementation suggests.

I could not run the test suite in this environment because `pytest` was not available on PATH, so this is a code-inspection conclusion rather than a runtime-verified one.

## 25. Practical Mental Model for Working on Meruem

If you are new to this codebase, use this mental model:

### Layer 1: data enters

Collectors and manual import create `SocialProfile` and `Post` rows.

### Layer 2: data is enriched

Processing turns raw text into:

- language
- entities
- sentiment
- inferred location
- embeddings

### Layer 3: profiles become audiences

Intelligence turns enriched profiles into:

- interests
- clusters
- identity links
- lookalike results

### Layer 4: audiences become activation artifacts

Campaigns and exports turn that intelligence into deliverables.

### Layer 5: top-value leads get interpreted

Profiling and scoring turn enriched profiles into psychographic and commercial lead records.

If you understand those five layers, you understand Meruem.

## 26. How to Extend the System Safely

### Adding a new collector

You would typically need to touch:

- `backend/app/collectors/`
- `backend/app/tasks/collection.py`
- possibly schemas or frontend options

The design expectation is:

- parse platform data into the shared profile/post shape
- upsert into `SocialProfile` and `Post`
- let the rest of the pipeline remain unchanged

That is a sign of good normalization.

### Changing NLP behavior

You should mostly work inside:

- `backend/app/processing/`

Because the processing pipeline is isolated, you can improve one stage without rewriting the rest of the system.

### Improving intelligence

You should mostly work inside:

- `backend/app/intelligence/`
- `backend/app/tasks/intelligence.py`

Because tasks call plain Python logic modules, the intelligence layer is relatively easy to swap or upgrade.

### Improving profiling

You should mostly work inside:

- `backend/app/services/profiling_service.py`
- `backend/app/prompts/profiling.py`
- `backend/app/services/scoring_service.py`

The code already separates prompt design, provider calling, and numeric scoring, which is a good foundation.

## 27. Final Assessment

Meruem is a serious full-stack audience intelligence system with a strong core idea:

- normalize cross-platform audience data
- enrich it in layers
- turn it into marketer-usable outputs

Its strongest architectural traits are:

- good separation between control-plane API code and worker execution
- a solid shared data model around `SocialProfile` and `Post`
- thoughtful use of `pgvector`
- strong Nigeria-specific adaptations
- practical ingestion flexibility
- clear phased growth path

Its most important current weaknesses are:

- backend auth bypass
- campaign audience schema drift
- some feature/UI mismatch
- a few operational seams that look unfinished

In other words:

Meruem is already much more than a prototype in architecture, but parts of the implementation still show an active transition from "fast-moving build phase" to "coherent production system."

That is the most accurate single-sentence description of the codebase.
