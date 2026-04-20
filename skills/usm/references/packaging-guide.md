# Packaging Guide for claude.ai / Claude Desktop

Detailed procedures for packaging skills as ZIP files for upload to claude.ai or Claude Desktop.

## Full Packaging Procedure

**Trigger:** User wants to use this skill in claude.ai or Claude Desktop.

1. **Explain the Process:**
   "I'll create a ZIP file with this skill ready for upload to claude.ai or Claude Desktop. Since cloud environments don't have access to your local environment variables, I can optionally embed your API key in the package. Note: the API key is optional -- SkillHub and ClawHub search work without one."

2. **Validate Frontmatter Compatibility (CRITICAL -- do this BEFORE packaging):**
   Run `validate_frontmatter.py` to check the SKILL.md against the Agent Skills spec:
   ```bash
   # Validate only (report issues)
   python3 scripts/validate_frontmatter.py /path/to/SKILL.md

   # Validate and auto-fix (overwrites file)
   python3 scripts/validate_frontmatter.py /path/to/SKILL.md --fix

   # Validate a ZIP file
   python3 scripts/validate_frontmatter.py /path/to/skill.zip --fix
   ```
   The script checks for unsupported top-level keys, nested metadata, non-string metadata values, and field length violations. With `--fix`, it automatically moves unsupported keys into `metadata`, flattens nested objects, and converts values to strings. Tell the user what was fixed. See Operational Rule 5 in SKILL.md for the full spec.

3. **Collect API Key (Optional):**
   - Ask: "Would you like to include your SkillsMP API key for curated search? This is optional -- SkillHub and ClawHub work without a key. If you skip this, the packaged skill will still work for SkillHub and ClawHub searches."
   - If user wants to include a key:
       - Ask: "Please provide your SkillsMP API key. You can get one at https://skillsmp.com"
       - Wait for user to provide the key
       - **Validate:** Key must start with `sk_live_skillsmp_`. If invalid, reject and re-prompt or offer to skip.
       - **Security:** Do not echo or display the key back to the user
   - If user skips, create the ZIP without `config.json`
   - **Credential safety warning (IMPORTANT -- always display this if a key is included):**
       > "**Security note:** This ZIP will contain your API key in plain text. Please follow these precautions:
       > - **Do NOT share** this ZIP publicly, post it online, or commit it to version control
       > - **Do NOT distribute** this ZIP to others -- each user should package their own
       > - **Use a scoped/least-privilege key** if your provider supports it
       > - **Rotate your key** if you suspect the ZIP was exposed
       > - The key is stored locally in `config.json` inside the ZIP and is only used at runtime to authenticate with the SkillsMP API"

4. **Create Package Contents:**
   - Create a temporary directory structure:
       ```
       universal-skills-manager/
       ├── SKILL.md          # Copy from current skill
       ├── config.json       # Create with embedded API key
       └── scripts/
           └── install_skill.py  # Copy from current skill
       ```
   - Generate `config.json` with the user's API key:
       ```json
       {
         "skillsmp_api_key": "USER_PROVIDED_KEY_HERE"
       }
       ```

5. **Create ZIP File:**
   - Use Python to create the ZIP:
       ```python
       import zipfile
       import json
       import tempfile
       from pathlib import Path

       # Create ZIP in user's Downloads or current directory
       zip_path = Path.home() / "Downloads" / "universal-skills-manager.zip"
       skill_dir = Path("~/.claude/skills/universal-skills-manager").expanduser()

       with tempfile.TemporaryDirectory() as temp_dir:
           temp_path = Path(temp_dir)

           # Copy skill files
           for file_path in skill_dir.rglob('*'):
               if file_path.is_file() and file_path.name != 'config.json':
                   rel_path = file_path.relative_to(skill_dir)
                   dest = temp_path / rel_path
                   dest.parent.mkdir(parents=True, exist_ok=True)
                   dest.write_bytes(file_path.read_bytes())

           # Create config.json with API key
           config = {"skillsmp_api_key": "USER_API_KEY"}
           (temp_path / "config.json").write_text(json.dumps(config, indent=2))

           # Create ZIP
           with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
               for file_path in temp_path.rglob('*'):
                   if file_path.is_file():
                       arcname = f"universal-skills-manager/{file_path.relative_to(temp_path)}"
                       zf.write(file_path, arcname)
       ```
   - Alternatively, provide the ZIP as a downloadable artifact

6. **Provide Upload Instructions:**
   - "Your skill package is ready! To use it:"
   - "1. Download the ZIP file: `universal-skills-manager.zip`"
   - "2. Go to claude.ai -> Settings -> Capabilities"
   - "3. Scroll to Skills section and click 'Upload skill'"
   - "4. Select the ZIP file and upload"
   - "5. Enable the skill and start using it!"

7. **Security Reminder:**
   - If a key was embedded: "This ZIP contains your API key. Do NOT share it publicly, distribute it to others, or commit it to version control. If you need to share the skill, create a key-free version (without `config.json`) and let each user add their own key."
   - If no key was embedded: "This ZIP is safe to share -- it contains no credentials. Recipients can add their own API key later, or use SkillHub/ClawHub search which requires no key."
