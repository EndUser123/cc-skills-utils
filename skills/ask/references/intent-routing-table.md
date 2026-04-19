# Intent-Based Routing Table

Complete mapping of user intent patterns to target commands.

## Intent Pattern Routing

| Intent Pattern                                                 | Route To            | Purpose                                |
| -------------------------------------------------------------- | ------------------- | -------------------------------------- |
| Extraction/justification, "should I extract X", "is creating Y justified", "new module/service" | `/adf`              | Architecture gate: evaluate if structural change is justified |
| Architecture decisions, design patterns, boundaries             | `/design`             | Design guidance, template-based analysis |
| Root cause analysis, "why does X fail", debugging              | `/rca`              | Error diagnosis, fix proposals         |
| Debugging, "stuck on error", "debug this"                      | `/debug`            | Structured debugging workflow          |
| Research, learning, "how does X work"                          | `/research`         | Information gathering, synthesis       |
| Documentation: ingest, update, create                          | `/doc`              | Document code, ingest docs to CKS      |
| Code analysis, quality, "improve this code"                    | `/analyze`          | Unified analysis engine                |
| Planning, task breakdown, "help me plan"                       | `/breakdown`        | Granular implementation planning       |
| Workflow orchestration, complex project                        | `/cwo`              | CWO unified orchestration              |
| Truth verification, "did I actually", "prove it"               | `/truth`            | Claim validation                       |
| Search chat history, "what did we discuss"                     | `/search`           | Unified intelligent search (auto-detects chat/web) |
| Discover codebase patterns, "what exists"                      | `/discover`         | Intelligent codebase discovery         |
| Verify implementation, "check my work"                         | `/verify`           | Verification command                   |
| Challenge assumptions, critical analysis                       | `/design --challenge` | Thoughtful disagreement                |
| Get multiple perspectives, debate                              | `/llm-debate`       | Decision alignment                     |
| Build feature, new feature, implement feature                  | `/build`            | Feature development workflow           |
| Modernize, upgrade, tech debt, refactor codebase               | `/evolve`           | Codebase modernization workflow        |
| QA, certify, test feature, e2e test                            | `/qa`               | Feature certification workflow         |

## Command Categories

- **Planning**: `/breakdown`, `/cwo`, `/flow`
- **Analysis**: `/analyze`, `/design`, `/discover`
- **Debugging**: `/debug`, `/rca`
- **Research**: `/research`, `/search`, `/cks`
- **Documentation**: `/doc` - Ingest, update, create docs
- **Testing**: `/test`, `/tdd`, `/verify`
- **LLM**: `/llm-route`, `/llm-debate`, `/llm-models`

## Command Discovery

```bash
/ask "list commands"              # Shows all discovered commands
/ask "help"                       # Universal help system
/ask "what [category] commands"    # Category-based discovery
```
