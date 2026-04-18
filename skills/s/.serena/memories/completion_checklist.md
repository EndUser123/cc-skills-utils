# What to do when a task is completed

After finishing a coding task, follow these steps to ensure quality and compliance with the project's standards.

## 1. Verify Implementation
- Ensure the code follows the 'Director Model' where human oversight is possible.
- Check that all new features or bug fixes have been implemented correctly.
- Ensure that the code uses asynchronous I/O (`asyncio`) where appropriate.

## 2. Testing
- Run existing tests to ensure no regressions:
  ```powershell
  pytest tests/
  ```
- Add new test cases to the existing test files or create a new test file in `tests/` to verify the new feature or fix.
- Ensure all tests pass with no errors.

## 3. Linting and Formatting
- Check and fix linting issues using `ruff`:
  ```powershell
  ruff check . --fix
  ```
- Format the codebase using `ruff`:
  ```powershell
  ruff format .
  ```

## 4. Documentation
- Update `SKILL.md` if the user-facing interface, flags, or features have changed.
- Update `CHANGELOG.md` with a summary of the changes following the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format and Semantic Versioning.
- Add entries to `IMPROVEMENTS.md` if any general improvements were made.

## 5. Security Check
- Ensure no API keys or secrets are logged or committed.
- Check that user inputs are sanitized before being sent to external LLM providers.
- Validate paths and block directory traversal attempts.

## 6. Final Review
- Confirm that the change is either backward-compatible or all references have been updated.
- Use `find_referencing_symbols` to check for impacts on other parts of the system.
