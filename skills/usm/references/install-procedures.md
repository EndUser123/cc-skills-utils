# Installation Procedures by Source

Detailed installation procedures for each skill source. The core workflow is in SKILL.md Section 1.

## A. Installing from SkillsMP API

1. **Fetch Skill Content:**
   - Convert `githubUrl` to raw content URL:
     ```
     Input:  https://github.com/{user}/{repo}/tree/{branch}/{path}
     Output: https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}/SKILL.md
     ```
   - Fetch the SKILL.md content using curl or web_fetch

2. **Create Directory:**
   - Use skill `name` from API response for directory: `.../skills/{skill-name}/`
   - Example: `.../skills/code-debugging/`

3. **Save SKILL.md:**
   - Write the fetched content to `SKILL.md` in the new directory
   - Preserve the original YAML frontmatter and content

4. **Handle Additional Files (Optional):**
   - Check if GitHub repo has additional files (reference docs, scripts)
   - Optionally fetch and save them to maintain complete skill package

5. **Confirm:**
   - Report: "Installed '{name}' by {author} to {path}"
   - Show GitHub URL and stars count
   - Offer sync to other AI tools

---

## B. Installing from SkillHub (WITH FIXES)

**1. Fetch Skill Details with Validation:**
```bash
# Try SkillHub detail endpoint first
detail_response=$(curl -s "https://skills.palebluedot.live/api/skills/{id}")

# Parse response - check if critical fields are null
github_owner=$(echo "$detail_response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('githubOwner') or '')")
github_repo=$(echo "$detail_response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('githubRepo') or '')")
skill_path=$(echo "$detail_response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('skillPath') or '')")
branch=$(echo "$detail_response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('branch') or 'main')")

# VALIDATION: If critical fields are null, use GitHub search fallback
if [[ -z "$github_owner" || -z "$github_repo" ]]; then
    echo "Warning: SkillHub detail endpoint returned null fields"
    echo "Using GitHub search fallback..."

    skill_name="${id##*/}"
    search_url="https://api.github.com/search/code?q=${skill_name}+in:file+extension:md"
    search_results=$(curl -s "$search_url" -H "User-Agent: Universal-Skills-Manager")

    first_path=$(echo "$search_results" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('items', [{}])[0].get('path', '') if d.get('items') else '')")

    if [[ -n "$first_path" ]]; then
        raw_url="https://raw.githubusercontent.com/${first_path}"
        echo "Found via GitHub search: $raw_url"
        curl -s "$raw_url" -o "/tmp/skill-download.md"

        if [[ -s "/tmp/skill-download.md" ]]; then
            echo "Successfully downloaded skill via GitHub search fallback"
        else
            echo "GitHub search fallback also failed"
            return 1
        fi
    else
        echo "Could not find skill in GitHub"
        return 1
    fi
fi

# If SkillHub details were complete, use original flow
if [[ -n "$skill_path" && -n "$github_owner" ]]; then
    github_url="https://github.com/${github_owner}/${github_repo}/tree/${branch}/${skill_path}"

    # VALIDATION: Check URL exists before attempting install
    validation_check=$(curl -s -o /dev/null -w "%{http_code}" "$github_url")

    if [[ "$validation_check" != "200" ]]; then
        echo "URL validation failed (HTTP $validation_check)"
        echo "Trying GitHub search fallback..."

        skill_name=$(basename "$skill_path")
        search_url="https://api.github.com/search/code?q=${skill_name}+repo:${github_owner}/${github_repo}+in:file+extension:md"
        search_results=$(curl -s "$search_url" -H "User-Agent: Universal-Skills-Manager")

        first_path=$(echo "$search_results" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('items', [{}])[0].get('path', '') if d.get('items') else '')")

        if [[ -n "$first_path" ]]; then
            raw_url="https://raw.githubusercontent.com/${first_path}"
            echo "Found via fallback: $raw_url"
            curl -s "$raw_url" -o "/tmp/skill-download.md"
        else
            echo "Cannot locate skill - repository may have moved"
            return 1
        fi
    else
        echo "URL validation passed (HTTP 200)"
    fi
fi

# Convert to raw GitHub URL for download
if [[ -n "$skill_path" && -z "$raw_url" ]]; then
    raw_url="https://raw.githubusercontent.com/${github_owner}/${github_repo}/${branch}/${skill_path}/SKILL.md"
fi

if [[ -z "$raw_url" ]]; then
    echo "No valid URL found for download"
    return 1
fi

echo "Downloading from: $raw_url"
curl -s "$raw_url" -o "/tmp/skill-download.md"

if [[ ! -s "/tmp/skill-download.md" ]]; then
    echo "Download failed or returned empty file"
    return 1
fi

if ! grep -q "^---" "/tmp/skill-download.md"; then
    echo "Warning: Downloaded file missing YAML frontmatter - may not be a valid skill"
fi

echo "Skill downloaded successfully, proceeding with installation..."
```

**2. Create Directory and Install:**
- Use skill `name` for directory: `.../skills/{skill-name}/`
- Move `/tmp/skill-download.md` to `.../skills/{skill-name}/SKILL.md`

**3. Confirm:**
- Report: "Installed '{name}' from SkillHub to {path}"
- Show GitHub URL and stars count
- Offer sync to other AI tools

### Key Changes:
1. **Null Field Detection:** Checks if SkillHub detail endpoint returns nulls
2. **GitHub Search Fallback:** Uses GitHub API search when SkillHub fails
3. **URL Validation:** Checks HTTP 200 before attempting install
4. **Error Recovery:** Multiple fallback strategies with clear error messages
5. **Download Verification:** Confirms file actually downloaded before proceeding

---

## C. Installing from ClawHub

ClawHub hosts skill files directly (not on GitHub), so the install flow bypasses `install_skill.py` and fetches content via ClawHub's API.

1. **Fetch SKILL.md Content:**
   - Use ClawHub's file endpoint to get the raw SKILL.md:
     ```bash
     curl -s "https://clawhub.ai/api/v1/skills/{slug}/file?path=SKILL.md" \
       -H "User-Agent: Universal-Skills-Manager" \
       -o /tmp/clawhub-{slug}/SKILL.md
     ```
   - **IMPORTANT:** This endpoint returns raw `text/plain` content, NOT JSON. Save the response body directly as the file.
   - The `x-content-sha256` response header can be used to verify file integrity.

2. **Handle Multi-File Skills (if applicable):**
   - If the skill has additional files (scripts, configs), use ClawHub's download endpoint:
     ```bash
     curl -s "https://clawhub.ai/api/v1/download?slug={slug}" \
       -H "User-Agent: Universal-Skills-Manager" \
       -o /tmp/clawhub-{slug}.zip
     unzip -o /tmp/clawhub-{slug}.zip -d /tmp/clawhub-{slug}/
     ```
   - To check if a skill has multiple files, inspect the detail response from `GET /api/v1/skills/{slug}` -- the `latestVersion` object may indicate file count.

3. **Run Security Scan:**
   - Since `install_skill.py` is bypassed, run the security scanner manually:
     ```bash
     python3 ~/.claude/skills/usm/scripts/scan_skill.py /tmp/clawhub-{slug}/
     ```
   - Review any findings before proceeding. ClawHub has VirusTotal integration but our scan provides an additional layer.

4. **Validate YAML Frontmatter:**
   - Verify the SKILL.md has valid YAML frontmatter (name, description fields).
   - If invalid, warn the user and ask whether to proceed.

5. **Create Directory and Install:**
   - Create the target directory: `.../skills/{slug}/`
   - Copy all files from the temp directory to the destination:
     ```bash
     mkdir -p {target-path}/{slug}
     cp -r /tmp/clawhub-{slug}/* {target-path}/{slug}/
     ```

6. **Confirm:**
   - Report: "Installed '{displayName}' (v{version}) from ClawHub to {path}"
   - Show version info and stars count
   - Offer sync to other AI tools

7. **Cleanup:**
   - Remove the temporary directory:
     ```bash
     rm -rf /tmp/clawhub-{slug}/ /tmp/clawhub-{slug}.zip
     ```

---

## D. Installing from Local Source (Sync/Copy)

1. **Retrieve:** Read all files from the source directory.
2. **Create Directory:** Create the target directory `.../skills/{slug}/`.
3. **Save Files:** Copy all files to the new location, preserving filenames.

---

## E. Installing from skills.sh

skills.sh indexes skills hosted on GitHub (it does not host files directly). Use the `source` field to construct the GitHub raw URL.

1. **Construct GitHub Raw URL:**
   - From the search result, `source` = GitHub repo owner/path (e.g., `wshobson/agents`)
   - `id` = full `owner/repo/skill-name` path (e.g., `wshobson/agents/debugging-strategies`)
   - Construct the raw URL:
       ```
       https://raw.githubusercontent.com/{source}/{branch}/{skill-path}/SKILL.md
       ```
   - The `skill-path` is the directory containing the skill (extract from `id` by removing `{owner}/{repo}/` prefix)

2. **Download SKILL.md:**
   ```bash
   curl -s "https://raw.githubusercontent.com/{source}/{branch}/{skill-path}/SKILL.md" \
     -o /tmp/skill-download.md
   ```

3. **Verify Download:**
   - Confirm the file has YAML frontmatter
   - Confirm the downloaded `name` field matches the expected skill name

4. **Create Directory and Install:**
   - Use skill `name` for directory: `.../skills/{skill-name}/`
   - Move `/tmp/skill-download.md` to `.../skills/{skill-name}/SKILL.md`

5. **Confirm:**
   - Report: "Installed '{name}' from skills.sh to {path}"
   - Show the GitHub source URL
   - Offer sync to other AI tools
