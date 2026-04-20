# API Reference

API configuration details for all skill and plugin sources.

## SkillsMP API

**Base URL:** `https://skillsmp.com/api/v1`

**Authentication:**
```bash
Authorization: Bearer ${API_KEY}
```

**Available Endpoints:**
- `GET /api/v1/skills/search?q={query}&page={1}&limit={20}&sortBy={recent|stars}`
- `GET /api/v1/skills/ai-search?q={query}`

**Response Format (Keyword Search):**
```json
{
  "success": true,
  "data": {
    "skills": [
      {
        "id": "...",
        "name": "skill-name",
        "author": "AuthorName",
        "description": "...",
        "githubUrl": "https://github.com/user/repo/tree/main/path",
        "skillUrl": "https://skillsmp.com/skills/...",
        "stars": 10,
        "updatedAt": 1768838561
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 3601,
      "totalPages": 1801,
      "hasNext": true
    }
  }
}
```

**Response Format (AI Search):**
```json
{
  "success": true,
  "data": {
    "search_query": "...",
    "data": [
      {
        "file_id": "...",
        "filename": "...",
        "score": 0.656,
        "skill": {
          "id": "...",
          "name": "...",
          "author": "...",
          "description": "...",
          "githubUrl": "...",
          "skillUrl": "...",
          "stars": 0,
          "updatedAt": 1769542668
        }
      }
    ]
  }
}
```

**Error Handling:**
- `401`: Invalid or missing API key
- `400`: Missing required query parameter
- `500`: Internal server error

---

## SkillHub API

**Base URL:** `https://skills.palebluedot.live/api`

**Authentication:** None required (open API)

**Available Endpoints:**
- `GET /api/skills?q={query}&limit={20}` -- Search skills by keyword
- `GET /api/skills/{id}` -- Get full skill details (includes `skillPath`, `branch`, `rawContent`)
- `GET /api/categories` -- List skill categories
- `GET /api/health` -- Health check

**Search Response Format:**
```json
{
  "skills": [
    {
      "id": "wshobson/agents/debugging-strategies",
      "name": "debugging-strategies",
      "description": "Master systematic debugging...",
      "githubOwner": "wshobson",
      "githubRepo": "agents",
      "githubStars": 27021,
      "downloadCount": 0,
      "securityScore": 100,
      "securityStatus": null,
      "rating": 0,
      "isVerified": false,
      "compatibility": { "platforms": [] }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1000,
    "totalPages": 50
  },
  "searchEngine": "meilisearch",
  "processingTimeMs": 10
}
```

**Detail Response Format (GET /api/skills/{id}):**
```json
{
  "id": "wshobson/agents/debugging-strategies",
  "name": "debugging-strategies",
  "description": "...",
  "githubOwner": "wshobson",
  "githubRepo": "agents",
  "skillPath": "plugins/developer-essentials/skills/debugging-strategies",
  "branch": "main",
  "githubStars": 27021,
  "rawContent": "---\nname: debugging-strategies\n..."
}
```

**Key Fields for Installation:**
- `skillPath`: The actual directory path within the GitHub repo (CRITICAL -- the `id` does NOT match the file path)
- `branch`: The branch name (e.g., `main`)
- `githubOwner` + `githubRepo`: Used to construct the GitHub URL
- `rawContent`: Full SKILL.md content (can be used as fallback if GitHub is unreachable)

**Error Handling:**
- `404`: Skill not found
- `500`: Internal server error

---

## ClawHub API

**Base URL:** `https://clawhub.ai/api/v1`

**Authentication:** None required (open API)

**Rate Limits:** 120 reads/min per IP (shown in `x-ratelimit-remaining` and `x-ratelimit-reset` response headers)

**Available Endpoints:**
- `GET /api/v1/search?q={query}&limit={20}` -- Semantic/vector search (ranked by similarity score)
- `GET /api/v1/skills?limit={20}&sort={stars|downloads|updated|trending}&cursor={cursor}` -- Browse/list with cursor pagination
- `GET /api/v1/skills/{slug}` -- Get full skill details (owner, version, moderation status)
- `GET /api/v1/skills/{slug}/file?path={filepath}&version={ver}` -- Get raw file content (text/plain, NOT JSON)
- `GET /api/v1/download?slug={slug}&version={ver}` -- Download full skill as ZIP

**Search Response Format (GET /api/v1/search):**
```json
{
  "results": [
    {
      "score": 0.82,
      "slug": "self-improving-agent",
      "displayName": "Self-Improving Agent",
      "summary": "An agent that iteratively improves itself...",
      "version": "1.0.0",
      "updatedAt": "2026-01-15T10:30:00Z"
    }
  ]
}
```

**Browse Response Format (GET /api/v1/skills):**
```json
{
  "items": [
    {
      "slug": "self-improving-agent",
      "displayName": "Self-Improving Agent",
      "summary": "...",
      "version": "1.0.0",
      "stats": {
        "stars": 42,
        "downloads": 150
      }
    }
  ],
  "nextCursor": "eyJ..."
}
```

**Detail Response Format (GET /api/v1/skills/{slug}):**
```json
{
  "skill": {
    "slug": "self-improving-agent",
    "displayName": "Self-Improving Agent",
    "summary": "...",
    "version": "1.0.0"
  },
  "owner": {
    "handle": "username",
    "displayName": "User Name"
  },
  "latestVersion": "1.0.0",
  "moderation": "approved"
}
```

**File Endpoint (GET /api/v1/skills/{slug}/file?path=SKILL.md):**
- Returns raw `text/plain` content (NOT JSON)
- Response headers include `x-content-sha256` (integrity hash) and `x-content-size` (byte count)
- Use `version` query param to fetch a specific version (defaults to latest)

**Key Differences from SkillsMP/SkillHub:**
- **Direct hosting:** ClawHub hosts skill files directly -- no GitHub URL construction needed
- **Versioned skills:** Each skill has explicit version numbers; use `version` param to pin
- **Slug-based IDs:** Skills are identified by `slug` (e.g., `self-improving-agent`), not GitHub paths
- **Semantic search built-in:** The `/search` endpoint uses vector similarity, not keyword matching
- **VirusTotal integration:** ClawHub scans skills via VirusTotal partnership; `moderation` field indicates status

**Error Handling:**
- `404`: Skill or file not found
- `429`: Rate limit exceeded (120 reads/min)
- `500`: Internal server error

---

## skills.sh API

**Base URL:** `https://skills.sh/api`

**Authentication:** None required (open API)

**Available Endpoints:**
- `GET /api/search?q={query}&limit={20}` -- Keyword search across GitHub-hosted skills

**Search Response Format:**
```json
{
  "skills": [
    {
      "id": "wshobson/agents/debugging-strategies",
      "name": "debugging-strategies",
      "installs": 1234,
      "source": "wshobson/agents"
    }
  ]
}
```

**Key Fields:**
- `id`: Full `owner/repo/skill-name` path (used for GitHub URL construction)
- `source`: GitHub repo owner/path (used to construct the raw GitHub URL)
- `name`: Skill display name
- `installs`: Installation count

**GitHub URL Construction:**
- skills.sh indexes skills hosted on GitHub -- it does NOT host files directly
- To install, construct the raw GitHub URL:
    ```
    https://raw.githubusercontent.com/{source}/{branch}/{skill-path}/SKILL.md
    ```
- The `skill-path` is extracted from `id` by removing the `{owner}/{repo}/` prefix
- Default branch is typically `main` (try `master` if `main` returns 404)

**Error Handling:**
- `200`: Success
- `404`: No results found
- `500`: Internal server error
